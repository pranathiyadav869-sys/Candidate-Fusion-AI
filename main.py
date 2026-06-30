# #!/usr/bin/env python3
# """
# main.py
# -------
# CandidateFusion AI — CLI entry point.

# Pipeline stages (in order):
#     1. Parse every enabled source     (parsers.csv_parser.parse_csv,
#                                         parsers.ats_parser.parse_ats,
#                                         parsers.resume_parser.parse_resume,
#                                         parsers.github_parser.parse_github)
#     2. Merge records                  (engine.merge.merge_sources)
#     3. Validate CandidateProfile      (engine.validator.validate_profile)
#     4. Apply projection               (engine.projector.project_candidate)
#     5. Save output/candidate.json and output/pipeline_report.json
#     6. Log execution                  (engine.logger.setup_logging)
#     7. Print a CLI summary            (rich, with a plain-text fallback)

# Integration notes (read before modifying):
# - This file calls ONLY the public functions that already exist in the
#   uploaded codebase. No new parser classes or merge APIs were invented:
#     parse_csv(path)        -> list[dict]   (one dict per CSV row)
#     parse_ats(path)        -> dict
#     parse_resume(path)     -> dict
#     parse_github(username) -> dict          (NOTE: takes a username, not a path)
#     merge_sources(Dict[SourceName, dict]) -> CandidateProfile
#     validate_profile(CandidateProfile)    -> CandidateProfile
# - merge_sources() expects exactly ONE dict per SourceName key. csv_parser
#   returns a LIST (a CSV can contain many rows/candidates), so when CSV is
#   used as one of several sources for a single fused profile, main.py
#   takes the first matching row (by --csv-row-email/--csv-row-index) or
#   the first row by default, and logs a warning if the CSV had more rows
#   that were not used. Bulk/batch fusion of an entire CSV is intentionally
#   out of scope for this CLI (the architecture doesn't constrain it either
#   way) and is documented as a possible future entry point.
# - GitHub is the only source identified by a username rather than a file
#   path; it is looked up via --github-username or the GITHUB_USERNAME
#   env var, consistent with parse_github()'s own GITHUB_TOKEN fallback.
# """

# from __future__ import annotations

# import argparse
# import logging
# import os
# import sys
# import time
# from pathlib import Path
# from typing import Any, Dict, List, Optional

# from engine.logger import setup_logging
# from engine.merge import merge_sources
# from engine.projector import (
#     build_pipeline_report,
#     load_projection_config,
#     project_candidate,
#     save_outputs,
# )
# from engine.schema import CandidateProfile, SourceName
# from engine.validator import validate_profile
# from parsers.ats_parser import parse_ats
# from parsers.csv_parser import parse_csv
# from parsers.github_parser import parse_github
# from parsers.resume_parser import parse_resume
# from utils.constants import PROJECT_ROOT
# from utils.exceptions import CandidateFusionError

# logger = logging.getLogger(__name__)

# DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "output"


# # ---------------------------------------------------------------------------
# # CLI argument parsing
# # ---------------------------------------------------------------------------

# def build_arg_parser() -> argparse.ArgumentParser:
#     parser = argparse.ArgumentParser(
#         prog="candidatefusion",
#         description="CandidateFusion AI — fuse a candidate profile from multiple sources.",
#     )
#     parser.add_argument("--csv", type=str, default=None, help="Path to recruiter CSV file")
#     parser.add_argument(
#         "--csv-row-email", type=str, default=None,
#         help="If --csv has multiple rows, select the row whose email matches this value",
#     )
#     parser.add_argument(
#         "--csv-row-index", type=int, default=0,
#         help="If --csv has multiple rows and --csv-row-email is not given, "
#              "use this 0-based row index (default: 0, the first row)",
#     )
#     parser.add_argument("--ats", type=str, default=None, help="Path to ATS JSON file")
#     parser.add_argument("--resume", type=str, default=None, help="Path to resume PDF file")
#     parser.add_argument(
#         "--github-username", type=str, default=None,
#         help="GitHub username to fetch (falls back to GITHUB_USERNAME env var)",
#     )
#     parser.add_argument(
#         "--github-token", type=str, default=None,
#         help="GitHub personal access token (falls back to GITHUB_TOKEN env var)",
#     )
#     parser.add_argument(
#         "--output-dir", type=str, default=str(DEFAULT_OUTPUT_DIR),
#         help=f"Directory to write candidate.json / pipeline_report.json (default: {DEFAULT_OUTPUT_DIR})",
#     )
#     parser.add_argument(
#         "--log-level", type=str, default=None,
#         help="Override DEFAULT_LOG_LEVEL from utils.constants (e.g. DEBUG, INFO, WARNING)",
#     )
#     parser.add_argument(
#         "--no-console-log", action="store_true",
#         help="Suppress console log output (file logging still happens)",
#     )
#     return parser


