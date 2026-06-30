# # """
# # engine/projector.py

# # Projection layer.

# # Transforms canonical CandidateProfile into
# # user-requested output format based on config.
# # """

# # from __future__ import annotations

# # from copy import deepcopy


# # class Projector:

# #     def __init__(self, config: dict):
# #         self.config = config or {}

# #     def project(self, candidate: dict) -> dict:

# #         result = deepcopy(candidate)

# #         # Hide provenance
# #         if self.config.get("hide_provenance", False):
# #             result.pop("provenance", None)

# #         # Hide confidence
# #         if self.config.get("hide_confidence", False):
# #             result.pop("overall_confidence", None)

# #             if "skills" in result:
# #                 for skill in result["skills"]:
# #                     skill.pop("confidence", None)

# #         # Rename fields
# #         aliases = self.config.get("field_aliases", {})

# #         for old, new in aliases.items():
# #             if old in result:
# #                 result[new] = result.pop(old)

# #         # Remove excluded fields
# #         exclude = self.config.get("exclude_fields", [])

# #         for field in exclude:
# #             result.pop(field, None)

# #         return result



# """
# engine/projector.py
# --------------------
# Output projection layer: turns a validated CandidateProfile into the two
# files the pipeline writes — candidate.json and pipeline_report.json.

# Design Decision: CandidateProfile.to_output_dict() (in engine/schema.py)
# already implements field aliasing, provenance hiding, confidence hiding,
# and field exclusion. This module does NOT duplicate that logic — it is a
# thin orchestration layer that:
#   1. Loads config/projection.json
#   2. Calls profile.to_output_dict(config) to get the candidate dict
#   3. Assembles a separate pipeline_report dict (source summary, conflict
#      log, field confidences, validation warnings, timing) according to
#      the `report` section of projection.json
#   4. Writes both files via utils.helpers.write_json

# This keeps schema.py as the single source of truth for *what a
# candidate record looks like on disk*, while this module owns *pipeline
# run metadata*, which schema.py has no business knowing about.
# """

# from __future__ import annotations

# import logging
# from pathlib import Path
# from typing import Any, Dict, List, Optional

# from engine.schema import CandidateProfile
# from utils.constants import PROJECTION_CONFIG_PATH
# from utils.exceptions import ProjectionError
# from utils.helpers import load_json_config_safe, write_json

# logger = logging.getLogger(__name__)

# # Fallback defaults mirror config/projection.json so the pipeline still
# # runs (with sane behavior) even if that file is ever missing/corrupt.
# _DEFAULT_PROJECTION_CONFIG: Dict[str, Any] = {
#     "hide_provenance": False,
#     "hide_confidence": False,
#     "field_aliases": {},
#     "exclude_fields": [],
#     "output": {
#         "candidate_json": "candidate.json",
#         "pipeline_report": "pipeline_report.json",
#         "indent": 2,
#         "ensure_ascii": False,
#     },
#     "report": {
#         "include_source_summary": True,
#         "include_conflict_log": True,
#         "include_field_confidences": True,
#         "include_validation_warnings": True,
#         "include_timing": True,
#     },
# }


# def load_projection_config(path: str | Path | None = None) -> Dict[str, Any]:
#     """Load config/projection.json, falling back to safe defaults on error."""
#     config = load_json_config_safe(
#         path or PROJECTION_CONFIG_PATH, default=_DEFAULT_PROJECTION_CONFIG
#     )
#     # Strip the "_comment"/"_version" metadata keys before use; they are
#     # documentation-only and were never meant to reach to_output_dict().
#     return {k: v for k, v in config.items() if not k.startswith("_")}


# def project_candidate(
#     profile: CandidateProfile, config: Optional[Dict[str, Any]] = None
# ) -> Dict[str, Any]:
#     """
#     Apply projection.json rules to a validated CandidateProfile.

#     Delegates entirely to CandidateProfile.to_output_dict(), which already
#     implements hide_provenance / hide_confidence / field_aliases /
#     exclude_fields. This function's only job is supplying the config.
#     """
#     cfg = config if config is not None else load_projection_config()
#     try:
#         return profile.to_output_dict(cfg)
#     except Exception as exc:
#         raise ProjectionError(f"Failed to project candidate profile: {exc}") from exc


# def build_pipeline_report(
#     *,
#     profile: CandidateProfile,
#     sources_attempted: List[str],
#     sources_succeeded: List[str],
#     source_errors: Dict[str, str],
#     validation_warnings: List[str],
#     timing: Dict[str, float],
#     config: Optional[Dict[str, Any]] = None,
# ) -> Dict[str, Any]:
#     """
#     Assemble the pipeline_report.json content.

#     Parameters
#     ----------
#     profile             : the final, validated CandidateProfile
#     sources_attempted   : every source name the CLI was asked to run
#     sources_succeeded   : sources that returned data successfully
#     source_errors       : {source_name: error_message} for sources that failed
#     validation_warnings : warnings captured during engine.validator.validate_profile
#     timing              : {"total_seconds": ..., "<source>_seconds": ..., ...}
#     config              : projection.json content (loaded if not supplied)

