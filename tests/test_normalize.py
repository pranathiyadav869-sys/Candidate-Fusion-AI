"""
tests/test_normalize.py
-----------------------
Unit tests for engine/normalize.py — all normalization functions.
"""
import pytest
from engine.normalize import (
    normalize_email,
    normalize_phone,
    normalize_name,
    normalize_skill,
    normalize_skills_list,
    normalize_location,
    normalize_url,
    normalize_date,
    normalize_years_experience,
)


# ─────────────────────────────────────────────────────────────────────────────
# Email
# ─────────────────────────────────────────────────────────────────────────────
class TestNormalizeEmail:
    def test_valid_lowercase(self):
        assert normalize_email("alice@example.com") == "alice@example.com"

    def test_uppercase_lowercased(self):
        assert normalize_email("ALICE@EXAMPLE.COM") == "alice@example.com"

    def test_strips_whitespace(self):
        assert normalize_email("  alice@example.com  ") == "alice@example.com"

    def test_invalid_no_at(self):
        assert normalize_email("aliceexample.com") is None

    def test_invalid_double_at(self):
        assert normalize_email("alice@@example.com") is None

    def test_invalid_empty(self):
        assert normalize_email("") is None

    def test_invalid_none(self):
        assert normalize_email(None) is None

    def test_plus_addressing(self):
        assert normalize_email("alice+tag@example.com") == "alice+tag@example.com"

    def test_subdomain(self):
        assert normalize_email("user@mail.company.co.uk") == "user@mail.company.co.uk"

    def test_missing_tld(self):
        assert normalize_email("alice@example") is None


# ─────────────────────────────────────────────────────────────────────────────
# Phone
# ─────────────────────────────────────────────────────────────────────────────
class TestNormalizePhone:
    def test_indian_mobile_with_plus(self):
        result = normalize_phone("+91-9876543210")
        assert result == "+919876543210"

    def test_indian_mobile_no_prefix(self):
        # Default region IN should handle this
        result = normalize_phone("9876543210", default_region="IN")
        assert result == "+919876543210"

    def test_invalid_too_short(self):
        assert normalize_phone("123") is None

    def test_empty(self):
        assert normalize_phone("") is None

    def test_none(self):
        assert normalize_phone(None) is None

    def test_us_number(self):
        result = normalize_phone("+1-415-555-1234", default_region="US")
        assert result == "+14155551234"

    def test_garbage_string(self):
        assert normalize_phone("not-a-phone-number-xyz") is None

    def test_all_zeros(self):
        assert normalize_phone("0000000000000000000") is None


# ─────────────────────────────────────────────────────────────────────────────
# Name
# ─────────────────────────────────────────────────────────────────────────────
class TestNormalizeName:
    def test_title_case(self):
        assert normalize_name("alice smith") == "Alice Smith"

    def test_strips_numbers(self):
        assert normalize_name("Alice 123 Smith") == "Alice  Smith"

    def test_none(self):
        assert normalize_name(None) is None

    def test_empty(self):
        assert normalize_name("") is None

    def test_hyphenated(self):
        assert normalize_name("mary-jane watson") == "Mary-Jane Watson"

    def test_uppercase_normalised(self):
        assert normalize_name("PRIYA SHARMA") == "Priya Sharma"

    def test_extra_whitespace_collapsed(self):
        result = normalize_name("  Priya   Sharma  ")
        assert result == "Priya Sharma"


# ─────────────────────────────────────────────────────────────────────────────
# Skill
# ─────────────────────────────────────────────────────────────────────────────
class TestNormalizeSkill:
    def test_known_alias_python(self):
        assert normalize_skill("python") == "Python"

    def test_known_alias_js(self):
        assert normalize_skill("js") == "JavaScript"

    def test_known_alias_k8s(self):
        assert normalize_skill("k8s") == "Kubernetes"

    def test_known_alias_reactjs(self):
        assert normalize_skill("reactjs") == "React"

    def test_unknown_skill_title_cased(self):
        result = normalize_skill("some obscure tool")
        assert result == "Some Obscure Tool"

    def test_case_insensitive_lookup(self):
        assert normalize_skill("PYTHON") == "Python"
        assert normalize_skill("PyThOn") == "Python"

    def test_ml_alias(self):
        assert normalize_skill("ml") == "Machine Learning"

    def test_nlp_alias(self):
        assert normalize_skill("nlp") == "Natural Language Processing"


class TestNormalizeSkillsList:
    def test_deduplication(self):
        result = normalize_skills_list(["python", "Python", "py"])
        assert result.count("Python") == 1

    def test_empty_list(self):
        assert normalize_skills_list([]) == []

    def test_preserves_unique_skills(self):
        result = normalize_skills_list(["python", "docker", "aws"])
        assert len(result) == 3


# ─────────────────────────────────────────────────────────────────────────────
# Location
# ─────────────────────────────────────────────────────────────────────────────
class TestNormalizeLocation:
    def test_known_abbreviation_hyd(self):
        assert normalize_location("hyd") == "Hyderabad, India"

    def test_known_abbreviation_blr(self):
        assert normalize_location("blr") == "Bengaluru, India"

    def test_none(self):
        assert normalize_location(None) is None

    def test_title_case_applied(self):
        result = normalize_location("new york, usa")
        assert result == "New York, Usa"

    def test_comma_parts_preserved(self):
        result = normalize_location("Hyderabad, Telangana")
        assert "Hyderabad" in result and "Telangana" in result


# ─────────────────────────────────────────────────────────────────────────────
# URL
# ─────────────────────────────────────────────────────────────────────────────
class TestNormalizeUrl:
    def test_already_https(self):
        assert normalize_url("https://github.com/user") == "https://github.com/user"

    def test_adds_https_for_www(self):
        assert normalize_url("www.github.com") == "https://www.github.com"

    def test_adds_https_for_domain(self):
        assert normalize_url("linkedin.com/in/user") == "https://linkedin.com/in/user"

    def test_none(self):
        assert normalize_url(None) is None

    def test_empty(self):
        assert normalize_url("") is None

    def test_garbage(self):
        assert normalize_url("not_a_url_at_all") is None


# ─────────────────────────────────────────────────────────────────────────────
# Date
# ─────────────────────────────────────────────────────────────────────────────
class TestNormalizeDate:
    def test_year_only(self):
        assert normalize_date("2019") == "2019-01"

    def test_month_year_slash(self):
        assert normalize_date("06/2019") == "2019-06"

    def test_month_name(self):
        result = normalize_date("January 2021")
        assert result == "2021-01"

    def test_present(self):
        assert normalize_date("Present") == "Present"

    def test_current(self):
        assert normalize_date("current") == "Present"

    def test_none(self):
        assert normalize_date(None) is None

    def test_empty(self):
        assert normalize_date("") is None


# ─────────────────────────────────────────────────────────────────────────────
# Years of experience
# ─────────────────────────────────────────────────────────────────────────────
class TestNormalizeYearsExperience:
    def test_integer(self):
        assert normalize_years_experience(5) == 5.0

    def test_float(self):
        assert normalize_years_experience(5.5) == 5.5

    def test_string_with_years(self):
        assert normalize_years_experience("7 years") == 7.0

    def test_string_with_plus(self):
        assert normalize_years_experience("5+") == 5.0

    def test_range_averages(self):
        assert normalize_years_experience("3-5") == 4.0

    def test_none(self):
        assert normalize_years_experience(None) is None

    def test_no_digits(self):
        assert normalize_years_experience("no experience") is None