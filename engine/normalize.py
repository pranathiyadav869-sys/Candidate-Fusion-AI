"""
engine/normalize.py
-------------------
All normalization logic lives here. No parser or merge module is allowed
to do its own normalization – they all call into this module.

Design Decisions:
- phonenumbers library handles phone normalization reliably across locales.
- python-dateutil handles flexible date parsing before we force YYYY-MM.
- Skill canonicalization uses a curated alias map + lowercase fuzzy fallback.
- Email validation uses a lightweight regex before accepting.
"""

from __future__ import annotations

import re
import logging
from typing import Optional

import phonenumbers
from dateutil import parser as dateutil_parser

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Skill alias map: maps known variants → canonical form
# This is extensible; in production this would live in a DB or config file.
# ---------------------------------------------------------------------------

SKILL_ALIASES: dict[str, str] = {
    # AI / ML
    "ai": "Artificial Intelligence",
    "a.i.": "Artificial Intelligence",
    "artificial intelligence": "Artificial Intelligence",
    "ml": "Machine Learning",
    "machine learning": "Machine Learning",
    "deep learning": "Deep Learning",
    "dl": "Deep Learning",
    "nlp": "Natural Language Processing",
    "natural language processing": "Natural Language Processing",
    "cv": "Computer Vision",
    "computer vision": "Computer Vision",
    # Languages
    "python": "Python",
    "py": "Python",
    "javascript": "JavaScript",
    "js": "JavaScript",
    "typescript": "TypeScript",
    "ts": "TypeScript",
    "java": "Java",
    "c++": "C++",
    "cpp": "C++",
    "c#": "C#",
    "csharp": "C#",
    "golang": "Go",
    "go": "Go",
    "rust": "Rust",
    "ruby": "Ruby",
    "sql": "SQL",
    "nosql": "NoSQL",
    # Frameworks
    "react": "React",
    "reactjs": "React",
    "react.js": "React",
    "vue": "Vue.js",
    "vuejs": "Vue.js",
    "vue.js": "Vue.js",
    "angular": "Angular",
    "angularjs": "Angular",
    "node": "Node.js",
    "node.js": "Node.js",
    "nodejs": "Node.js",
    "django": "Django",
    "flask": "Flask",
    "fastapi": "FastAPI",
    "spring": "Spring",
    "spring boot": "Spring Boot",
    # Data
    "pandas": "Pandas",
    "numpy": "NumPy",
    "tensorflow": "TensorFlow",
    "tf": "TensorFlow",
    "pytorch": "PyTorch",
    "torch": "PyTorch",
    "scikit-learn": "scikit-learn",
    "sklearn": "scikit-learn",
    "scikit learn": "scikit-learn",
    # Cloud & DevOps
    "aws": "AWS",
    "amazon web services": "AWS",
    "gcp": "GCP",
    "google cloud": "GCP",
    "google cloud platform": "GCP",
    "azure": "Azure",
    "microsoft azure": "Azure",
    "docker": "Docker",
    "kubernetes": "Kubernetes",
    "k8s": "Kubernetes",
    "terraform": "Terraform",
    "ci/cd": "CI/CD",
    "cicd": "CI/CD",
    "git": "Git",
    "github": "GitHub",
    "gitlab": "GitLab",
    # Databases
    "postgresql": "PostgreSQL",
    "postgres": "PostgreSQL",
    "mysql": "MySQL",
    "mongodb": "MongoDB",
    "mongo": "MongoDB",
    "redis": "Redis",
    "elasticsearch": "Elasticsearch",
    # Other
    "rest api": "REST API",
    "restapi": "REST API",
    "rest": "REST API",
    "graphql": "GraphQL",
    "microservices": "Microservices",
    "agile": "Agile",
    "scrum": "Scrum",
}


# ---------------------------------------------------------------------------
# Phone normalization
# ---------------------------------------------------------------------------

def normalize_phone(raw: str, default_region: str = "IN") -> Optional[str]:
    """
    Attempt to parse raw phone string and return E.164 format.
    Returns None if the number cannot be parsed or is invalid.

    Design note: We default to IN (India) region since the recruiter base
    is Hyderabad-centric, but this is configurable.
    """
    if not raw or not raw.strip():
        return None
    try:
        # Remove common non-numeric noise but keep + for country codes
        cleaned = re.sub(r"[^\d+\-\(\)\s]", "", raw).strip()
        parsed = phonenumbers.parse(cleaned, default_region)
        if phonenumbers.is_valid_number(parsed):
            return phonenumbers.format_number(
                parsed, phonenumbers.PhoneNumberFormat.E164
            )
        return None
    except Exception:
        logger.debug("Could not normalize phone: %s", raw)
        return None


# ---------------------------------------------------------------------------
# Email normalization
# ---------------------------------------------------------------------------

_EMAIL_RE = re.compile(
    r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"
)