# # ---------------------------------------------------------------------------
# # Per-source parsing, isolated so one bad source can't kill the run
# # ---------------------------------------------------------------------------

# def _select_csv_row(
#     rows: List[Dict[str, Any]], row_email: Optional[str], row_index: int
# ) -> Dict[str, Any]:
#     """Pick a single row dict out of parse_csv()'s list-of-rows return value."""
#     if not rows:
#         raise CandidateFusionError("CSV file contained no usable rows")

#     if row_email:
#         target = row_email.strip().lower()
#         for row in rows:
#             if target in [e.lower() for e in (row.get("emails") or [])]:
#                 return row
#         logger.warning(
#             "No CSV row matched --csv-row-email=%s; falling back to row index %d",
#             row_email, row_index,
#         )

#     if len(rows) > 1:
#         logger.warning(
#             "CSV contains %d candidate rows; using row index %d. "
#             "Pass --csv-row-email or --csv-row-index to select a different row.",
#             len(rows), row_index,
#         )
#     if not (0 <= row_index < len(rows)):
#         logger.warning("--csv-row-index=%d out of range; using row 0 instead", row_index)
#         row_index = 0
#     return rows[row_index]


# def run_parsers(args: argparse.Namespace) -> tuple[
#     Dict[SourceName, Dict[str, Any]], List[str], List[str], Dict[str, str], Dict[str, float]
# ]:
#     """
#     Run every enabled source's parser, isolating failures per-source.

#     Returns
#     -------
#     (source_records, attempted, succeeded, errors, timing)
#     """
#     source_records: Dict[SourceName, Dict[str, Any]] = {}
#     attempted: List[str] = []
#     succeeded: List[str] = []
#     errors: Dict[str, str] = {}
#     timing: Dict[str, float] = {}

#     # ── CSV ──────────────────────────────────────────────────────────────
#     if args.csv:
#         attempted.append("csv")
#         t0 = time.perf_counter()
#         try:
#             rows = parse_csv(args.csv)
#             row = _select_csv_row(rows, args.csv_row_email, args.csv_row_index)
#             source_records[SourceName.CSV] = row
#             succeeded.append("csv")
#             logger.info("CSV source parsed successfully: %s", args.csv)
#         except Exception as exc:
#             logger.error("CSV parsing failed: %s", exc)
#             errors["csv"] = str(exc)
#         timing["csv_seconds"] = round(time.perf_counter() - t0, 4)

#     # ── ATS ──────────────────────────────────────────────────────────────
#     if args.ats:
#         attempted.append("ats")
#         t0 = time.perf_counter()
#         try:
#             source_records[SourceName.ATS] = parse_ats(args.ats)
#             succeeded.append("ats")
#             logger.info("ATS source parsed successfully: %s", args.ats)
#         except Exception as exc:
#             logger.error("ATS parsing failed: %s", exc)
#             errors["ats"] = str(exc)
#         timing["ats_seconds"] = round(time.perf_counter() - t0, 4)

#     # ── Resume ───────────────────────────────────────────────────────────
#     if args.resume:
#         attempted.append("resume")
#         t0 = time.perf_counter()
#         try:
#             source_records[SourceName.RESUME] = parse_resume(args.resume)
#             succeeded.append("resume")
#             logger.info("Resume source parsed successfully: %s", args.resume)
#         except Exception as exc:
#             logger.error("Resume parsing failed: %s", exc)
#             errors["resume"] = str(exc)
#         timing["resume_seconds"] = round(time.perf_counter() - t0, 4)

