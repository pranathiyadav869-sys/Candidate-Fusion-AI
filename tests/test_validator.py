"""
tests/test_validator.py
-----------------------
Tests for engine/validator.py — post-merge validation.
"""
import pytest
from engine.validator import validate_profile
from engine.schema import CandidateProfile, SkillEntry, ExperienceEntry, EducationEntry, SourceName


def make_profile(**kwargs) -> CandidateProfile:
    """Build a minimal valid CandidateProfile for testing."""
    defaults = dict(
        candidate_id="test-id-001",
        full_name="Alice Smith",
        emails=["alice@example.com"],
        phones=["+919876543210"],
        location="Hyderabad, India",
        years_experience=5.0,
        skills=[],
        experience=[],
        education=[],
        overall_confidence=0.85,
    )
    defaults.update(kwargs)
    return CandidateProfile(**defaults)


class TestValidateProfile:
    def test_valid_profile_passes_unchanged(self):
        profile = make_profile()
        validated = validate_profile(profile)
        assert validated.full_name == "Alice Smith"
        assert validated.emails == ["alice@example.com"]

    def test_missing_candidate_id_is_generated(self):
        profile = make_profile(candidate_id="")
        validated = validate_profile(profile)
        assert validated.candidate_id != ""
        assert len(validated.candidate_id) > 0

    def test_short_name_dropped(self):
        profile = make_profile(full_name="A")
        validated = validate_profile(profile)
        assert validated.full_name is None

    def test_invalid_email_dropped(self):
        profile = make_profile(emails=["good@example.com", "notanemail", "bad@@broken.com"])
        validated = validate_profile(profile)
        assert validated.emails == ["good@example.com"]

    def test_non_e164_phone_dropped(self):
        profile = make_profile(phones=["+919876543210", "not-a-phone"])
        validated = validate_profile(profile)
        assert "+919876543210" in validated.phones
        assert "not-a-phone" not in validated.phones

    def test_unrealistic_years_experience_dropped_high(self):
        profile = make_profile(years_experience=75.0)
        validated = validate_profile(profile)
        assert validated.years_experience is None

    def test_unrealistic_years_experience_dropped_negative(self):
        profile = make_profile(years_experience=-1.0)
        validated = validate_profile(profile)
        assert validated.years_experience is None

    def test_valid_years_experience_kept(self):
        profile = make_profile(years_experience=8.0)
        validated = validate_profile(profile)
        assert validated.years_experience == 8.0

    def test_skill_with_empty_canonical_name_dropped(self):
        profile = make_profile(skills=[
            SkillEntry(name="Python", canonical_name="Python", sources=[SourceName.ATS]),
            SkillEntry(name="",       canonical_name="",       sources=[SourceName.CSV]),
        ])
        validated = validate_profile(profile)
        assert len(validated.skills) == 1
        assert validated.skills[0].canonical_name == "Python"

    def test_experience_entry_without_company_and_title_dropped(self):
        profile = make_profile(experience=[
            ExperienceEntry(title="Engineer", company="Acme"),
            ExperienceEntry(title=None, company=None),
        ])
        validated = validate_profile(profile)
        assert len(validated.experience) == 1
        assert validated.experience[0].company == "Acme"

    def test_experience_with_only_title_kept(self):
        profile = make_profile(experience=[
            ExperienceEntry(title="Freelance Developer", company=None),
        ])
        validated = validate_profile(profile)
        assert len(validated.experience) == 1

    def test_education_without_institution_dropped(self):
        profile = make_profile(education=[
            EducationEntry(institution="IIT", degree="M.Tech"),
            EducationEntry(institution=None, degree="B.E."),
        ])
        validated = validate_profile(profile)
        assert len(validated.education) == 1
        assert validated.education[0].institution == "IIT"

    def test_confidence_clamped_above_1(self):
        profile = make_profile(overall_confidence=1.5)
        validated = validate_profile(profile)
        assert validated.overall_confidence == 1.0

    def test_confidence_clamped_below_0(self):
        profile = make_profile(overall_confidence=-0.5)
        validated = validate_profile(profile)
        assert validated.overall_confidence == 0.0

    def test_all_emails_invalid_results_in_empty_list(self):
        profile = make_profile(emails=["bad1", "bad2", "bad@@bad"])
        validated = validate_profile(profile)
        assert validated.emails == []

    def test_none_name_passes_without_error(self):
        profile = make_profile(full_name=None)
        validated = validate_profile(profile)
        assert validated.full_name is None
