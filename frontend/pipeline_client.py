# frontend/pipeline_client.py
"""
Thin wrapper around engine.projector.run_pipeline().

This module owns ZERO business logic. Its only jobs are:
  1. Translate Streamlit's UploadedFile objects into the file paths that
     run_pipeline() expects (parsers read from disk, not from file-like
     objects in memory).
  2. Accept a GitHub username OR a full GitHub profile URL and normalize
     it to a plain username before handing it to run_pipeline().
  3. Catch anything run_pipeline() (or the parsers underneath it) raises,
     and turn it into a friendly, displayable message instead of letting
     a traceback reach the user.

run_pipeline() itself, and everything it calls, is never modified.
"""

from __future__ import annotations

import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from engine.projector import PipelineResult, run_pipeline


@dataclass
class PipelineClientResult:
    """What the Streamlit app actually works with — always safe to read,
    even when the pipeline failed."""
    success: bool
    result: Optional[PipelineResult] = None
    error_message: Optional[str] = None


def extract_github_username(raw_input: Optional[str]) -> Optional[str]:
    """
    Accept either a bare username ("octocat") or a full GitHub profile
    URL ("https://github.com/octocat", "github.com/octocat/", etc.) and
    return just the username. Returns None for empty input.
    """
    if not raw_input:
        return None

    value = raw_input.strip()
    if not value:
        return None

    match = re.search(r"github\.com/([A-Za-z0-9-]+)", value)
    if match:
        return match.group(1)

    # Not a URL — treat the cleaned input as a plain username
    return value.strip("/ ")


def _save_uploaded_file(uploaded_file, suffix: str) -> Optional[str]:
    """
    Persist a Streamlit UploadedFile to a temp file on disk and return its
    path. Parsers expect real file paths, not in-memory file-like objects,
    so this bridges that gap without touching the parsers themselves.
    """
    if uploaded_file is None:
        return None

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.write(uploaded_file.getbuffer())
    tmp.flush()
    tmp.close()
    return tmp.name


def generate_candidate_profile(
    *,
    resume_file=None,
    ats_file=None,
    csv_file=None,
    github_input: Optional[str] = None,
    github_token: Optional[str] = None,
    output_dir: str = "output",
) -> PipelineClientResult:
    """
    Save any uploaded files to disk, normalize the GitHub input, call
    run_pipeline(), and return a result that's always safe to render —
    no matter what went wrong inside the pipeline.
    """
    resume_path = ats_path = csv_path = None

    try:
        resume_path = _save_uploaded_file(resume_file, suffix=".pdf")
        ats_path = _save_uploaded_file(ats_file, suffix=".json")
        csv_path = _save_uploaded_file(csv_file, suffix=".csv")
        github_username = extract_github_username(github_input)

        if not any([resume_path, ats_path, csv_path, github_username]):
            return PipelineClientResult(
                success=False,
                error_message=(
                    "Please provide at least one source: a resume PDF, "
                    "ATS JSON, recruiter CSV, or a GitHub username/profile URL."
                ),
            )

        result = run_pipeline(
            resume_path=resume_path,
            ats_path=ats_path,
            csv_path=csv_path,
            github_username=github_username,
            github_token=github_token,
            output_dir=output_dir,
        )
        return PipelineClientResult(success=True, result=result)

    except Exception as exc:
        return PipelineClientResult(
            success=False,
            error_message=f"We couldn't generate the candidate profile: {exc}",
        )

    finally:
        # Uploads only need to live for the duration of this call — the
        # parsers have already read them by the time we get here.
        for path in (resume_path, ats_path, csv_path):
            if path:
                try:
                    Path(path).unlink(missing_ok=True)
                except OSError:
                    pass