#     # ── GitHub ───────────────────────────────────────────────────────────
#     github_username = args.github_username or os.environ.get("GITHUB_USERNAME")
#     if github_username:
#         attempted.append("github")
#         t0 = time.perf_counter()
#         try:
#             github_token = args.github_token or os.environ.get("GITHUB_TOKEN")
#             source_records[SourceName.GITHUB] = parse_github(github_username, github_token)
#             succeeded.append("github")
#             logger.info("GitHub source parsed successfully: %s", github_username)
#         except Exception as exc:
#             logger.error("GitHub parsing failed: %s", exc)
#             errors["github"] = str(exc)
#         timing["github_seconds"] = round(time.perf_counter() - t0, 4)

#     return source_records, attempted, succeeded, errors, timing


# # ---------------------------------------------------------------------------
# # CLI summary printing
# # ---------------------------------------------------------------------------

# def _print_summary_plain(
#     profile: CandidateProfile,
#     attempted: List[str],
#     succeeded: List[str],
#     errors: Dict[str, str],
#     output_paths: Dict[str, Path],
#     total_seconds: float,
# ) -> None:
#     bar = "=" * 60
#     print(f"\n{bar}")
#     print("  CandidateFusion AI — Pipeline Summary")
#     print(bar)
#     print(f"  Candidate ID        : {profile.candidate_id}")
#     print(f"  Name                : {profile.full_name or '(unknown)'}")
#     print(f"  Emails              : {', '.join(profile.emails) or '(none)'}")
#     print(f"  Phones              : {', '.join(profile.phones) or '(none)'}")
#     print(f"  Location            : {profile.location or '(unknown)'}")
#     print(f"  Skills found        : {len(profile.skills)}")
#     print(f"  Experience entries  : {len(profile.experience)}")
#     print(f"  Education entries   : {len(profile.education)}")
#     print(f"  Overall confidence  : {profile.overall_confidence:.2%}")
#     print(bar)
#     print(f"  Sources attempted   : {', '.join(attempted) or '(none)'}")
#     print(f"  Sources succeeded   : {', '.join(succeeded) or '(none)'}")
#     if errors:
#         print(f"  Sources failed      : {', '.join(errors.keys())}")
#         for src, msg in errors.items():
#             print(f"    - {src}: {msg}")
#     print(bar)
#     print(f"  candidate.json      : {output_paths['candidate_json']}")
#     print(f"  pipeline_report.json: {output_paths['pipeline_report']}")
#     print(f"  Total time          : {total_seconds:.2f}s")
#     print(f"{bar}\n")


# def _print_summary_rich(
#     profile: CandidateProfile,
#     attempted: List[str],
#     succeeded: List[str],
#     errors: Dict[str, str],
#     output_paths: Dict[str, Path],
#     total_seconds: float,
# ) -> bool:
#     """Try to print a richly-formatted summary. Returns False if `rich`
#     is unavailable so the caller can fall back to plain text."""
#     try:
#         from rich.console import Console
#         from rich.panel import Panel
#         from rich.table import Table
#     except ImportError:
#         return False

#     console = Console()

#     table = Table(title="CandidateFusion AI — Pipeline Summary", show_header=False)
#     table.add_column("Field", style="bold cyan")
#     table.add_column("Value")
#     table.add_row("Candidate ID", profile.candidate_id)
#     table.add_row("Name", profile.full_name or "[dim](unknown)[/dim]")
#     table.add_row("Emails", ", ".join(profile.emails) or "[dim](none)[/dim]")
#     table.add_row("Phones", ", ".join(profile.phones) or "[dim](none)[/dim]")
#     table.add_row("Location", profile.location or "[dim](unknown)[/dim]")
#     table.add_row("Skills found", str(len(profile.skills)))
#     table.add_row("Experience entries", str(len(profile.experience)))
#     table.add_row("Education entries", str(len(profile.education)))
#     confidence_pct = f"{profile.overall_confidence:.1%}"
#     conf_style = "green" if profile.overall_confidence >= 0.75 else (
#         "yellow" if profile.overall_confidence >= 0.5 else "red"
#     )
#     table.add_row("Overall confidence", f"[{conf_style}]{confidence_pct}[/{conf_style}]")
#     console.print(table)

