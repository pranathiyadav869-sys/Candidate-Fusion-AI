"""
engine/schema.py
----------------
Canonical Pydantic schema for the unified candidate profile.

Design Decision: Pydantic v2 is used throughout for runtime validation,
serialization, and clear error messages. Every field is Optional so
partial data from any single source never causes a crash. The schema is
the single source of truth – parsers, merge, and projector all reference it.
"""

from __future__ import annotations
from pydantic import PrivateAttr
from datetime import date
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, EmailStr, field_validator, model_validator


# ---------------------------------------------------------------------------
# Supporting enums & sub-models
# ---------------------------------------------------------------------------

class SourceName(str, Enum):
    CSV = "csv"
    ATS = "ats"
    RESUME = "resume"
    GITHUB = "github"
    DERIVED = "derived"


class ProvenanceEntry(BaseModel):
    """Tracks exactly where a value came from."""
    source: SourceName
    method: str                    # e.g. "regex", "api", "direct_field"
    raw_value: Optional[str] = None
    confidence: float = 0.0        # 0.0 – 1.0


class FieldProvenance(BaseModel):
    """Per-field provenance: which sources supplied values and which won."""
    selected_source: Optional[SourceName] = None
    entries: List[ProvenanceEntry] = []
    confidence: float = 0.0


class ExperienceEntry(BaseModel):
    title: Optional[str] = None
    company: Optional[str] = None
    start_date: Optional[str] = None   # YYYY-MM
    end_date: Optional[str] = None     # YYYY-MM or "Present"
    description: Optional[str] = None
    location: Optional[str] = None


class EducationEntry(BaseModel):
    institution: Optional[str] = None
    degree: Optional[str] = None
    field_of_study: Optional[str] = None
    start_date: Optional[str] = None   # YYYY-MM
    end_date: Optional[str] = None     # YYYY-MM
    gpa: Optional[float] = None


class SkillEntry(BaseModel):
    name: str
    canonical_name: str            # normalized form
    sources: List[SourceName] = []
    confidence: float = 0.0


class LinkEntry(BaseModel):
    url: str
    label: Optional[str] = None    # "GitHub", "Portfolio", etc.


# ---------------------------------------------------------------------------
# Top-level canonical candidate profile
# ---------------------------------------------------------------------------

class CandidateProfile(BaseModel):
    """
    The unified, validated, canonical candidate record produced by the pipeline.

    Every field that touches the outside world is Optional so that a missing
    value is represented as null in the output rather than causing a crash.
    """

    # Identity
    candidate_id: str
    full_name: Optional[str] = None
    emails: List[str] = []
    phones: List[str] = []          # E.164 format
    location: Optional[str] = None
    links: List[LinkEntry] = []
    headline: Optional[str] = None

    # Professional summary
    years_experience: Optional[float] = None
    skills: List[SkillEntry] = []
    experience: List[ExperienceEntry] = []
    education: List[EducationEntry] = []

    # Pipeline metadata
    provenance: Dict[str, FieldProvenance] = {}
    overall_confidence: float = 0.0
    
    # Internal: raw per-source data (stripped before final output if configured)
    _source_data: Dict[str, Any] = PrivateAttr(default_factory=dict)

    @field_validator("emails", mode="before")
    @classmethod
    def deduplicate_emails(cls, v):
        seen = set()
        result = []
        for email in (v or []):
            lower = email.lower().strip()
            if lower not in seen:
                seen.add(lower)
                result.append(lower)
        return result

    @field_validator("phones", mode="before")
    @classmethod
    def deduplicate_phones(cls, v):
        seen = set()
        result = []
        for phone in (v or []):
            if phone not in seen:
                seen.add(phone)
                result.append(phone)
        return result

    @field_validator("overall_confidence", mode="before")
    @classmethod
    def clamp_confidence(cls, v):
        return max(0.0, min(1.0, float(v or 0.0)))

    def to_output_dict(self, config: dict | None = None) -> dict:
        """
        Serialize to dict, applying optional config projection rules.
        Config keys: hide_provenance, hide_confidence, field_aliases,
                     exclude_fields.
        """
        data = self.model_dump(mode="json", exclude_none=False)
        if config is None:
            return data
        if config.get("hide_provenance"):
            data.pop("provenance", None)
        if config.get("hide_confidence"):
            data.pop("overall_confidence", None)
            for skill in data.get("skills", []):
                skill.pop("confidence", None)
        for old_name, new_name in config.get("field_aliases", {}).items():
            if old_name in data:
                data[new_name] = data.pop(old_name)
        for field in config.get("exclude_fields", []):
            data.pop(field, None)
        return data