#     Returns
#     -------
#     dict ready to be written as pipeline_report.json
#     """
#     cfg = config if config is not None else load_projection_config()
#     report_cfg = cfg.get("report", _DEFAULT_PROJECTION_CONFIG["report"])

#     report: Dict[str, Any] = {
#         "candidate_id": profile.candidate_id,
#         "overall_confidence": profile.overall_confidence,
#     }

#     if report_cfg.get("include_source_summary", True):
#         report["source_summary"] = {
#             "attempted": sources_attempted,
#             "succeeded": sources_succeeded,
#             "failed": sorted(source_errors.keys()),
#             "errors": source_errors,
#         }

#     if report_cfg.get("include_field_confidences", True):
#         report["field_confidences"] = {
#             field: fp.confidence for field, fp in profile.provenance.items()
#         }

#     if report_cfg.get("include_conflict_log", True):
#         report["conflict_log"] = _build_conflict_log(profile)

#     if report_cfg.get("include_validation_warnings", True):
#         report["validation_warnings"] = validation_warnings

#     if report_cfg.get("include_timing", True):
#         report["timing"] = timing

#     return report


# def _build_conflict_log(profile: CandidateProfile) -> List[Dict[str, Any]]:
#     """
#     Surface fields where more than one source supplied a competing value,
#     using the provenance entries that engine.provenance.ProvenanceTracker
#     already recorded during merge. A "conflict" here means: more than one
#     distinct raw value was seen for a scalar field, OR more than one
#     source contributed entries for a list field.
#     """
#     conflicts: List[Dict[str, Any]] = []
#     for field_name, fp in profile.provenance.items():
#         distinct_raw_values = {
#             e.raw_value for e in fp.entries if e.raw_value is not None
#         }
#         sources_seen = {e.source.value for e in fp.entries}
#         if len(distinct_raw_values) > 1 or len(sources_seen) > 1:
#             conflicts.append({
#                 "field": field_name,
#                 "selected_source": fp.selected_source.value if fp.selected_source else None,
#                 "final_confidence": fp.confidence,
#                 "candidates": [
#                     {
#                         "source": e.source.value,
#                         "method": e.method,
#                         "raw_value": e.raw_value,
#                         "confidence": e.confidence,
#                     }
#                     for e in fp.entries
#                 ],
#             })
#     return conflicts


# def save_outputs(
#     candidate_dict: Dict[str, Any],
#     report_dict: Dict[str, Any],
#     output_dir: str | Path,
#     config: Optional[Dict[str, Any]] = None,
# ) -> Dict[str, Path]:
#     """
#     Write candidate.json and pipeline_report.json to output_dir, honoring
#     the filenames/indent/ensure_ascii settings from projection.json.

#     Returns
#     -------
#     dict mapping {"candidate_json": Path, "pipeline_report": Path}
#     """
#     cfg = config if config is not None else load_projection_config()
#     out_cfg = cfg.get("output", _DEFAULT_PROJECTION_CONFIG["output"])

#     output_dir = Path(output_dir)
#     candidate_path = output_dir / out_cfg.get("candidate_json", "candidate.json")
#     report_path = output_dir / out_cfg.get("pipeline_report", "pipeline_report.json")
#     indent = out_cfg.get("indent", 2)
#     ensure_ascii = out_cfg.get("ensure_ascii", False)

#     try:
#         write_json(candidate_dict, candidate_path, indent=indent, ensure_ascii=ensure_ascii)
#         write_json(report_dict, report_path, indent=indent, ensure_ascii=ensure_ascii)
#     except Exception as exc:
#         raise ProjectionError(f"Failed to write output files: {exc}") from exc

#     return {"candidate_json": candidate_path, "pipeline_report": report_path}


