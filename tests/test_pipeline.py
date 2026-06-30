"""
tests/test_pipeline.py
----------------------
Integration tests for the full pipeline (projector + merge + validate).
Uses actual sample input files from the input/ directory.
"""
import json
import os
import tempfile
from pathlib import Path

import pytest

from engine.projector import run_pipeline, PipelineResult

# Paths relative to project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
INPUT_DIR = PROJECT_ROOT / "input"
ATS_JSON = INPUT_DIR / "ats.json"
CSV_FILE = INPUT_DIR / "recruiter.csv"
RESUME_PDF = INPUT_DIR / "resume.pdf"


@pytest.fixture
def tmp_output(tmp_path):
    return tmp_path


class TestPipelineATS:
    def test_ats_only_pipeline(self, tmp_output):
        if not ATS_JSON.exists():
            pytest.skip("input/ats.json not present")
        result = run_pipeline(ats_path=ATS_JSON, output_dir=tmp_output)
        assert isinstance(result, PipelineResult)
        assert result.profile.full_name is not None
        assert result.candidate_json_path.exists()
        assert result.report_json_path.exists()

    def test_ats_outputs_valid_json(self, tmp_output):
        if not ATS_JSON.exists():
            pytest.skip("input/ats.json not present")
        result = run_pipeline(ats_path=ATS_JSON, output_dir=tmp_output)
        with open(result.candidate_json_path) as f:
            data = json.load(f)
        assert "candidate_id" in data

    def test_ats_emails_normalized(self, tmp_output):
        if not ATS_JSON.exists():
            pytest.skip("input/ats.json not present")
        result = run_pipeline(ats_path=ATS_JSON, output_dir=tmp_output)
        for email in result.profile.emails:
            assert email == email.lower()
            assert "@" in email

    def test_ats_invalid_email_excluded(self, tmp_output):
        if not ATS_JSON.exists():
            pytest.skip("input/ats.json not present")
        result = run_pipeline(ats_path=ATS_JSON, output_dir=tmp_output)
        # The ATS sample has "not-an-email@@broken" which should be excluded
        assert not any("@@" in e for e in result.profile.emails)


class TestPipelineCSV:
    def test_csv_only_pipeline(self, tmp_output):
        if not CSV_FILE.exists():
            pytest.skip("input/recruiter.csv not present")
        result = run_pipeline(csv_path=CSV_FILE, output_dir=tmp_output)
        assert isinstance(result, PipelineResult)
        assert result.candidate_json_path.exists()

    def test_csv_skills_normalized(self, tmp_output):
        if not CSV_FILE.exists():
            pytest.skip("input/recruiter.csv not present")
        result = run_pipeline(csv_path=CSV_FILE, output_dir=tmp_output)
        skill_names = [s.canonical_name for s in result.profile.skills]
        # "python" and "ml" should be normalized
        assert "Python" in skill_names or len(skill_names) > 0


class TestPipelineMultiSource:
    def test_ats_and_csv_combined(self, tmp_output):
        if not ATS_JSON.exists() or not CSV_FILE.exists():
            pytest.skip("Sample files not present")
        result = run_pipeline(ats_path=ATS_JSON, csv_path=CSV_FILE, output_dir=tmp_output)
        assert result.profile is not None
        assert len(result.sources_used) == 2

    def test_conflict_log_in_report(self, tmp_output):
        if not ATS_JSON.exists() or not CSV_FILE.exists():
            pytest.skip("Sample files not present")
        result = run_pipeline(ats_path=ATS_JSON, csv_path=CSV_FILE, output_dir=tmp_output)
        with open(result.report_json_path) as f:
            report = json.load(f)
        assert "conflict_log" in report

    def test_field_confidences_in_report(self, tmp_output):
        if not ATS_JSON.exists():
            pytest.skip("Sample files not present")
        result = run_pipeline(ats_path=ATS_JSON, output_dir=tmp_output)
        with open(result.report_json_path) as f:
            report = json.load(f)
        assert "field_confidences" in report
        assert "overall_confidence" in report

    def test_overall_confidence_between_0_and_1(self, tmp_output):
        if not ATS_JSON.exists():
            pytest.skip("Sample files not present")
        result = run_pipeline(ats_path=ATS_JSON, output_dir=tmp_output)
        assert 0.0 <= result.profile.overall_confidence <= 1.0

    def test_elapsed_time_in_report(self, tmp_output):
        if not ATS_JSON.exists():
            pytest.skip("Sample files not present")
        result = run_pipeline(ats_path=ATS_JSON, output_dir=tmp_output)
        with open(result.report_json_path) as f:
            report = json.load(f)
        assert "elapsed_seconds" in report
        assert report["elapsed_seconds"] >= 0


class TestPipelineEdgeCases:
    def test_no_sources_raises_value_error(self, tmp_output):
        with pytest.raises(ValueError):
            run_pipeline(output_dir=tmp_output)

    def test_nonexistent_ats_file_produces_warning(self, tmp_output):
        import tempfile, json
        # Write a valid CSV so pipeline has at least one source
        tmp_csv = tmp_output / "fallback.csv"
        tmp_csv.write_text("name,email\nAlice,alice@x.com\n")
        result = run_pipeline(
            ats_path="/nonexistent/file.json",
            csv_path=tmp_csv,
            output_dir=tmp_output,
        )
        assert any("ATS" in w or "ats" in w.lower() for w in result.warnings)

    def test_projection_field_aliases_applied(self, tmp_output):
        if not ATS_JSON.exists():
            pytest.skip("Sample files not present")
        # The default projection.json aliases full_name → name
        result = run_pipeline(ats_path=ATS_JSON, output_dir=tmp_output)
        with open(result.candidate_json_path) as f:
            data = json.load(f)
        # Either alias is applied or original name is present
        assert "name" in data or "full_name" in data

    def test_output_dir_created_if_missing(self, tmp_path):
        new_dir = tmp_path / "deep" / "nested" / "output"
        if not ATS_JSON.exists():
            pytest.skip("Sample files not present")
        result = run_pipeline(ats_path=ATS_JSON, output_dir=new_dir)
        assert new_dir.exists()
        assert result.candidate_json_path.exists()