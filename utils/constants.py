"""
utils/constants.py
------------------
Project-wide constants for CandidateFusion.

Design Decision: All magic strings, numeric thresholds, and default paths
live here so they can be changed in one place without hunting through code.
"""

from __future__ import annotations

from pathlib import Path

# ─────────────────────────────────────────────────────────────────────────────
# Project root
# ─────────────────────────────────────────────────────────────────────────────

PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent

# ─────────────────────────────────────────────────────────────────────────────
# Config file paths
# ─────────────────────────────────────────────────────────────────────────────

CONFIG_DIR: Path = PROJECT_ROOT / "config"
CONFIDENCE_CONFIG_PATH: Path = CONFIG_DIR / "confidence.json"
PROJECTION_CONFIG_PATH: Path = CONFIG_DIR / "projection.json"
SKILLS_CONFIG_PATH: Path = CONFIG_DIR / "skills.json"

# ─────────────────────────────────────────────────────────────────────────────
# Default output paths
# ─────────────────────────────────────────────────────────────────────────────

DEFAULT_OUTPUT_DIR: Path = PROJECT_ROOT
DEFAULT_CANDIDATE_JSON: str = "candidate.json"
DEFAULT_PIPELINE_REPORT: str = "pipeline_report.json"

# ─────────────────────────────────────────────────────────────────────────────
# Pipeline source identifiers (mirror SourceName enum values)
# ─────────────────────────────────────────────────────────────────────────────

SOURCE_CSV: str = "csv"
SOURCE_ATS: str = "ats"
SOURCE_RESUME: str = "resume"
SOURCE_GITHUB: str = "github"
SOURCE_DERIVED: str = "derived"

# ─────────────────────────────────────────────────────────────────────────────
# GitHub API
# ─────────────────────────────────────────────────────────────────────────────

GITHUB_API_BASE_URL: str = "https://api.github.com"
GITHUB_MAX_REPOS: int = 30          # Max repos fetched per user
GITHUB_MAX_LANGUAGES: int = 10      # Max languages collected

# ─────────────────────────────────────────────────────────────────────────────
# PDF / Resume parsing
# ─────────────────────────────────────────────────────────────────────────────

# Section heading keywords (case-insensitive) for resume segmentation
RESUME_SECTION_KEYWORDS: dict[str, list[str]] = {
    "experience": [
        "experience", "work experience", "professional experience",
        "employment", "employment history", "work history", "career history",
    ],
    "education": [
        "education", "academic background", "qualifications",
        "academic qualifications", "educational background",
    ],
    "skills": [
        "skills", "technical skills", "core competencies",
        "competencies", "technologies", "tools", "stack",
    ],
    "projects": [
        "projects", "personal projects", "open source", "side projects",
    ],
    "summary": [
        "summary", "profile", "objective", "about me",
        "professional summary", "career objective",
    ],
    "links": [
        "links", "social", "online profiles", "portfolio",
    ],
}

# ─────────────────────────────────────────────────────────────────────────────
# CSV parser
# ─────────────────────────────────────────────────────────────────────────────

# Column name aliases: maps known variants to the canonical internal name
CSV_COLUMN_ALIASES: dict[str, str] = {
    # name
    "name": "full_name",
    "full name": "full_name",
    "candidate name": "full_name",
    "candidate_name": "full_name",
    "applicant_name": "full_name",
    "applicant name": "full_name",
    # email
    "email": "emails",
    "email address": "emails",
    "email_address": "emails",
    "e-mail": "emails",
    # phone
    "phone": "phones",
    "phone number": "phones",
    "phone_number": "phones",
    "mobile": "phones",
    "mobile number": "phones",
    "cell": "phones",
    # location
    "location": "location",
    "city": "location",
    "address": "location",
    "city/state": "location",
    # skills
    "skills": "skills",
    "skill set": "skills",
    "skillset": "skills",
    "technical skills": "skills",
    # experience
    "years_experience": "years_experience",
    "years experience": "years_experience",
    "experience": "years_experience",
    "yoe": "years_experience",
    # links
    "linkedin": "linkedin",
    "github": "github_url",
    "github url": "github_url",
    "portfolio": "portfolio",
    "website": "portfolio",
    # headline
    "headline": "headline",
    "title": "headline",
    "job title": "headline",
    "current title": "headline",
    # candidate id
    "id": "candidate_id",
    "candidate_id": "candidate_id",
    "applicant_id": "candidate_id",
}

# ─────────────────────────────────────────────────────────────────────────────
# Validation thresholds
# ─────────────────────────────────────────────────────────────────────────────

MAX_YEARS_EXPERIENCE: float = 60.0
MIN_YEARS_EXPERIENCE: float = 0.0
MIN_NAME_LENGTH: int = 2
MAX_EMAILS_PER_CANDIDATE: int = 5
MAX_PHONES_PER_CANDIDATE: int = 5

# ─────────────────────────────────────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────────────────────────────────────

LOG_FORMAT: str = "%(asctime)s [%(levelname)s] %(name)s – %(message)s"
LOG_DATE_FORMAT: str = "%Y-%m-%d %H:%M:%S"
DEFAULT_LOG_LEVEL: str = "INFO"
LOG_FILE: str = "candidatefusion.log"

# ─────────────────────────────────────────────────────────────────────────────
# Merge priority (higher = preferred source for conflicts)
# ─────────────────────────────────────────────────────────────────────────────

SOURCE_PRIORITY: dict[str, int] = {
    SOURCE_RESUME:  4,
    SOURCE_ATS:     3,
    SOURCE_GITHUB:  2,
    SOURCE_CSV:     1,
    SOURCE_DERIVED: 0,
}
