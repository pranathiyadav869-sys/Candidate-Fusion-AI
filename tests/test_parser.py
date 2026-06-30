"""
tests/test_parser.py
--------------------
Tests for all parsers: CSV, ATS, Resume (PDF), GitHub.
"""
import json
import os
import tempfile
from pathlib import Path

import pytest

from parsers.csv_parser import parse_csv
from parsers.ats_parser import parse_ats
from utils.exceptions import CSVParseError, ATSParseError


# ─────────────────────────────────────────────────────────────────────────────
# CSV Parser
# ─────────────────────────────────────────────────────────────────────────────
class TestCSVParser:
    def _write_csv(self, content: str) -> Path:
        tmp = tempfile.NamedTemporaryFile(suffix=".csv", mode="w", delete=False, encoding="utf-8")
        tmp.write(content)
        tmp.close()
        return Path(tmp.name)

    def test_basic_valid_row(self):
        p = self._write_csv(
            "Candidate Name,Email,Phone,Location,Skills,Years Experience\n"
            "Alice Smith,alice@example.com,+919876543210,Hyderabad India,Python;Django,5\n"
        )
        results = parse_csv(p)
        assert len(results) == 1
        r = results[0]
        assert r["full_name"] == "Alice Smith"
        assert "alice@example.com" in r["emails"]
        assert r["years_experience"] == 5.0
        os.unlink(p)

    def test_invalid_email_dropped_with_warning(self):
        p = self._write_csv(
            "name,email,skills\n"
            "Bob Jones,not-an-email,Python\n"
        )
        results = parse_csv(p)
        assert results[0]["emails"] == []
        os.unlink(p)

    def test_column_aliases(self):
        # Test that "name", "e-mail", "yoe" all map correctly
        p = self._write_csv("name,e-mail,yoe\nCarol Chen,carol@x.com,3\n")
        results = parse_csv(p)
        assert results[0]["full_name"] == "Carol Chen"
        assert results[0]["emails"] == ["carol@x.com"]
        assert results[0]["years_experience"] == 3.0
        os.unlink(p)

    def test_semicolon_separated_skills(self):
        p = self._write_csv("name,email,skills\nDan,d@x.com,Python;AWS;Docker\n")
        results = parse_csv(p)
        skills = results[0]["skills"]
        assert "Python" in skills
        assert "AWS" in skills
        os.unlink(p)

    def test_pipe_separated_emails(self):
        p = self._write_csv("name,email\nEve,eve@a.com|eve@b.com\n")
        results = parse_csv(p)
        assert len(results[0]["emails"]) == 2
        os.unlink(p)

    def test_empty_rows_skipped(self):
        p = self._write_csv("name,email\nAlice,alice@x.com\n,,\n\nBob,bob@x.com\n")
        results = parse_csv(p)
        assert len(results) == 2
        os.unlink(p)

    def test_file_not_found_raises(self):
        with pytest.raises(CSVParseError):
            parse_csv("/nonexistent/file.csv")

    def test_no_headers_raises(self):
        p = self._write_csv("")
        with pytest.raises(CSVParseError):
            parse_csv(p)
        os.unlink(p)

    def test_bom_utf8_handled(self):
        tmp = tempfile.NamedTemporaryFile(suffix=".csv", mode="wb", delete=False)
        tmp.write(b"\xef\xbb\xbfname,email\nFrank,frank@x.com\n")
        tmp.close()
        results = parse_csv(Path(tmp.name))
        assert results[0]["full_name"] == "Frank"
        os.unlink(tmp.name)

    def test_candidate_id_generated_when_missing(self):
        p = self._write_csv("name,email\nGrace,grace@x.com\n")
        results = parse_csv(p)
        assert results[0]["candidate_id"] is not None
        assert len(results[0]["candidate_id"]) > 0
        os.unlink(p)

    def test_duplicate_skills_deduped(self):
        p = self._write_csv("name,skills\nHank,Python,Python;python;py\n")
        results = parse_csv(p)
        skills = results[0]["skills"]
        assert skills.count("Python") == 1
        os.unlink(p)

    def test_yoe_range_string(self):
        p = self._write_csv("name,email,years experience\nIvy,ivy@x.com,3-5\n")
        results = parse_csv(p)
        assert results[0]["years_experience"] == 4.0
        os.unlink(p)