def normalize_email(raw: str) -> Optional[str]:
    """
    Lowercase, strip, and validate. Returns None if invalid.
    """
    if not raw:
        return None
    cleaned = raw.strip().lower()
    if _EMAIL_RE.match(cleaned):
        return cleaned
    logger.debug("Rejected invalid email: %s", raw)
    return None


# ---------------------------------------------------------------------------
# Date normalization
# ---------------------------------------------------------------------------

_PRESENT_RE = re.compile(r"^(present|current|now|ongoing|—|-+)$", re.I)


def normalize_date(raw: str | None) -> Optional[str]:
    """
    Parse a date string in any reasonable format and return YYYY-MM.
    Returns 'Present' if the raw value means present.
    Returns None if unparseable.
    """
    if not raw:
        return None
    stripped = raw.strip()
    if _PRESENT_RE.match(stripped):
        return "Present"
    # Handle year-only like "2019"
    if re.match(r"^\d{4}$", stripped):
        return f"{stripped}-01"
    # Handle "MM/YYYY" or "YYYY/MM"
    m = re.match(r"^(\d{1,2})/(\d{4})$", stripped)
    if m:
        return f"{m.group(2)}-{int(m.group(1)):02d}"
    m = re.match(r"^(\d{4})/(\d{1,2})$", stripped)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}"
    try:
        dt = dateutil_parser.parse(stripped, default=dateutil_parser.parse("2000-01-01"))
        return dt.strftime("%Y-%m")
    except Exception:
        logger.debug("Could not parse date: %s", raw)
        return None


# ---------------------------------------------------------------------------
# Name normalization
# ---------------------------------------------------------------------------

def normalize_name(raw: str | None) -> Optional[str]:
    """
    Title-case, strip extra whitespace, remove non-name characters.
    """
    if not raw:
        return None
    # Remove digits and most punctuation except hyphens and apostrophes
    cleaned = re.sub(r"[^a-zA-Z\s\-\']", "", raw)
    # Collapse whitespace
    cleaned = " ".join(cleaned.split())
    return cleaned.title() if cleaned else None


# ---------------------------------------------------------------------------
# Skill normalization
# ---------------------------------------------------------------------------

def normalize_skill(raw: str) -> str:
    """
    Map a raw skill string to its canonical form.
    Falls back to Title Case if no alias is found.
    """
    key = raw.strip().lower()
    return SKILL_ALIASES.get(key, raw.strip().title())


def normalize_skills_list(raw_skills: list[str]) -> list[str]:
    """
    Deduplicate and canonicalize a list of raw skills.
    """
    seen: set[str] = set()
    result: list[str] = []
    for skill in raw_skills:
        canonical = normalize_skill(skill)
        if canonical.lower() not in seen:
            seen.add(canonical.lower())
            result.append(canonical)
    return result


# ---------------------------------------------------------------------------
# Location normalization
# ---------------------------------------------------------------------------

_LOCATION_ABBREV: dict[str, str] = {
    "sf": "San Francisco, CA",
    "nyc": "New York, NY",
    "la": "Los Angeles, CA",
    "dc": "Washington, DC",
    "blr": "Bengaluru, India",
    "bangalore": "Bengaluru, India",
    "bombay": "Mumbai, India",
    "hyd": "Hyderabad, India",
    "pune": "Pune, India",
    "chn": "Chennai, India",
    "madras": "Chennai, India",
}


def normalize_location(raw: str | None) -> Optional[str]:
    """
    Standardize location strings. Expand known abbreviations.
    Otherwise Title-Case and strip.
    """
    if not raw:
        return None
    stripped = raw.strip()
    lower = stripped.lower()
    if lower in _LOCATION_ABBREV:
        return _LOCATION_ABBREV[lower]
    # Title-case comma-separated parts
    parts = [p.strip().title() for p in stripped.split(",")]
    return ", ".join(parts) if parts else None


# ---------------------------------------------------------------------------
# URL normalization
# ---------------------------------------------------------------------------

def normalize_url(raw: str | None) -> Optional[str]:
    """
    Ensure the URL has a scheme. Return None if clearly invalid.
    """
    if not raw:
        return None
    url = raw.strip()
    if url.startswith("http://") or url.startswith("https://"):
        return url
    if url.startswith("www.") or "." in url:
        return f"https://{url}"
    return None


# ---------------------------------------------------------------------------
# Years of experience normalization
# ---------------------------------------------------------------------------

def normalize_years_experience(raw: str | int | float | None) -> Optional[float]:
    """
    Convert various representations of years of experience to a float.
    Handles strings like "5 years", "5+", "3-5", "~4".
    """
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    text = str(raw).strip().lower()
    # Extract first number encountered
    numbers = re.findall(r"\d+(?:\.\d+)?", text)
    if not numbers:
        return None
    # If range like "3-5", take average
    if len(numbers) >= 2:
        return (float(numbers[0]) + float(numbers[1])) / 2
    return float(numbers[0])
