"""
parsers/resume_parser.py
------------------------
Extracts candidate information from a PDF resume using PyMuPDF (fitz).

Design Decisions:
- PyMuPDF is used for text extraction; no OCR (assumes digitally-created PDFs).
- The resume is split into logical sections using a keyword-based heading detector.
  This handles the majority of standard resume formats without ML.
- Regex is used for structured fields (email, phone, URL, date ranges).
- Section parsing is heuristic: first-match wins for unambiguous sections,
  but skills and experience use broader extraction since resumes vary so much.
- Corrupted / password-protected PDFs are caught and a ResumeParseError is raised.
- All fields are Optional; a partial parse is better than no parse.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

import fitz  # PyMuPDF

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
from utils.constants import RESUME_SECTION_KEYWORDS, SOURCE_RESUME
from utils.exceptions import ResumeParseError
from utils.helpers import coerce_str, deduplicate_preserving_order, generate_candidate_id

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Compiled regexes
# ---------------------------------------------------------------------------

_EMAIL_RE = re.compile(
    r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"
)
_PHONE_RE = re.compile(
    r"(?:\+?[\d\-\(\)\s]{7,16})"
)
_URL_RE = re.compile(
    r"(?:https?://|www\.)[^\s\)\]\,\"\']+"
    r"|(?:linkedin\.com|github\.com|gitlab\.com)[^\s\)\]\,\"\']*",
    re.I,
)
_GITHUB_RE = re.compile(r"github\.com/([A-Za-z0-9\-]+)", re.I)
_LINKEDIN_RE = re.compile(r"linkedin\.com/in/([A-Za-z0-9\-]+)", re.I)

# Date-range pattern: captures start–end inside experience/education blocks
_DATE_RANGE_RE = re.compile(
    r"((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s*\d{4}"
    r"|\d{1,2}/\d{4}|\d{4})"
    r"\s*(?:–|-|to)\s*"
    r"((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s*\d{4}"
    r"|\d{1,2}/\d{4}|\d{4}|[Pp]resent|[Cc]urrent|[Nn]ow)",
    re.I,
)
# Year-only range (e.g. 2018 – 2021)
_YEAR_RANGE_RE = re.compile(
    r"(\d{4})\s*(?:–|-|to)\s*(\d{4}|[Pp]resent|[Cc]urrent)",
    re.I,
)

# GPA pattern
_GPA_RE = re.compile(r"\bGPA[:\s]+(\d+\.\d+)", re.I)

# Headline heuristic: short line near top with a job-title-like form
_HEADLINE_INDICATORS = re.compile(
    r"\b(engineer|developer|scientist|analyst|manager|architect|designer|"
    r"consultant|specialist|lead|director|intern|researcher|officer)\b",
    re.I,
)


# ---------------------------------------------------------------------------
# Section segmentation
# ---------------------------------------------------------------------------

def _build_section_pattern() -> re.Pattern:
    """Build a compiled regex that matches any known section heading."""
    all_keywords = []
    for keywords in RESUME_SECTION_KEYWORDS.values():
        all_keywords.extend(keywords)
    escaped = [re.escape(k) for k in sorted(all_keywords, key=len, reverse=True)]
    pattern = r"(?im)^(?:" + "|".join(escaped) + r")\s*:?\s*$"
    return re.compile(pattern)


_SECTION_HEADING_RE = _build_section_pattern()


def _classify_heading(line: str) -> str | None:
    """Return the canonical section name if line is a known section heading."""
    normalized = line.strip().lower().rstrip(":")
    for section, keywords in RESUME_SECTION_KEYWORDS.items():
        if normalized in keywords:
            return section
    return None


def _segment_text(text: str) -> dict[str, str]:
    """
    Split raw resume text into named sections.

    Returns a dict: section_name → raw_text_block.
    A special "_header" key holds everything before the first section.
    """
    lines = text.splitlines()
    sections: dict[str, list[str]] = {"_header": []}
    current_section = "_header"

    for line in lines:
        stripped = line.strip()
        if not stripped:
            sections.setdefault(current_section, []).append("")
            continue
        classified = _classify_heading(stripped)
        if classified:
            current_section = classified
            sections.setdefault(current_section, [])
        else:
            sections.setdefault(current_section, []).append(line)

    return {k: "\n".join(v) for k, v in sections.items()}


# ---------------------------------------------------------------------------
# Field extractors
# ---------------------------------------------------------------------------

def _extract_emails(text: str) -> list[str]:
    found = _EMAIL_RE.findall(text)
    result = []
    for raw in found:
        n = normalize_email(raw)
        if n:
            result.append(n)
    return list(dict.fromkeys(result))


def _extract_phones(text: str) -> list[str]:
    found = _PHONE_RE.findall(text)
    result = []
    for raw in found:
        n = normalize_phone(raw.strip())
        if n:
            result.append(n)
    return list(dict.fromkeys(result))


def _extract_urls(text: str) -> list[dict[str, str]]:
    found = _URL_RE.findall(text)
    links: list[dict[str, str]] = []
    seen: set[str] = set()
    for raw in found:
        url = normalize_url(raw.strip("."))
        if not url or url in seen:
            continue
        seen.add(url)
        label = "Link"
        if "github.com" in url.lower():
            label = "GitHub"
        elif "linkedin.com" in url.lower():
            label = "LinkedIn"
        elif "gitlab.com" in url.lower():
            label = "GitLab"
        links.append({"url": url, "label": label})
    return links


def _extract_name_from_header(header: str) -> str | None:
    """
    Attempt to extract a name from the top few lines of the resume.
    Heuristic: the first non-empty line that contains only name-like characters
    and is not an email/URL/phone.
    """
    lines = [l.strip() for l in header.splitlines() if l.strip()]
    for line in lines[:6]:
        if _EMAIL_RE.search(line) or _URL_RE.search(line):
            continue
        if re.search(r"\d{5,}", line):  # zip codes, long numbers
            continue
        # A name: 2-5 words, letters/hyphens/apostrophes only
        words = line.split()
        if 2 <= len(words) <= 5 and all(re.match(r"^[A-Za-z\-\'\.]+$", w) for w in words):
            return normalize_name(line)
    return None


def _extract_headline_from_header(header: str, name: str | None) -> str | None:
    """
    Find a short role/title line near the top. Skip the name line itself.
    """
    lines = [l.strip() for l in header.splitlines() if l.strip()]
    for line in lines[:8]:
        if name and normalize_name(line) == name:
            continue
        if _EMAIL_RE.search(line) or _URL_RE.search(line) or _PHONE_RE.search(line):
            continue
        if _HEADLINE_INDICATORS.search(line) and len(line.split()) <= 10:
            return line
    return None


def _extract_location_from_header(header: str) -> str | None:
    """
    Look for a location-like line (City, State / City, Country pattern).
    """
    lines = [l.strip() for l in header.splitlines() if l.strip()]
    loc_re = re.compile(
        r"^[A-Za-z\s]+,\s*[A-Za-z\s]+$"
    )
    for line in lines[:10]:
        if _EMAIL_RE.search(line) or _URL_RE.search(line):
            continue
        if loc_re.match(line) and len(line.split()) <= 6:
            return normalize_location(line)
    return None


def _extract_skills_section(text: str) -> list[str]:
    """
    Parse a skills section: handles bullet lists, comma-separated, pipe-separated.
    """
    skill_names: list[str] = []
    # Split on bullets, pipes, commas, newlines
    tokens = re.split(r"[•\-|,\n\r]+", text)
    for token in tokens:
        t = token.strip()
        if t and 1 < len(t) < 40:
            # Skip date-like tokens
            if re.match(r"^\d{4}", t):
                continue
            skill_names.append(normalize_skill(t))
    return list(dict.fromkeys(s for s in skill_names if s))


def _parse_experience_blocks(text: str) -> list[dict[str, Any]]:
    """
    Parse experience section into structured entries.
    Strategy:
    1. Split on double-newlines to get blocks.
    2. Each block: first line = title/company, date range if present.
    3. Rest = description.
    """
    blocks = re.split(r"\n{2,}", text.strip())
    entries: list[dict[str, Any]] = []

    for block in blocks:
        block = block.strip()
        if not block or len(block) < 5:
            continue

        lines = [l.strip() for l in block.splitlines() if l.strip()]
        if not lines:
            continue

        entry: dict[str, Any] = {
            "title": None, "company": None,
            "start_date": None, "end_date": None,
            "description": None, "location": None,
        }

        # Try to find date range in the block
        date_match = _DATE_RANGE_RE.search(block) or _YEAR_RANGE_RE.search(block)
        if date_match:
            entry["start_date"] = normalize_date(date_match.group(1))
            end_raw = date_match.group(2)
            entry["end_date"] = ("Present" if re.match(r"present|current|now", end_raw, re.I)
                                 else normalize_date(end_raw))

        # First line: often "Title at Company" or "Title | Company" or "Title\nCompany"
        first_line = lines[0]
        at_match = re.split(r"\s+(?:at|@|–|-)\s+|\s*\|\s*", first_line, maxsplit=1)
        if len(at_match) == 2:
            entry["title"] = at_match[0].strip()
            entry["company"] = re.sub(r"\s*\d{4}.*", "", at_match[1]).strip()
        else:
            entry["title"] = first_line

        # Second line might be company if not already extracted
        if not entry["company"] and len(lines) > 1:
            second = lines[1]
            if not _DATE_RANGE_RE.search(second) and not _YEAR_RANGE_RE.search(second):
                entry["company"] = re.sub(r"\s*\d{4}.*", "", second).strip()

        # Remaining lines = description (skip date-only lines)
        desc_lines = []
        for line in lines[2:]:
            if _DATE_RANGE_RE.search(line) or _YEAR_RANGE_RE.search(line):
                continue
            if re.match(r"^\d{4}\s*[-–]\s*(?:\d{4}|[Pp]resent)", line):
                continue
            desc_lines.append(line)
        if desc_lines:
            entry["description"] = " ".join(desc_lines)

        if entry["title"] or entry["company"]:
            entries.append(entry)

    return entries


def _parse_education_blocks(text: str) -> list[dict[str, Any]]:
    """Parse education section into structured entries."""
    degree_re = re.compile(
        r"\b(B\.?Tech|B\.?E\.?|B\.?Sc\.?|B\.?S\.?|B\.?A\.?|"
        r"M\.?Tech|M\.?E\.?|M\.?Sc\.?|M\.?S\.?|M\.?A\.?|MBA|"
        r"Ph\.?D\.?|Doctor|Bachelor|Master|Associate|Diploma)\b",
        re.I,
    )

    blocks = re.split(r"\n{2,}", text.strip())
    entries: list[dict[str, Any]] = []

    for block in blocks:
        block = block.strip()
        if not block or len(block) < 5:
            continue

        lines = [l.strip() for l in block.splitlines() if l.strip()]
        if not lines:
            continue

        entry: dict[str, Any] = {
            "institution": None, "degree": None,
            "field_of_study": None,
            "start_date": None, "end_date": None, "gpa": None,
        }

        # Date range
        date_match = _DATE_RANGE_RE.search(block) or _YEAR_RANGE_RE.search(block)
        if date_match:
            entry["start_date"] = normalize_date(date_match.group(1))
            end_raw = date_match.group(2)
            entry["end_date"] = None if re.match(r"present|current|now", end_raw, re.I) \
                else normalize_date(end_raw)

        # GPA
        gpa_m = _GPA_RE.search(block)
        if gpa_m:
            try:
                entry["gpa"] = float(gpa_m.group(1))
            except ValueError:
                pass

        # Try to identify institution and degree from first 2 lines
        for line in lines[:3]:
            deg_m = degree_re.search(line)
            if deg_m and not entry["degree"]:
                entry["degree"] = deg_m.group(0)
                # Try to extract major from same line
                after = line[deg_m.end():].strip().lstrip("in").strip()
                if after and not re.match(r"^\d", after):
                    entry["field_of_study"] = after.split(",")[0].strip()
            elif not entry["institution"] and len(line.split()) >= 2:
                if not _DATE_RANGE_RE.search(line) and not _YEAR_RANGE_RE.search(line):
                    entry["institution"] = re.sub(r"\s*\d{4}.*", "", line).strip()

        if entry["institution"] or entry["degree"]:
            entries.append(entry)

    return entries


def _estimate_years_experience(experience: list[dict[str, Any]]) -> float | None:
    """
    Derive total years of experience from parsed experience entries.
    This is a DERIVED value – lower confidence than a stated value.
    """
    from datetime import date
    import calendar

    total_months = 0
    for exp in experience:
        start = exp.get("start_date")
        end = exp.get("end_date")
        if not start:
            continue
        try:
            sy, sm = int(start[:4]), int(start[5:7]) if len(start) > 4 else 1
            if end and end != "Present":
                ey, em = int(end[:4]), int(end[5:7]) if len(end) > 4 else 12
            else:
                ey, em = date.today().year, date.today().month
            months = (ey - sy) * 12 + (em - sm)
            if 0 < months < 600:  # sanity check
                total_months += months
        except (ValueError, IndexError):
            continue

    if total_months > 0:
        return round(total_months / 12, 1)
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_resume(path: str | Path) -> dict[str, Any]:
    """
    Parse a PDF resume into a canonical candidate dictionary.

    Parameters
    ----------
    path : str | Path
        Path to the PDF resume file.

    Returns
    -------
    dict[str, Any]
        Canonical intermediate dictionary ready for the merge engine.

    Raises
    ------
    ResumeParseError
        If the file cannot be opened or text cannot be extracted.
    """
    p = Path(path).resolve()
    if not p.exists():
        raise ResumeParseError(f"File not found", str(p))

    logger.info("Parsing resume PDF: %s", p)

    try:
        doc = fitz.open(str(p))
    except Exception as exc:
        raise ResumeParseError(f"Cannot open PDF: {exc}", str(p)) from exc

    if doc.is_encrypted:
        raise ResumeParseError("PDF is password-protected", str(p))

    try:
        pages_text: list[str] = []
        for page_num in range(len(doc)):
            try:
                page = doc.load_page(page_num)
                pages_text.append(page.get_text("text"))
            except Exception as exc:
                logger.warning("Could not extract text from page %d: %s", page_num + 1, exc)
        full_text = "\n".join(pages_text)
    finally:
        doc.close()

    if not full_text.strip():
        raise ResumeParseError(
            "No extractable text found – possibly a scanned/image PDF", str(p)
        )

    logger.debug("Extracted %d characters from resume", len(full_text))

    # ── Segment into sections ──────────────────────────────────────────────
    sections = _segment_text(full_text)
    header_text = sections.get("_header", full_text[:1500])

    # ── Identity fields ───────────────────────────────────────────────────
    full_name = _extract_name_from_header(header_text)
    headline = _extract_headline_from_header(header_text, full_name)
    location = _extract_location_from_header(header_text)

    # ── Contact info (scan full text for robustness) ──────────────────────
    emails = _extract_emails(full_text)
    phones = _extract_phones(full_text)
    links = _extract_urls(full_text)

    # ── Skills ───────────────────────────────────────────────────────────
    skills_text = sections.get("skills", "")
    # Also scan summary & projects for skill mentions if skills section is thin
    if len(skills_text.split()) < 5:
        skills_text += "\n" + sections.get("summary", "")
    skill_names = _extract_skills_section(skills_text)

    # ── Experience ────────────────────────────────────────────────────────
    experience_text = sections.get("experience", "")
    experience = _parse_experience_blocks(experience_text)

    # ── Education ─────────────────────────────────────────────────────────
    education_text = sections.get("education", "")
    education = _parse_education_blocks(education_text)

    # ── Years of experience ───────────────────────────────────────────────
    # First check summary/header for stated YOE, then derive from entries
    summary_text = sections.get("summary", "") + header_text
    yoe_match = re.search(
        r"(\d+\+?)\s*(?:years?|yrs?)\s*(?:of\s+)?(?:experience|exp)", summary_text, re.I
    )
    if yoe_match:
        years_experience = normalize_years_experience(yoe_match.group(1))
    else:
        years_experience = _estimate_years_experience(experience)

    # ── Candidate ID ──────────────────────────────────────────────────────
    seed = emails[0] if emails else full_name or ""
    candidate_id = generate_candidate_id(seed or None)

    canonical: dict[str, Any] = {
        "candidate_id": candidate_id,
        "full_name": full_name,
        "emails": emails,
        "phones": phones,
        "location": location,
        "headline": headline,
        "skills": skill_names,
        "links": links,
        "experience": experience,
        "education": education,
        "years_experience": years_experience,
        "_source": SOURCE_RESUME,
    }

    logger.info(
        "Resume: parsed name=%r emails=%r skills=%d experience=%d",
        full_name, emails, len(skill_names), len(experience),
    )
    return canonical