#     sources_line = (
#         f"Attempted: {', '.join(attempted) or '-'}\n"
#         f"Succeeded: {', '.join(succeeded) or '-'}\n"
#     )
#     if errors:
#         sources_line += "Failed: " + ", ".join(
#             f"{src} ({msg})" for src, msg in errors.items()
#         )
#         console.print(Panel(sources_line, title="Sources", border_style="yellow"))
#     else:
#         console.print(Panel(sources_line, title="Sources", border_style="green"))

#     console.print(
#         Panel(
#             f"candidate.json:       {output_paths['candidate_json']}\n"
#             f"pipeline_report.json: {output_paths['pipeline_report']}\n"
#             f"Total time:           {total_seconds:.2f}s",
#             title="Output",
#             border_style="blue",
#         )
#     )
#     return True


# def print_summary(
#     profile: CandidateProfile,
#     attempted: List[str],
#     succeeded: List[str],
#     errors: Dict[str, str],
#     output_paths: Dict[str, Path],
#     total_seconds: float,
# ) -> None:
#     if not _print_summary_rich(profile, attempted, succeeded, errors, output_paths, total_seconds):
#         _print_summary_plain(profile, attempted, succeeded, errors, output_paths, total_seconds)


# # ---------------------------------------------------------------------------
# # Pipeline orchestration
# # ---------------------------------------------------------------------------

# def run_pipeline(args: argparse.Namespace) -> int:
#     """
#     Execute the full pipeline. Returns a process exit code (0 = success).
#     """
#     pipeline_start = time.perf_counter()

#     if not any([args.csv, args.ats, args.resume, args.github_username,
#                 os.environ.get("GITHUB_USERNAME")]):
#         logger.error(
#             "No sources enabled. Provide at least one of --csv, --ats, "
#             "--resume, or --github-username."
#         )
#         return 2

#     # 1. Parse every enabled source
#     source_records, attempted, succeeded, errors, timing = run_parsers(args)

#     if not source_records:
#         logger.error("All sources failed to parse; nothing to merge. See errors above.")
#         return 1

#     # 2. Merge records
#     t0 = time.perf_counter()
#     try:
#         profile = merge_sources(source_records)
#     except Exception as exc:
#         logger.exception("Merge stage failed unrecoverably")
#         return 1
#     timing["merge_seconds"] = round(time.perf_counter() - t0, 4)

#     # 3. Validate CandidateProfile
#     t0 = time.perf_counter()
#     validation_warnings: List[str] = []
#     warning_capture = _WarningCaptureHandler()
#     validator_logger = logging.getLogger("engine.validator")
#     validator_logger.addHandler(warning_capture)
#     try:
#         profile = validate_profile(profile)
#     finally:
#         validator_logger.removeHandler(warning_capture)
#     validation_warnings = warning_capture.warnings
#     timing["validation_seconds"] = round(time.perf_counter() - t0, 4)

#     # 4. Apply projection
#     t0 = time.perf_counter()
#     try:
#         projection_config = load_projection_config()
#         candidate_dict = project_candidate(profile, projection_config)
#         report_dict = build_pipeline_report(
#             profile=profile,
#             sources_attempted=attempted,
#             sources_succeeded=succeeded,
#             source_errors=errors,
#             validation_warnings=validation_warnings,
#             timing=timing,
#             config=projection_config,
#         )
#     except Exception:
#         logger.exception("Projection stage failed unrecoverably")
#         return 1
#     timing["projection_seconds"] = round(time.perf_counter() - t0, 4)

#     # 5. Save output/candidate.json and output/pipeline_report.json
#     total_seconds = round(time.perf_counter() - pipeline_start, 4)
#     timing["total_seconds"] = total_seconds
#     report_dict["timing"] = timing  # ensure final total is included

#     try:
#         output_paths = save_outputs(
#             candidate_dict, report_dict, args.output_dir, config=projection_config
#         )
#     except Exception:
#         logger.exception("Failed to save output files")
#         return 1

#     # 7. Print a professional CLI summary  (6. logging already active throughout)
#     print_summary(profile, attempted, succeeded, errors, output_paths, total_seconds)

#     if errors and not succeeded:
#         return 1
#     return 0


