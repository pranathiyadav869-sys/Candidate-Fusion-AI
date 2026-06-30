"""
utils/exceptions.py
-------------------
Custom exception hierarchy for CandidateFusion.

Design Decision: A rich exception hierarchy allows callers to catch
at the right granularity (e.g. catch all ParseError vs just CSVParseError)
and gives log messages meaningful context without string matching.
"""

from __future__ import annotations


# ─────────────────────────────────────────────────────────────────────────────
# Base
# ─────────────────────────────────────────────────────────────────────────────

class CandidateFusionError(Exception):
    """
    Root exception for all CandidateFusion errors.
    Catch this to handle any pipeline failure generically.
    """


# ─────────────────────────────────────────────────────────────────────────────
# Configuration errors
# ─────────────────────────────────────────────────────────────────────────────

class ConfigError(CandidateFusionError):
    """Raised when a config file is missing, malformed, or has invalid values."""


class ConfigFileNotFoundError(ConfigError):
    """Raised when a required config file cannot be located."""

    def __init__(self, path: str) -> None:
        super().__init__(f"Config file not found: {path}")
        self.path = path


class ConfigValidationError(ConfigError):
    """Raised when config file content fails schema validation."""

    def __init__(self, path: str, detail: str) -> None:
        super().__init__(f"Config validation error in '{path}': {detail}")
        self.path = path
        self.detail = detail


# ─────────────────────────────────────────────────────────────────────────────
# Parser errors
# ─────────────────────────────────────────────────────────────────────────────

class ParseError(CandidateFusionError):
    """Base class for all parser failures."""

    def __init__(self, source: str, detail: str) -> None:
        super().__init__(f"[{source}] Parse error: {detail}")
        self.source = source
        self.detail = detail


class CSVParseError(ParseError):
    """Raised when the CSV parser encounters an unrecoverable error."""

    def __init__(self, detail: str, row: int | None = None) -> None:
        location = f" (row {row})" if row is not None else ""
        super().__init__("CSV", f"{detail}{location}")
        self.row = row


class ATSParseError(ParseError):
    """Raised when the ATS JSON parser encounters an unrecoverable error."""

    def __init__(self, detail: str) -> None:
        super().__init__("ATS", detail)


class ResumeParseError(ParseError):
    """Raised when the PDF resume parser encounters an unrecoverable error."""

    def __init__(self, detail: str, path: str | None = None) -> None:
        location = f" (file: {path})" if path else ""
        super().__init__("Resume", f"{detail}{location}")
        self.path = path


class GitHubParseError(ParseError):
    """Raised when the GitHub parser cannot reach the API or parse the response."""

    def __init__(self, username: str, detail: str) -> None:
        super().__init__("GitHub", f"user={username}: {detail}")
        self.username = username


# ─────────────────────────────────────────────────────────────────────────────
# Merge errors
# ─────────────────────────────────────────────────────────────────────────────

class MergeError(CandidateFusionError):
    """Raised when the merge engine encounters an irrecoverable conflict."""


# ─────────────────────────────────────────────────────────────────────────────
# Validation errors
# ─────────────────────────────────────────────────────────────────────────────

class ValidationError(CandidateFusionError):
    """Raised when post-merge validation fails critically (not just a warning)."""

    def __init__(self, field: str, detail: str) -> None:
        super().__init__(f"Validation failed for '{field}': {detail}")
        self.field = field
        self.detail = detail


# ─────────────────────────────────────────────────────────────────────────────
# Projection errors
# ─────────────────────────────────────────────────────────────────────────────

class ProjectionError(CandidateFusionError):
    """Raised when output projection/serialization fails."""
