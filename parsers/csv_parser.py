"""
parsers/csv_parser.py
---------------------
Parses recruiter-supplied CSV files into a canonical intermediate dictionary.

Design Decisions:
- Column aliasing via CSV_COLUMN_ALIASES handles the wild inconsistency of
  recruiter spreadsheets (e.g. "Candidate Name", "name", "full_name" all map
  to "full_name").
- Malformed rows are skipped with a warning rather than crashing the pipeline.
- Multi-value fields (emails, phones, skills) support semicolon, pipe, and
  comma delimiters within a cell.
- Returns a list of raw dicts; the merge engine handles deduplication.
"""

from __future__ import annotations

import csv
import io
import logging
from pathlib import Path
from typing import Any

from engine.normalize import (
    normalize_email,
    normalize_location,
    normalize_name,
    normalize_phone,
    normalize_skill,
    normalize_url,
    normalize_years_experience,
)
from utils.constants import CSV_COLUMN_ALIASES, SOURCE_CSV
from utils.exceptions import CSVParseError
from utils.helpers import coerce_str, generate_candidate_id, split_multi_value

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _normalize_header(raw: str) -> str:
    """Strip and lowercase a CSV column header for alias lookup."""
    return raw.strip().lower().replace("-", "_")


def _map_columns(headers: list[str]) -> dict[str, str]:
    """
    Build a mapping: original_header → canonical_field_name.
    Unknown headers are kept as-is.
    """
    mapping: dict[str, str] = {}
    for h in headers:
        normalized = _normalize_header(h)
        canonical = CSV_COLUMN_ALIASES.get(normalized, normalized)
        mapping[h] = canonical
        if canonical != normalized:
            logger.debug("CSV column alias: %r → %r", h, canonical)
    return mapping


def _parse_row(
    row: dict[str, str],
    col_map: dict[str, str],
    row_num: int,
) -> dict[str, Any] | None:
    """
    Parse one CSV row dict into a canonical intermediate dict.
    Returns None if the row is entirely empty.
    """
    canonical: dict[str, Any] = {}

    # Remap all column keys to their canonical equivalents
    remapped: dict[str, str] = {}
    for orig_key, value in row.items():
        canon_key = col_map.get(orig_key, _normalize_header(orig_key))
        remapped[canon_key] = coerce_str(value) or ""

    # Bail on entirely empty rows
    if all(v == "" for v in remapped.values()):
        logger.debug("Skipping empty row %d", row_num)
        return None

    # ── candidate_id ──────────────────────────────────────────────────────
    raw_id = remapped.get("candidate_id", "")
    canonical["candidate_id"] = raw_id if raw_id else None  # resolved later

    # ── full_name ─────────────────────────────────────────────────────────
    raw_name = remapped.get("full_name", "")
    canonical["full_name"] = normalize_name(raw_name) if raw_name else None

    # ── emails ────────────────────────────────────────────────────────────
    raw_email = remapped.get("emails", "")
    emails: list[str] = []
    for e in split_multi_value(raw_email, r"[;|,\s]+"):
        normalized_email = normalize_email(e)
        if normalized_email:
            emails.append(normalized_email)
        else:
            logger.warning("Row %d: invalid email skipped: %r", row_num, e)
    canonical["emails"] = emails

    # ── phones ────────────────────────────────────────────────────────────
    raw_phone = remapped.get("phones", "")
    phones: list[str] = []
    for p in split_multi_value(raw_phone, r"[;|]"):
        normalized_phone = normalize_phone(p)
        if normalized_phone:
            phones.append(normalized_phone)
        else:
            logger.warning("Row %d: invalid phone skipped: %r", row_num, p)
    canonical["phones"] = phones

    # ── location ──────────────────────────────────────────────────────────
    raw_loc = remapped.get("location", "")
    canonical["location"] = normalize_location(raw_loc) if raw_loc else None

    # ── skills ────────────────────────────────────────────────────────────
    raw_skills = remapped.get("skills", "")
    skill_names: list[str] = []
    for s in split_multi_value(raw_skills, r"[;|,]"):
        if s:
            skill_names.append(normalize_skill(s))
    canonical["skills"] = list(dict.fromkeys(skill_names))  # preserve order, dedup

    # ── years_experience ──────────────────────────────────────────────────
    raw_yoe = remapped.get("years_experience", "")
    canonical["years_experience"] = normalize_years_experience(raw_yoe) if raw_yoe else None

    # ── headline ──────────────────────────────────────────────────────────
    raw_headline = remapped.get("headline", "")
    canonical["headline"] = raw_headline.strip() if raw_headline else None

    # ── links ─────────────────────────────────────────────────────────────
    links: list[dict[str, str]] = []
    for label, key in [("LinkedIn", "linkedin"), ("GitHub", "github_url"), ("Portfolio", "portfolio")]:
        raw_url = remapped.get(key, "")
        normalized_url = normalize_url(raw_url) if raw_url else None
        if normalized_url:
            links.append({"url": normalized_url, "label": label})
    canonical["links"] = links

    # ── source tag ────────────────────────────────────────────────────────
    canonical["_source"] = SOURCE_CSV

    logger.debug("Row %d parsed: name=%r emails=%r", row_num, canonical["full_name"], canonical["emails"])
    return canonical


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def parse_csv(path: str | Path) -> list[dict[str, Any]]:
    """
    Parse a recruiter CSV file into a list of canonical candidate dicts.

    Each returned dict represents one row and contains normalized values
    ready to be consumed by the merge engine.

    Parameters
    ----------
    path : str | Path
        Path to the CSV file.

    Returns
    -------
    list[dict[str, Any]]
        List of parsed candidate dicts. Empty list on unrecoverable errors.

    Raises
    ------
    CSVParseError
        If the file cannot be opened or has no usable headers.
    """
    p = Path(path).resolve()
    if not p.exists():
        raise CSVParseError(f"File not found: {p}")

    logger.info("Parsing CSV: %s", p)

    try:
        raw_text = p.read_text(encoding="utf-8-sig")  # strip BOM if present
    except UnicodeDecodeError:
        # Fallback to latin-1 for legacy spreadsheet exports
        raw_text = p.read_text(encoding="latin-1")
        logger.warning("CSV file %s decoded with latin-1 fallback", p)

    reader = csv.DictReader(io.StringIO(raw_text))

    if reader.fieldnames is None or len(reader.fieldnames) == 0:
        raise CSVParseError(f"No column headers found in: {p}")

    col_map = _map_columns(list(reader.fieldnames))
    logger.debug("CSV columns detected: %s", list(reader.fieldnames))

    results: list[dict[str, Any]] = []
    for row_num, row in enumerate(reader, start=2):  # 2 = first data row (row 1 is header)
        try:
            parsed = _parse_row(dict(row), col_map, row_num)
            if parsed is None:
                continue

            # Assign candidate_id if not in CSV
            if not parsed.get("candidate_id"):
                seed = (parsed.get("emails") or [""])[0] or parsed.get("full_name") or ""
                parsed["candidate_id"] = generate_candidate_id(seed or None)

            results.append(parsed)
        except Exception as exc:
            logger.warning("Skipping malformed CSV row %d: %s", row_num, exc)
            continue

    logger.info("CSV: parsed %d candidate row(s) from %s", len(results), p.name)
    return results