# class _WarningCaptureHandler(logging.Handler):
#     """Captures WARNING-level log records emitted by engine.validator so
#     they can be embedded in pipeline_report.json, without engine/validator.py
#     needing to return them explicitly (its public contract is "never raises,
#     logs warnings" — this handler respects that contract rather than
#     changing validate_profile()'s signature)."""

#     def __init__(self) -> None:
#         super().__init__(level=logging.WARNING)
#         self.warnings: List[str] = []

#     def emit(self, record: logging.LogRecord) -> None:
#         self.warnings.append(record.getMessage())


# # ---------------------------------------------------------------------------
# # Entrypoint
# # ---------------------------------------------------------------------------

# def main(argv: Optional[List[str]] = None) -> int:
#     parser = build_arg_parser()
#     args = parser.parse_args(argv)

#     setup_logging(level=args.log_level, console=not args.no_console_log)

#     Path(args.output_dir).mkdir(parents=True, exist_ok=True)

#     logger.info("CandidateFusion AI pipeline starting")
#     try:
#         exit_code = run_pipeline(args)
#     except CandidateFusionError as exc:
#         logger.error("Pipeline failed: %s", exc)
#         exit_code = 1
#     except Exception:
#         logger.exception("Unexpected error in pipeline")
#         exit_code = 1

#     logger.info("CandidateFusion AI pipeline finished with exit code %d", exit_code)
#     return exit_code


# if __name__ == "__main__":
#     sys.exit(main())
#!/usr/bin/env python3
"""
main.py
-------
CandidateFusion AI — CLI entry point.

Delegates the entire pipeline (parsing, merging, validation, projection,
and output writing) to engine.projector.run_pipeline().
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import List, Optional

from engine.projector import run_pipeline

logger = logging.getLogger(__name__)

DEFAULT_OUTPUT_DIR = "output"


# ---------------------------------------------------------------------------
# CLI argument parsing
# ---------------------------------------------------------------------------

def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="candidatefusion",
        description="CandidateFusion AI — fuse a candidate profile from multiple sources.",
    )
    parser.add_argument("--csv", type=str, default=None, help="Path to recruiter CSV file")
    parser.add_argument("--ats", type=str, default=None, help="Path to ATS JSON file")
    parser.add_argument("--resume", type=str, default=None, help="Path to resume PDF file")
    parser.add_argument(
        "--github-username", type=str, default=None,
        help="GitHub username to fetch",
    )
    parser.add_argument(
        "--github-token", type=str, default=None,
        help="GitHub personal access token",
    )
    parser.add_argument(
        "--output-dir", type=str, default=DEFAULT_OUTPUT_DIR,
        help=f"Directory to write candidate.json / pipeline_report.json (default: {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "--projection-config", type=str, default=None,
        help="Custom projection.json path",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging")
    return parser


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="[%(asctime)s] %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


# ---------------------------------------------------------------------------
# Summary printing
# ---------------------------------------------------------------------------

def print_summary(result) -> None:
    print(f"\n✅ Pipeline complete in {result.elapsed_seconds:.2f}s")
    print(f"   Sources used : {', '.join(result.sources_used) or '-'}")
    print(f"   Candidate ID : {result.profile.candidate_id}")
    print(f"   Name         : {result.profile.full_name or '(not found)'}")
    print(f"   Confidence   : {result.profile.overall_confidence:.1%}")
    print(f"   Skills       : {len(result.profile.skills)}")
    print(f"   candidate.json    → {result.candidate_json_path}")
    print(f"   pipeline_report   → {result.report_json_path}")
    if result.warnings:
        print(f"\n⚠️  Warnings ({len(result.warnings)}):")
        for w in result.warnings:
            print(f"   • {w}")


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

def main(argv: Optional[List[str]] = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    _setup_logging(args.verbose)

    if not any([args.csv, args.ats, args.resume, args.github_username]):
        parser.print_help()
        logger.error(
            "No sources enabled. Provide at least one of --csv, --ats, "
            "--resume, or --github-username."
        )
        return 1

    try:
        result = run_pipeline(
            resume_path=args.resume,
            ats_path=args.ats,
            csv_path=args.csv,
            github_username=args.github_username,
            github_token=args.github_token,
            output_dir=args.output_dir,
            projection_config_path=args.projection_config,
        )
        print_summary(result)
        return 0

    except Exception as exc:
        logger.exception("Pipeline failed: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())