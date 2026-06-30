"""
parsers/ats_parser.py
---------------------
Parses ATS (Applicant Tracking System) JSON payloads into a canonical
intermediate dictionary compatible with the merge engine.

Design Decisions:
- ATS JSON schemas vary wildly between vendors (Greenhouse, Lever, Workday,
  Taleo, etc.). This parser handles a normalised superset by looking for
  known key variants at each level.
- All field extraction is wrapped in try/except so a malformed nested
  object never crashes the whole parse.
- Unknown top-level keys are silently ignored; no data is lost from known keys.
- Returns a single dict (not a list) because one ATS record = one candidate.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

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
from utils.constants import SOURCE_ATS
from utils.exceptions import ATSParseError
from utils.helpers import coerce_str, deep_get, generate_candidate_id, split_multi_value

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Key alias maps: known ATS field names → canonical name
# ---------------------------------------------------------------------------

_NAME_KEYS = ("full_name", "name", "candidate_name", "applicant_name",
              "firstName", "first_name", "display_name")
_FIRST_KEYS = ("first_name", "firstName", "given_name", "givenName")
_LAST_KEYS = ("last_name", "lastName", "family_name", "surname")
_EMAIL_KEYS = ("email", "emails", "email_address", "email_addresses",
               "emailAddress", "emailAddresses", "primary_email")
_PHONE_KEYS = ("phone", "phones", "phone_number", "phone_numbers",
               "phoneNumber", "phoneNumbers", "mobile", "cell")
_LOCATION_KEYS = ("location", "address", "city", "current_location",
                  "currentLocation", "residence", "city_state")
_HEADLINE_KEYS = ("headline", "title", "current_title", "currentTitle",
                  "job_title", "jobTitle", "position")
_SKILLS_KEYS = ("skills", "skill_tags", "skillTags", "technical_skills",
                "technicalSkills", "competencies", "tags")
_LINKS_KEYS = ("links", "social_links", "socialLinks", "profiles",
               "social_profiles", "socialProfiles", "urls")
_LINKEDIN_KEYS = ("linkedin", "linkedin_url", "linkedinUrl", "linkedin_profile")
_GITHUB_KEYS = ("github", "github_url", "githubUrl", "github_profile")
_PORTFOLIO_KEYS = ("portfolio", "website", "personal_site", "portfolioUrl")
_EXPERIENCE_KEYS = ("experience", "work_experience", "workExperience",
                    "positions", "jobs", "employment", "employment_history")
_EDUCATION_KEYS = ("education", "education_history", "educationHistory",
                   "academic_background", "qualifications")
_YOE_KEYS = ("years_experience", "years_of_experience", "yearsOfExperience",
             "experience_years", "experienceYears", "total_experience")
_ID_KEYS = ("candidate_id", "id", "applicant_id", "candidateId",
            "applicantId", "ats_id", "external_id")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _first_of(obj: dict, keys: tuple, default=None) -> Any:
    """Return the first non-None value found among the given keys."""
    for key in keys:
        val = obj.get(key)
        if val is not None:
            return val
    return default


def _extract_name(data: dict) -> str | None:
    """Reconstruct full name from whatever fields the ATS provides."""
    raw = _first_of(data, _NAME_KEYS)
    if raw:
        return normalize_name(coerce_str(raw))
    # Try to compose from first + last
    first = coerce_str(_first_of(data, _FIRST_KEYS))
    last = coerce_str(_first_of(data, _LAST_KEYS))
    if first or last:
        composed = " ".join(p for p in (first, last) if p)
        return normalize_name(composed)
    return None


def _extract_emails(data: dict) -> list[str]:
    """Extract and normalize all emails from the ATS record."""
    raw = _first_of(data, _EMAIL_KEYS, [])
    candidates: list[str] = []
    if isinstance(raw, str):
        candidates = split_multi_value(raw, r"[;|,\s]+")
    elif isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict):
                # e.g. {"type": "work", "value": "a@b.com"}
                v = item.get("value") or item.get("email") or item.get("address")
                if v:
                    candidates.append(str(v))
            elif isinstance(item, str):
                candidates.extend(split_multi_value(item, r"[;|,\s]+"))
    result = []
    for e in candidates:
        normalized = normalize_email(e)
        if normalized:
            result.append(normalized)
    return list(dict.fromkeys(result))  # dedup preserving order


def _extract_phones(data: dict) -> list[str]:
    """Extract and normalize all phones from the ATS record."""
    raw = _first_of(data, _PHONE_KEYS, [])
    candidates: list[str] = []
    if isinstance(raw, str):
        candidates = split_multi_value(raw, r"[;|]")
    elif isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict):
                v = item.get("value") or item.get("number") or item.get("phone")
                if v:
                    candidates.append(str(v))
            elif isinstance(item, str):
                candidates.append(item)
    result = []
    for p in candidates:
        normalized = normalize_phone(p)
        if normalized:
            result.append(normalized)
    return list(dict.fromkeys(result))


def _extract_location(data: dict) -> str | None:
    """Extract location, handling both string and object forms."""
    raw = _first_of(data, _LOCATION_KEYS)
    if raw is None:
        return None
    if isinstance(raw, dict):
        # e.g. {"city": "Hyderabad", "state": "Telangana", "country": "India"}
        parts = [
            raw.get("city") or raw.get("locality"),
            raw.get("state") or raw.get("region"),
            raw.get("country"),
        ]
        raw = ", ".join(p for p in parts if p)
    return normalize_location(coerce_str(raw))


def _extract_skills(data: dict) -> list[str]:
    """Extract and normalise skill list from the ATS record."""
    raw = _first_of(data, _SKILLS_KEYS, [])
    skill_names: list[str] = []
    if isinstance(raw, str):
        skill_names = split_multi_value(raw, r"[;|,]")
    elif isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict):
                name = item.get("name") or item.get("skill") or item.get("value")
                if name:
                    skill_names.append(str(name))
            elif isinstance(item, str) and item.strip():
                skill_names.append(item.strip())
    normalized = [normalize_skill(s) for s in skill_names if s.strip()]
    return list(dict.fromkeys(normalized))


def _extract_links(data: dict) -> list[dict[str, str]]:
    """Extract social/profile links from all common ATS fields."""
    links: list[dict[str, str]] = []
    seen_urls: set[str] = set()

    def _add(url_raw: str | None, label: str) -> None:
        url = normalize_url(coerce_str(url_raw))
        if url and url not in seen_urls:
            seen_urls.add(url)
            links.append({"url": url, "label": label})

    # Dedicated shortcut fields
    _add(_first_of(data, _LINKEDIN_KEYS), "LinkedIn")
    _add(_first_of(data, _GITHUB_KEYS), "GitHub")
    _add(_first_of(data, _PORTFOLIO_KEYS), "Portfolio")

    # Generic links array
    raw_links = _first_of(data, _LINKS_KEYS, [])
    if isinstance(raw_links, list):
        for item in raw_links:
            if isinstance(item, dict):
                url = item.get("url") or item.get("href") or item.get("link")
                label = item.get("label") or item.get("type") or item.get("name") or "Link"
                _add(url, label)
            elif isinstance(item, str):
                _add(item, "Link")

    return links


def _extract_experience(data: dict) -> list[dict[str, Any]]:
    """
    Extract work experience entries from the ATS record.
    Handles nested structures from Greenhouse, Lever, Workday, Taleo etc.
    """
    raw_list = _first_of(data, _EXPERIENCE_KEYS, [])
    if not isinstance(raw_list, list):
        return []

    entries = []
    for item in raw_list:
        if not isinstance(item, dict):
            continue
        try:
            entry: dict[str, Any] = {
                "title": coerce_str(
                    item.get("title") or item.get("job_title") or item.get("role")
                ),
                "company": coerce_str(
                    item.get("company") or item.get("employer")
                    or item.get("organization") or deep_get(item, "company", "name")
                ),
                "start_date": normalize_date(coerce_str(
                    item.get("start_date") or item.get("startDate") or item.get("from")
                )),
                "end_date": normalize_date(coerce_str(
                    item.get("end_date") or item.get("endDate") or item.get("to")
                )) or ("Present" if str(
                    item.get("end_date") or item.get("endDate") or ""
                ).lower() in ("present", "current", "now", "") and item.get("current") else None),
                "description": coerce_str(
                    item.get("description") or item.get("summary") or item.get("responsibilities")
                ),
                "location": normalize_location(coerce_str(
                    item.get("location") or deep_get(item, "location", "name")
                )),
            }
            # Treat explicit "current: true" as present
            if item.get("current") is True or item.get("is_current") is True:
                entry["end_date"] = "Present"

            if entry["company"] or entry["title"]:
                entries.append(entry)
        except Exception as exc:
            logger.debug("Skipping malformed experience entry: %s", exc)

    return entries


def _extract_education(data: dict) -> list[dict[str, Any]]:
    """Extract education entries from the ATS record."""
    raw_list = _first_of(data, _EDUCATION_KEYS, [])
    if not isinstance(raw_list, list):
        return []

    entries = []
    for item in raw_list:
        if not isinstance(item, dict):
            continue
        try:
            gpa_raw = item.get("gpa") or item.get("grade")
            try:
                gpa = float(gpa_raw) if gpa_raw is not None else None
            except (TypeError, ValueError):
                gpa = None
            entry: dict[str, Any] = {
                "institution": coerce_str(
                    item.get("institution") or item.get("school")
                    or item.get("university") or item.get("college")
                ),
                "degree": coerce_str(
                    item.get("degree") or item.get("degree_type")
                    or item.get("qualification")
                ),
                "field_of_study": coerce_str(
                    item.get("field_of_study") or item.get("major")
                    or item.get("subject") or item.get("course")
                ),
                "start_date": normalize_date(coerce_str(
                    item.get("start_date") or item.get("startDate")
                )),
                "end_date": normalize_date(coerce_str(
                    item.get("end_date") or item.get("endDate")
                    or item.get("graduation_date") or item.get("graduationDate")
                )),
                "gpa": gpa,
            }
            if entry["institution"]:
                entries.append(entry)
        except Exception as exc:
            logger.debug("Skipping malformed education entry: %s", exc)

    return entries


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_ats(path: str | Path) -> dict[str, Any]:
    """
    Parse an ATS JSON file into a canonical candidate dictionary.

    Parameters
    ----------
    path : str | Path
        Path to the ATS JSON file.

    Returns
    -------
    dict[str, Any]
        Canonical intermediate dictionary ready for the merge engine.

    Raises
    ------
    ATSParseError
        If the file cannot be opened or is not valid JSON.
    """
    p = Path(path).resolve()
    if not p.exists():
        raise ATSParseError(f"File not found: {p}")

    logger.info("Parsing ATS JSON: %s", p)

    try:
        with p.open("r", encoding="utf-8") as fh:
            raw: dict = json.load(fh)
    except json.JSONDecodeError as exc:
        raise ATSParseError(f"Invalid JSON in {p}: {exc}") from exc
    except Exception as exc:
        raise ATSParseError(f"Cannot read {p}: {exc}") from exc

    if not isinstance(raw, dict):
        raise ATSParseError(
            f"Expected a JSON object at root level, got {type(raw).__name__}"
        )

    # Some ATS wrappers nest the candidate under a key
    for wrapper_key in ("candidate", "applicant", "data", "result"):
        if wrapper_key in raw and isinstance(raw[wrapper_key], dict):
            logger.debug("Unwrapping ATS root key: %r", wrapper_key)
            raw = raw[wrapper_key]
            break

    # ── candidate_id ──────────────────────────────────────────────────────
    raw_id = coerce_str(_first_of(raw, _ID_KEYS))
    candidate_id = raw_id or None

    # ── Core fields ───────────────────────────────────────────────────────
    full_name = _extract_name(raw)
    emails = _extract_emails(raw)
    phones = _extract_phones(raw)
    location = _extract_location(raw)
    headline = coerce_str(_first_of(raw, _HEADLINE_KEYS))
    skills = _extract_skills(raw)
    links = _extract_links(raw)
    experience = _extract_experience(raw)
    education = _extract_education(raw)

    # ── Years of experience ───────────────────────────────────────────────
    raw_yoe = _first_of(raw, _YOE_KEYS)
    years_experience = normalize_years_experience(raw_yoe) if raw_yoe is not None else None

    # ── Assign candidate_id if missing ────────────────────────────────────
    if not candidate_id:
        seed = emails[0] if emails else full_name or ""
        candidate_id = generate_candidate_id(seed or None)

    canonical: dict[str, Any] = {
        "candidate_id": candidate_id,
        "full_name": full_name,
        "emails": emails,
        "phones": phones,
        "location": location,
        "headline": headline,
        "skills": skills,
        "links": links,
        "experience": experience,
        "education": education,
        "years_experience": years_experience,
        "_source": SOURCE_ATS,
    }

    logger.info(
        "ATS: parsed candidate id=%s name=%r emails=%r skills=%d exp=%d",
        candidate_id, full_name, emails, len(skills), len(experience),
    )
    return canonical
