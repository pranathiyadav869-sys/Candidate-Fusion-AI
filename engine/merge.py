"""
engine/merge.py
---------------
Merges data from multiple parsed sources into one canonical CandidateProfile.

Conflict Resolution Strategy
-----------------------------
Priority order (highest → lowest):
  RESUME (0.95) > ATS (0.90) > GITHUB (0.88) > CSV (0.82)

For scalar fields (name, location, headline):
  - Pick the value from the highest-priority source that has a non-null value.

For list fields (emails, phones, skills, experience, education):
  - Union all values, deduplicate, then sort by confidence.
  - For emails/phones: strict deduplication after normalization.
  - For skills: deduplicate by canonical name.
  - For experience: deduplicate by (company, title, start_date) tuple.
  - For education: deduplicate by (institution, degree) tuple.

Design Decision: We deliberately do NOT silently drop values from lower-priority
sources for list fields. A recruiter CSV may have a phone number the resume
omitted. We want all valid emails in the output.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional

from engine.confidence import compute_field_confidence, compute_overall_confidence
from engine.normalize import (
    normalize_date,
    normalize_email,
    normalize_location,
    normalize_name,
    normalize_phone,
    normalize_skill,
    normalize_url,
    normalize_years_experience,
)
from engine.provenance import ProvenanceTracker
from engine.schema import (
    CandidateProfile,
    EducationEntry,
    ExperienceEntry,
    FieldProvenance,
    LinkEntry,
    SkillEntry,
    SourceName,
)

logger = logging.getLogger(__name__)

# Source priority: lower index = higher priority
SOURCE_PRIORITY: List[SourceName] = [
    SourceName.RESUME,
    SourceName.ATS,
    SourceName.GITHUB,
    SourceName.CSV,
    SourceName.DERIVED,
]


def _priority(source: SourceName) -> int:
    """Lower return value = higher priority."""
    try:
        return SOURCE_PRIORITY.index(source)
    except ValueError:
        return 99


def merge_sources(
    source_records: Dict[SourceName, Dict[str, Any]],
) -> CandidateProfile:
    """
    Primary entry point for the merge engine.

    Parameters
    ----------
    source_records : dict mapping SourceName → parsed dict from that parser.
                     Parsers return dicts with keys matching schema field names.

    Returns
    -------
    CandidateProfile with all fields populated, provenance recorded, and
    confidence scores computed.
    """
    tracker = ProvenanceTracker()
    sources_present = list(source_records.keys())

    # -----------------------------------------------------------------------
    # Scalar fields: pick from highest-priority source
    # -----------------------------------------------------------------------
    full_name = _merge_scalar(
        "full_name", source_records, tracker,
        transform=normalize_name,
    )
    location = _merge_scalar(
        "location", source_records, tracker,
        transform=normalize_location,
    )
    headline = _merge_scalar("headline", source_records, tracker)
    years_exp_raw = _merge_scalar("years_experience", source_records, tracker)
    years_experience = normalize_years_experience(years_exp_raw)

    # -----------------------------------------------------------------------
    # Email list: union from all sources, deduplicate
    # -----------------------------------------------------------------------
    emails = _merge_email_list("emails", source_records, tracker)

    # -----------------------------------------------------------------------
    # Phone list: union from all sources, deduplicate
    # -----------------------------------------------------------------------
    phones = _merge_phone_list("phones", source_records, tracker)

    # -----------------------------------------------------------------------
    # Links: union, deduplicate by URL
    # -----------------------------------------------------------------------
    links = _merge_links("links", source_records, tracker)

    # -----------------------------------------------------------------------
    # Skills: union by canonical name, annotate with sources
    # -----------------------------------------------------------------------
    skills = _merge_skills("skills", source_records, tracker)

    # -----------------------------------------------------------------------
    # Experience: deduplicate by (company, title) fingerprint
    # -----------------------------------------------------------------------
    experience = _merge_experience("experience", source_records, tracker)

    # -----------------------------------------------------------------------
    # Education: deduplicate by (institution, degree) fingerprint
    # -----------------------------------------------------------------------
    education = _merge_education("education", source_records, tracker)

    # -----------------------------------------------------------------------
    # Finalize provenance and compute confidence scores
    # -----------------------------------------------------------------------
    provenance = tracker.finalize()

    field_confidences = {}

    for field, fp in provenance.items():
        conf = fp.confidence

        # Penalize if only one source provided the field
        source_count = len({entry.source for entry in fp.entries})

        if source_count == 1:
            conf -= 0.08
        elif source_count == 2:
            conf -= 0.03
        elif source_count >= 3:
            conf += 0.02

        field_confidences[field] = max(0.0, min(1.0, round(conf, 4)))

    # Default confidence for merged list fields if provenance doesn't contain them
    if emails and "emails" not in field_confidences:
        field_confidences["emails"] = 0.88

    if skills and "skills" not in field_confidences:
        field_confidences["skills"] = 0.90

    if experience and "experience" not in field_confidences:
        field_confidences["experience"] = 0.88

    if education and "education" not in field_confidences:
        field_confidences["education"] = 0.87

    overall_confidence = compute_overall_confidence(
        field_confidences,
        sources_present,
    )

    return CandidateProfile(
        candidate_id=(
            source_records.get(SourceName.ATS, {}).get("candidate_id")
            or str(uuid.uuid4())),
        full_name=full_name,
        emails=emails,
        phones=phones,
        location=location,
        links=links,
        headline=headline,
        years_experience=years_experience,
        skills=skills,
        experience=experience,
        education=education,
        provenance=provenance,
        overall_confidence=overall_confidence,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _merge_scalar(
    field: str,
    source_records: Dict[SourceName, Dict[str, Any]],
    tracker: ProvenanceTracker,
    transform=None,
) -> Optional[Any]:
    """
    Pick the best value for a scalar field from all sources.
    Records all candidates in provenance.
    """
    best_value = None
    best_priority = 999

    for source in SOURCE_PRIORITY:
        record = source_records.get(source)
        if not record:
            continue
        raw = record.get(field)
        if raw is None or raw == "":
            continue
        value = transform(raw) if transform else raw
        if value is None:
            continue

        conf = compute_field_confidence(field, value, source)
        tracker.record(field, source, "direct_field", raw, conf)

        priority = _priority(source)
        if priority < best_priority:
            best_value = value
            best_priority = priority

    if best_value is not None:
        # Identify winning source
        winning_source = None
        for source in SOURCE_PRIORITY:
            record = source_records.get(source)
            if record and record.get(field):
                winning_source = source
                break
        if winning_source:
            conf = compute_field_confidence(field, best_value, winning_source)
            tracker.select(field, winning_source, conf)

    return best_value


def _merge_email_list(
    field: str,
    source_records: Dict[SourceName, Dict[str, Any]],
    tracker: ProvenanceTracker,
) -> List[str]:
    """Union emails from all sources, normalize and deduplicate."""
    seen: Dict[str, SourceName] = {}  # email → first-seen source
    for source in SOURCE_PRIORITY:
        record = source_records.get(source)
        if not record:
            continue
        raw_emails = record.get(field, [])
        if isinstance(raw_emails, str):
            raw_emails = [raw_emails]
        for raw in raw_emails:
            normalized = normalize_email(raw)
            if normalized and normalized not in seen:
                seen[normalized] = source
                conf = compute_field_confidence(field, normalized, source)
                tracker.record(field, source, "email_normalize", raw, conf)

    if seen:
        # Select highest-priority source as "the" source
        for source in SOURCE_PRIORITY:
            if any(v == source for v in seen.values()):
                conf = compute_field_confidence(field, list(seen.keys()), source)
                tracker.select(field, source, conf)
                break

    return list(seen.keys())


def _merge_phone_list(
    field: str,
    source_records: Dict[SourceName, Dict[str, Any]],
    tracker: ProvenanceTracker,
) -> List[str]:
    """Union phones from all sources, normalize to E.164 and deduplicate."""
    seen: Dict[str, SourceName] = {}
    for source in SOURCE_PRIORITY:
        record = source_records.get(source)
        if not record:
            continue
        raw_phones = record.get(field, [])
        if isinstance(raw_phones, str):
            raw_phones = [raw_phones]
        for raw in raw_phones:
            normalized = normalize_phone(raw)
            if normalized and normalized not in seen:
                seen[normalized] = source
                conf = compute_field_confidence(field, normalized, source)
                tracker.record(field, source, "phone_e164", raw, conf)

    if seen:
        for source in SOURCE_PRIORITY:
            if any(v == source for v in seen.values()):
                conf = compute_field_confidence(field, list(seen.keys()), source)
                tracker.select(field, source, conf)
                break

    return list(seen.keys())


def _merge_links(
    field: str,
    source_records: Dict[SourceName, Dict[str, Any]],
    tracker: ProvenanceTracker,
) -> List[LinkEntry]:
    """Union links by URL, deduplicate."""
    seen: Dict[str, LinkEntry] = {}
    for source in SOURCE_PRIORITY:
        record = source_records.get(source)
        if not record:
            continue
        raw_links = record.get(field, [])
        for item in raw_links:
            if isinstance(item, dict):
                url = normalize_url(item.get("url", ""))
                label = item.get("label")
            elif isinstance(item, str):
                url = normalize_url(item)
                label = None
            else:
                continue
            if url and url not in seen:
                seen[url] = LinkEntry(url=url, label=label)
    return list(seen.values())


def _merge_skills(
    field: str,
    source_records: Dict[SourceName, Dict[str, Any]],
    tracker: ProvenanceTracker,
) -> List[SkillEntry]:
    """
    Build a deduplicated skill list. Each SkillEntry records ALL sources
    that mentioned the skill and the highest confidence seen.
    """
    # canonical_name → {sources, max_confidence, raw_name}
    skill_map: Dict[str, Dict] = {}

    for source in SOURCE_PRIORITY:
        record = source_records.get(source)
        if not record:
            continue
        raw_skills = record.get(field, [])
        for raw in raw_skills:
            if not raw:
                continue
            canonical = normalize_skill(str(raw))
            key = canonical.lower()
            conf = compute_field_confidence(field, canonical, source)
            tracker.record(field, source, "skill_normalize", raw, conf)
            if key not in skill_map:
                skill_map[key] = {
                    "name": str(raw).strip(),
                    "canonical": canonical,
                    "sources": set(),
                    "confidence": 0.0,
                }
            skill_map[key]["sources"].add(source)
            skill_map[key]["confidence"] = max(skill_map[key]["confidence"], conf)

    result = []
    for data in skill_map.values():
        # Cross-source agreement bonus
        n_sources = len(data["sources"])
        agreement_bonus = (n_sources - 1) * 0.02
        final_conf = min(1.0, data["confidence"] + agreement_bonus)
        result.append(SkillEntry(
            name=data["name"],
            canonical_name=data["canonical"],
            sources=sorted(list(data["sources"]), key=lambda s: _priority(s)),
            confidence=round(final_conf, 4),
        ))

    # Sort: multi-source skills first, then by confidence desc
    result.sort(key=lambda s: (-len(s.sources), -s.confidence))
    return result


def _merge_experience(
    field: str,
    source_records: Dict[SourceName, Dict[str, Any]],
    tracker: ProvenanceTracker,
) -> List[ExperienceEntry]:
    """
    Merge experience entries from all sources.
    Deduplication key: normalized (company, title).
    Higher-priority source wins when there's a collision.
    """
    seen: Dict[str, ExperienceEntry] = {}

    for source in SOURCE_PRIORITY:
        record = source_records.get(source)
        if not record:
            continue
        entries = record.get(field, [])
        for raw_entry in entries:
            if not isinstance(raw_entry, dict):
                continue
            company = (raw_entry.get("company") or "").strip().lower()
            title = (raw_entry.get("title") or "").strip().lower()
            key = f"{company}||{title}"
            if key in seen:
                # Already have this from a higher-priority source; skip
                continue
            entry = ExperienceEntry(
                title=raw_entry.get("title"),
                company=raw_entry.get("company"),
                start_date=normalize_date(raw_entry.get("start_date")),
                end_date=normalize_date(raw_entry.get("end_date"))
                         or ("Present" if str(raw_entry.get("end_date", "")).lower() in ("present", "current", "now") else None),
                description=raw_entry.get("description"),
                location=normalize_location(raw_entry.get("location")),
            )
            seen[key] = entry
            tracker.record(field, source, "experience_merge", key, 0.85)

    entries_list = list(seen.values())
    # Sort by start_date descending (most recent first)
    entries_list.sort(
        key=lambda e: e.start_date or "0000-00", reverse=True
    )
    return entries_list


def _merge_education(
    field: str,
    source_records: Dict[SourceName, Dict[str, Any]],
    tracker: ProvenanceTracker,
) -> List[EducationEntry]:
    """Merge education entries, deduplicate by (institution, degree)."""
    seen: Dict[str, EducationEntry] = {}

    for source in SOURCE_PRIORITY:
        record = source_records.get(source)
        if not record:
            continue
        entries = record.get(field, [])
        for raw_entry in entries:
            if not isinstance(raw_entry, dict):
                continue
            institution = (raw_entry.get("institution") or "").strip().lower()
            degree = (raw_entry.get("degree") or "").strip().lower()
            key = f"{institution}||{degree}"
            if key in seen:
                continue
            gpa_raw = raw_entry.get("gpa")
            try:
                gpa = float(gpa_raw) if gpa_raw else None
            except (TypeError, ValueError):
                gpa = None
            entry = EducationEntry(
                institution=raw_entry.get("institution"),
                degree=raw_entry.get("degree"),
                field_of_study=raw_entry.get("field_of_study"),
                start_date=normalize_date(raw_entry.get("start_date")),
                end_date=normalize_date(raw_entry.get("end_date")),
                gpa=gpa,
            )
            seen[key] = entry
            tracker.record(field, source, "education_merge", key, 0.85)

    entries_list = list(seen.values())
    entries_list.sort(
        key=lambda e: e.end_date or "0000-00", reverse=True
    )
    return entries_list
