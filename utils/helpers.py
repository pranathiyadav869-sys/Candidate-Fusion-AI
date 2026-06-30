"""
utils/helpers.py
----------------
Shared helper functions used across parsers, engine, and CLI.

Design Decision: Pure functions only – no state, no side-effects.
This makes them trivially testable and safe to import anywhere.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import time
import uuid
from functools import wraps
from pathlib import Path
from typing import Any, Callable, TypeVar

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


# ─────────────────────────────────────────────────────────────────────────────
# ID generation
# ─────────────────────────────────────────────────────────────────────────────

def generate_candidate_id(seed: str | None = None) -> str:
    """
    Generate a deterministic candidate ID from a seed string,
    or a random UUID if no seed is provided.

    Determinism: given the same seed (e.g. normalized email), the same
    candidate always gets the same ID across pipeline runs.
    """
    if seed:
        return hashlib.sha256(seed.encode()).hexdigest()[:16]
    return str(uuid.uuid4()).replace("-", "")[:16]


# ─────────────────────────────────────────────────────────────────────────────
# Config loading
# ─────────────────────────────────────────────────────────────────────────────

def load_json_config(path: str | Path) -> dict[str, Any]:
    """
    Load and parse a JSON config file.

    Parameters
    ----------
    path : str | Path
        Absolute or relative path to the JSON file.

    Returns
    -------
    dict[str, Any]
        Parsed JSON content.

    Raises
    ------
    FileNotFoundError
        If the file does not exist.
    json.JSONDecodeError
        If the file is not valid JSON.
    """
    resolved = Path(path).resolve()
    if not resolved.exists():
        raise FileNotFoundError(f"Config file not found: {resolved}")
    with resolved.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def load_json_config_safe(path: str | Path, default: dict | None = None) -> dict[str, Any]:
    """
    Like load_json_config but returns `default` on any error instead of raising.
    Logs a warning on failure.
    """
    try:
        return load_json_config(path)
    except Exception as exc:
        logger.warning("Could not load config from %s: %s. Using defaults.", path, exc)
        return default or {}


# ─────────────────────────────────────────────────────────────────────────────
# String utilities
# ─────────────────────────────────────────────────────────────────────────────

def coerce_str(value: Any) -> str | None:
    """
    Safely coerce any value to a stripped string.
    Returns None for None, NaN, empty string after stripping.
    """
    if value is None:
        return None
    s = str(value).strip()
    # Handle pandas NaN representations
    if s.lower() in {"nan", "none", "null", "", "n/a", "na", "-"}:
        return None
    return s


def split_multi_value(raw: str, delimiters: str = r"[;|,]") -> list[str]:
    """
    Split a string on common delimiters and return non-empty stripped parts.

    Example
    -------
    >>> split_multi_value("alice@a.com; bob@b.com | carol@c.com")
    ['alice@a.com', 'bob@b.com', 'carol@c.com']
    """
    if not raw or not raw.strip():
        return []
    parts = re.split(delimiters, raw)
    return [p.strip() for p in parts if p.strip()]


def truncate(text: str, max_len: int = 200, suffix: str = "…") -> str:
    """Truncate text to max_len characters, appending suffix if cut."""
    if len(text) <= max_len:
        return text
    return text[: max_len - len(suffix)] + suffix


def slugify(text: str) -> str:
    """
    Convert a string to a lowercase slug (letters, digits, hyphens only).
    Used for IDs and log keys.
    """
    s = text.lower().strip()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s_]+", "-", s)
    s = re.sub(r"-+", "-", s)
    return s.strip("-")


# ─────────────────────────────────────────────────────────────────────────────
# List utilities
# ─────────────────────────────────────────────────────────────────────────────

def deduplicate_preserving_order(items: list[Any]) -> list[Any]:
    """
    Remove duplicates from a list while preserving insertion order.
    Comparison is done via equality (works for strings, ints, etc.).
    """
    seen: set = set()
    result: list = []
    for item in items:
        key = item if not isinstance(item, dict) else json.dumps(item, sort_keys=True)
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result


def flatten(nested: list[list[Any]]) -> list[Any]:
    """Flatten one level of nesting in a list."""
    return [item for sublist in nested for item in sublist]


# ─────────────────────────────────────────────────────────────────────────────
# Dict utilities
# ─────────────────────────────────────────────────────────────────────────────

def deep_get(d: dict, *keys: str, default: Any = None) -> Any:
    """
    Safely navigate a nested dict by key path.

    Example
    -------
    >>> deep_get({"a": {"b": 1}}, "a", "b")
    1
    >>> deep_get({}, "a", "b", default=0)
    0
    """
    current = d
    for key in keys:
        if not isinstance(current, dict):
            return default
        current = current.get(key, default)
        if current is default:
            return default
    return current


def merge_dicts_non_null(*dicts: dict[str, Any]) -> dict[str, Any]:
    """
    Merge multiple dicts left-to-right; later dicts only overwrite if their
    value is non-None and non-empty.
    """
    result: dict[str, Any] = {}
    for d in dicts:
        for k, v in d.items():
            if v is not None and v != "" and v != [] and v != {}:
                result[k] = v
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Timing / profiling decorator
# ─────────────────────────────────────────────────────────────────────────────

def timed(label: str | None = None) -> Callable[[F], F]:
    """
    Decorator that logs execution time of a function.

    Usage
    -----
    @timed("CSV parser")
    def parse_csv(...): ...
    """
    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            name = label or func.__qualname__
            start = time.perf_counter()
            try:
                result = func(*args, **kwargs)
                elapsed = time.perf_counter() - start
                logger.debug("%s completed in %.3fs", name, elapsed)
                return result
            except Exception:
                elapsed = time.perf_counter() - start
                logger.debug("%s failed after %.3fs", name, elapsed)
                raise
        return wrapper  # type: ignore[return-value]
    return decorator


# ─────────────────────────────────────────────────────────────────────────────
# File utilities
# ─────────────────────────────────────────────────────────────────────────────

def write_json(data: Any, path: str | Path, indent: int = 2, ensure_ascii: bool = False) -> None:
    """
    Write data as pretty-printed JSON to a file, creating parent dirs as needed.
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=indent, ensure_ascii=ensure_ascii, default=str)
    logger.info("Wrote %s", p)


def ensure_dir(path: str | Path) -> Path:
    """Create directory (and parents) if it doesn't exist. Returns Path."""
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p