# ─────────────────────────────────────────────────────────────────────────────
# ATS Parser
# ─────────────────────────────────────────────────────────────────────────────
class TestATSParser:
    def _write_ats(self, data: dict) -> Path:
        tmp = tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False, encoding="utf-8")
        json.dump(data, tmp)
        tmp.close()
        return Path(tmp.name)

    def test_basic_parse(self):
        p = self._write_ats({
            "full_name": "Jane Doe",
            "email": "jane@example.com",
            "phone": "+919876543210",
            "skills": [{"name": "Python"}, {"name": "Docker"}],
        })
        result = parse_ats(p)
        assert result["full_name"] == "Jane Doe"
        assert "jane@example.com" in result["emails"]
        assert len(result["skills"]) == 2
        os.unlink(p)

    def test_wrapped_in_candidate_key(self):
        p = self._write_ats({"candidate": {"full_name": "Kate Kim", "email": "kate@x.com"}})
        result = parse_ats(p)
        assert result["full_name"] == "Kate Kim"
        os.unlink(p)

    def test_wrapped_in_applicant_key(self):
        p = self._write_ats({"applicant": {"name": "Leo Lin", "email": "leo@x.com"}})
        result = parse_ats(p)
        assert result["full_name"] == "Leo Lin"
        os.unlink(p)

    def test_composed_name_from_first_last(self):
        p = self._write_ats({"firstName": "Mary", "lastName": "Moon", "email": "mary@x.com"})
        result = parse_ats(p)
        assert result["full_name"] == "Mary Moon"
        os.unlink(p)

    def test_invalid_email_dropped(self):
        p = self._write_ats({"name": "Nick Ng", "email": "notanemail"})
        result = parse_ats(p)
        assert result["emails"] == []
        os.unlink(p)

    def test_location_dict_format(self):
        p = self._write_ats({
            "name": "Olivia Oh",
            "location": {"city": "Hyderabad", "state": "Telangana", "country": "India"}
        })
        result = parse_ats(p)
        assert "Hyderabad" in (result["location"] or "")
        os.unlink(p)

    def test_experience_extraction(self):
        p = self._write_ats({
            "name": "Paul Park",
            "experience": [
                {"title": "Engineer", "company": "Acme", "start_date": "2020", "end_date": "Present"}
            ]
        })
        result = parse_ats(p)
        assert len(result["experience"]) == 1
        assert result["experience"][0]["company"] == "Acme"
        os.unlink(p)

    def test_current_flag_sets_present(self):
        p = self._write_ats({
            "name": "Quinn Qui",
            "experience": [
                {"title": "CTO", "company": "Startup", "start_date": "2022", "current": True}
            ]
        })
        result = parse_ats(p)
        assert result["experience"][0]["end_date"] == "Present"
        os.unlink(p)

    def test_education_extraction(self):
        p = self._write_ats({
            "name": "Rita Roy",
            "education": [
                {"institution": "MIT", "degree": "B.S.", "field_of_study": "CS", "end_date": "2018"}
            ]
        })
        result = parse_ats(p)
        assert len(result["education"]) == 1
        assert result["education"][0]["institution"] == "MIT"
        os.unlink(p)

    def test_file_not_found(self):
        with pytest.raises(ATSParseError):
            parse_ats("/no/such/file.json")

    def test_invalid_json(self):
        tmp = tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False)
        tmp.write("{ this is not json }")
        tmp.close()
        with pytest.raises(ATSParseError):
            parse_ats(tmp.name)
        os.unlink(tmp.name)

    def test_non_dict_root(self):
        p = self._write_ats([{"name": "Sam"}])
        with pytest.raises(ATSParseError):
            parse_ats(p)
        os.unlink(p)

    def test_skills_string_list(self):
        p = self._write_ats({"name": "Tina Tan", "skills": ["python", "aws", "docker"]})
        result = parse_ats(p)
        assert "Python" in result["skills"]
        assert "AWS" in result["skills"]
        os.unlink(p)

    def test_skills_deduped(self):
        p = self._write_ats({"name": "Uma Uma", "skills": [
            {"name": "Python"}, {"name": "python"}, {"name": "py"}
        ]})
        result = parse_ats(p)
        assert result["skills"].count("Python") == 1
        os.unlink(p)

    def test_gpa_float_and_string(self):
        p = self._write_ats({
            "name": "Vera Vega",
            "education": [
                {"institution": "IIT", "degree": "M.Tech", "gpa": "8.7"},
                {"institution": "OU",  "degree": "B.E.",   "gpa": 9.1},
            ]
        })
        result = parse_ats(p)
        assert result["education"][0]["gpa"] == 8.7
        assert result["education"][1]["gpa"] == 9.1
        os.unlink(p)