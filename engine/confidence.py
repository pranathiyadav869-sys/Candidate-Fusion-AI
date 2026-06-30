"""
engine/confidence.py
--------------------
Confidence scoring for every field and the overall candidate record.

Design Philosophy:
- Source baseline scores reflect empirical data quality: resumes are
  human-crafted for accuracy; ATS is validated at submission; CSV may
  have typos; GitHub is factual but limited in scope.
- Field quality modifiers adjust the score up or down based on whether
  the value looks complete and well-formed.
- Cross-source agreement bumps the score: if three sources agree on an
  email, we're more confident than if only one reports it.
- Scores are clamped to [0.0, 1.0].
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from engine.schema import SourceName

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Source baseline confidence scores
# ---------------------------------------------------------------------------

SOURCE_BASELINE: Dict[SourceName, float] = {
    SourceName.RESUME: 0.92,
    SourceName.ATS: 0.90,
    SourceName.CSV: 0.80,
    SourceName.GITHUB: 0.86,
}

# ---------------------------------------------------------------------------
# Field quality modifiers
# ---------------------------------------------------------------------------
# These are additive adjustments on top of the baseline.

FIELD_QUALITY_RULES: Dict[str, List[tuple]] = {
    # field_name → list of (condition_fn, delta)
    "full_name": [
        (lambda v: v and len(v.split()) >= 2, +0.05),   # Has first & last
        (lambda v: v and len(v) > 30, -0.05),            # Suspiciously long
    ],
    "emails": [
        (lambda v: v and len(v) > 0, +0.03),
        (lambda v: v and len(v) > 3, -0.05),             # Too many emails = suspicious
    ],
    "phones": [
        (lambda v: v and len(v) > 0, +0.02),
    ],
    "location": [
        (lambda v: v and "," in v, +0.03),               # City, Country format
    ],
    "years_experience": [
        (lambda v: v is not None and 0 < v < 50, +0.03),
        (lambda v: v is not None and v > 40, -0.10),     # Unrealistic
    ],
    "skills": [
        (lambda v: v and len(v) >= 3, +0.03),
        (lambda v: v and len(v) >= 10, +0.02),
    ],
}


def _apply_quality_rules(field_name: str, value: Any) -> float:
    """Return total delta from quality rules for this field."""
    rules = FIELD_QUALITY_RULES.get(field_name, [])
    delta = 0.0
    for condition, adjustment in rules:
        try:
            if condition(value):
                delta += adjustment
        except Exception:
            pass
    return delta


def compute_field_confidence(
    field_name: str,
    value: Any,
    source: SourceName,
    agreeing_sources: int = 1,
) -> float:
    """
    Compute confidence for a single field value from a specific source.

    Parameters
    ----------
    field_name      : canonical field name
    value           : the value being scored
    source          : which source provided this value
    agreeing_sources: number of sources that agree on this value
    """
    if value is None or value == [] or value == "":
        return 0.0

    baseline = SOURCE_BASELINE.get(source, 0.70)
    quality_delta = _apply_quality_rules(field_name, value)

    # Cross-source agreement bonus: each additional source adds 2%
    agreement_bonus = (agreeing_sources - 1) * 0.02

    score = baseline + quality_delta + agreement_bonus
    return round(max(0.0, min(1.0, score)), 4)


def compute_overall_confidence(
    field_confidences: Dict[str, float],
    sources_present: List[SourceName],
) -> float:
    """
    Compute overall candidate profile confidence.

    Algorithm:
    1. Weighted average of key field confidences.
    2. Bonus for multiple sources present.
    3. Penalty if critical fields (name, email) are missing.
    """
    # Key fields and their importance weights
    key_fields = {
        "full_name": 0.20,
        "emails": 0.20,
        "phones": 0.10,
        "location": 0.05,
        "skills": 0.15,
        "experience": 0.15,
        "education": 0.10,
        "years_experience": 0.05,
    }

    weighted_sum = 0.0
    weight_total = 0.0
    for field, weight in key_fields.items():
        conf = field_confidences.get(field, 0.0)
        weighted_sum += conf * weight
        weight_total += weight

    base_score = weighted_sum / weight_total if weight_total > 0 else 0.0

    # Multi-source bonus
    source_bonus = min((len(sources_present) - 1) * 0.015, 0.05)

    # Critical field penalties
    penalty = 0.0
    if not field_confidences.get("full_name"):
        penalty += 0.10
    if not field_confidences.get("emails"):
        penalty += 0.08

    score = base_score + source_bonus - penalty
    return round(max(0.0, min(1.0, score)), 4)