"""
engine/projector.py
-------------------
Pipeline orchestrator and output projector for CandidateFusion.

Responsibilities:
1. Accept paths to one or more source files (ATS JSON, CSV, GitHub username, Resume PDF).
2. Dispatch each file to the correct parser.
3. Feed all parsed dicts to the merge engine.
4. Run post-merge validation.
5. Apply output projection (field aliases, hiding provenance/confidence, field exclusions).
6. Write candidate.json and pipeline_report.json to the output directory.
7. Return a PipelineResult for programmatic use.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from engine.merge import merge_sources
from engine.schema import CandidateProfile, SourceName
from engine.validator import validate_profile
from utils.helpers import load_json_config_safe

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    """Returned from run_pipeline(). Contains all outputs and metadata."""
    profile: CandidateProfile
    candidate_json_path: Path
    report_json_path: Path
    sources_used: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    elapsed_seconds: float = 0.0


def run_pipeline(
    *,
    resume_path=None,
    ats_path=None,
    csv_path=None,
    github_username=None,
    github_token=None,
    output_dir=".",
    projection_config_path=None,
) -> PipelineResult:
    start = time.perf_counter()

    if not any([resume_path, ats_path, csv_path, github_username]):
        raise ValueError("At least one source must be provided.")

    proj_config_path = projection_config_path or (
        Path(__file__).resolve().parent.parent / "config" / "projection.json"
    )
    proj_config = load_json_config_safe(proj_config_path, default={})

    source_records: dict = {}
    warnings: list = []
    sources_used: list = []

    if resume_path:
        try:
            from parsers.resume_parser import parse_resume
            parsed = parse_resume(resume_path)
            source_records[SourceName.RESUME] = parsed
            sources_used.append(f"resume:{Path(resume_path).name}")
        except Exception as exc:
            msg = f"Resume parse failed: {exc}"
            warnings.append(msg)
            logger.warning(msg)

    if ats_path:
        try:
            from parsers.ats_parser import parse_ats
            parsed = parse_ats(ats_path)
            source_records[SourceName.ATS] = parsed
            sources_used.append(f"ats:{Path(ats_path).name}")
        except Exception as exc:
            msg = f"ATS parse failed: {exc}"
            warnings.append(msg)
            logger.warning(msg)

    if csv_path:
        try:
            from parsers.csv_parser import parse_csv
            rows = parse_csv(csv_path)
            if rows:
                source_records[SourceName.CSV] = rows[0]
                sources_used.append(f"csv:{Path(csv_path).name}")
                if len(rows) > 1:
                    warnings.append(f"CSV has {len(rows)} rows; only first row merged.")
            else:
                warnings.append("CSV produced no candidate rows.")
        except Exception as exc:
            msg = f"CSV parse failed: {exc}"
            warnings.append(msg)
            logger.warning(msg)

    if github_username:
        try:
            from parsers.github_parser import parse_github
            parsed = parse_github(github_username, token=github_token)
            source_records[SourceName.GITHUB] = parsed
            sources_used.append(f"github:{github_username}")
        except Exception as exc:
            msg = f"GitHub parse failed: {exc}"
            warnings.append(msg)
            logger.warning(msg)

    if not source_records:
        raise RuntimeError("All sources failed to parse.")

    profile = merge_sources(source_records)
    profile = validate_profile(profile)

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    output_cfg = proj_config.get("output", {})
    candidate_filename = output_cfg.get("candidate_json", "candidate.json")
    report_filename = output_cfg.get("pipeline_report", "pipeline_report.json")
    indent = output_cfg.get("indent", 2)
    ensure_ascii = output_cfg.get("ensure_ascii", False)

    candidate_data = profile.to_output_dict(config=proj_config)

    candidate_path = out_dir / candidate_filename

    print("DEBUG: candidate path =", candidate_path.resolve())
    print("DEBUG: candidate keys =", list(candidate_data.keys()))

    with candidate_path.open("w", encoding="utf-8") as fh:
        json.dump(candidate_data, fh, indent=indent, ensure_ascii=ensure_ascii, default=str)
        fh.flush()

    print("DEBUG: candidate size =", candidate_path.stat().st_size)

    elapsed = time.perf_counter() - start
    report = _build_report(profile, sources_used, warnings, elapsed, proj_config)

    report_path = out_dir / report_filename

    with report_path.open("w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=indent, ensure_ascii=ensure_ascii, default=str)
        fh.flush()

    print("DEBUG: report size =", report_path.stat().st_size)

    return PipelineResult(
        profile=profile,
        candidate_json_path=candidate_path,
        report_json_path=report_path,
        sources_used=sources_used,
        warnings=warnings,
        elapsed_seconds=elapsed,
    )


def _build_report(profile, sources_used, warnings, elapsed, proj_config):
    report_cfg = proj_config.get("report", {})
    report: dict = {
        "candidatefusion_version": "1.0.0",
        "candidate_id": profile.candidate_id,
    }
    if report_cfg.get("include_source_summary", True):
        report["sources_used"] = sources_used
    if report_cfg.get("include_field_confidences", True):
        report["field_confidences"] = {
            fname: fp.confidence for fname, fp in profile.provenance.items()
        }
        report["overall_confidence"] = profile.overall_confidence
    if report_cfg.get("include_conflict_log", True):
        conflicts = []
        for fname, fp in profile.provenance.items():
            if len(fp.entries) > 1:
                conflicts.append({
                    "field": fname,
                    "selected_source": fp.selected_source.value if fp.selected_source else None,
                    "all_sources": [
                        {"source": e.source.value, "raw_value": e.raw_value, "confidence": e.confidence}
                        for e in fp.entries
                    ],
                })
        report["conflict_log"] = conflicts
    if report_cfg.get("include_validation_warnings", True):
        report["validation_warnings"] = warnings
    if report_cfg.get("include_timing", True):
        report["elapsed_seconds"] = round(elapsed, 4)
    return report