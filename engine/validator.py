"""
engine/validator.py
-------------------
Post-merge validation layer. Validates the merged CandidateProfile and
applies any corrections. Never raises – invalid values are replaced with
None/empty, and validation warnings are logged.

Design Decision: Validation happens AFTER merge, not during parsing.
This means each parser can be lenient (accept anything parseable) while
the validator enforces the final contract. This separation keeps parsers
simple and the contract enforced in one place.
"""

from __future__ import annotations

import logging
import re
from typing import List

from engine.schema import CandidateProfile, SkillEntry

logger = logging.getLogger(__name__)


def validate_profile(profile: CandidateProfile) -> CandidateProfile:
    """
    Validate and sanitize a merged CandidateProfile.

    Rules enforced:
    - candidate_id must be a non-empty string
    - full_name: must be >= 2 characters if present
    - emails: each must match email regex; invalid ones dropped
    - phones: each must start with + for E.164; invalid ones dropped
    - years_experience: must be in [0, 60] if present
    - skills: must have non-empty canonical_name
    - experience: entries with no company AND no title are dropped
    - education: entries with no institution are dropped
    - overall_confidence: must be in [0.0, 1.0]

    Returns the (possibly modified) profile. Never raises.
    """
    warnings: List[str] = []

    # --- candidate_id ---
    if not profile.candidate_id:
        import uuid
        profile.candidate_id = str(uuid.uuid4())
        warnings.append("candidate_id was missing; generated new UUID")

    # --- full_name ---
    if profile.full_name is not None and len(profile.full_name.strip()) < 2:
        warnings.append(f"Dropping invalid full_name: {profile.full_name!r}")
        profile.full_name = None

    # --- emails ---
    email_re = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")
    valid_emails = []
    for email in profile.emails:
        if email and email_re.match(email):
            valid_emails.append(email)
        else:
            warnings.append(f"Dropping invalid email: {email!r}")
    profile.emails = valid_emails

    # --- phones ---
    valid_phones = []
    for phone in profile.phones:
        if phone and phone.startswith("+"):
            valid_phones.append(phone)
        else:
            warnings.append(f"Dropping non-E164 phone: {phone!r}")
    profile.phones = valid_phones

    # --- years_experience ---
    if profile.years_experience is not None:
        if not (0 <= profile.years_experience <= 60):
            warnings.append(
                f"Dropping unrealistic years_experience: {profile.years_experience}"
            )
            profile.years_experience = None

    # --- skills ---
    valid_skills = []
    for skill in profile.skills:
        if skill.canonical_name and skill.canonical_name.strip():
            valid_skills.append(skill)
        else:
            warnings.append(f"Dropping skill with empty canonical_name: {skill}")
    profile.skills = valid_skills

    # --- experience ---
    valid_exp = []
    for exp in profile.experience:
        if exp.company or exp.title:
            valid_exp.append(exp)
        else:
            warnings.append("Dropping experience entry with no company and no title")
    profile.experience = valid_exp

    # --- education ---
    valid_edu = []
    for edu in profile.education:
        if edu.institution:
            valid_edu.append(edu)
        else:
            warnings.append("Dropping education entry with no institution")
    profile.education = valid_edu

    # --- overall_confidence ---
    profile.overall_confidence = max(0.0, min(1.0, profile.overall_confidence))

    # Log all warnings
    for w in warnings:
        logger.warning("Validator: %s", w)

    return profile
