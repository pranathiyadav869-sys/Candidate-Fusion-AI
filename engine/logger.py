# """
# engine/logger.py
# ----------------
# Centralized logging configuration for CandidateFusion.

# Creates:
# - Console logger
# - File logger
# - Execution timer
# """

# from __future__ import annotations

# import logging
# import os
# import time
# from functools import wraps

# LOG_DIR = "logs"
# LOG_FILE = "pipeline.log"


# def setup_logger(name: str = "CandidateFusion") -> logging.Logger:
#     """
#     Configure application logger.
#     """

#     os.makedirs(LOG_DIR, exist_ok=True)

#     logger = logging.getLogger(name)

#     if logger.handlers:
#         return logger

#     logger.setLevel(logging.DEBUG)

#     formatter = logging.Formatter(
#         "[%(asctime)s] %(levelname)s | %(name)s | %(message)s",
#         datefmt="%Y-%m-%d %H:%M:%S",
#     )

#     # Console Handler
#     console_handler = logging.StreamHandler()
#     console_handler.setLevel(logging.INFO)
#     console_handler.setFormatter(formatter)

#     # File Handler
#     file_handler = logging.FileHandler(
#         os.path.join(LOG_DIR, LOG_FILE),
#         encoding="utf-8",
#     )
#     file_handler.setLevel(logging.DEBUG)
#     file_handler.setFormatter(formatter)

#     logger.addHandler(console_handler)
#     logger.addHandler(file_handler)

#     logger.propagate = False

#     return logger


# logger = setup_logger()


# def log_execution(func):
#     """
#     Decorator to log execution time.
#     """

#     @wraps(func)
#     def wrapper(*args, **kwargs):
#         start = time.perf_counter()

#         logger.info(f"Starting {func.__name__}")

#         try:
#             result = func(*args, **kwargs)
#         except Exception as e:
#             logger.exception(f"{func.__name__} failed: {e}")
#             raise

#         elapsed = time.perf_counter() - start

#         logger.info(f"{func.__name__} completed in {elapsed:.3f} seconds")

#         return result

#     return wrapper


"""
engine/logger.py
-----------------
Centralized logging configuration for CandidateFusion.

Design Decision: A single `setup_logging()` call configures the root
logger once, at process start, in main.py. Every module in the project
already does `logger = logging.getLogger(__name__)` at import time, so
no other file needs to change — they simply inherit whatever handlers
and level this function attaches to the root logger.

This module deliberately reuses the constants already defined in
utils/constants.py (LOG_FORMAT, LOG_DATE_FORMAT, DEFAULT_LOG_LEVEL,
LOG_FILE) rather than redefining them, so there is a single source of
truth for log formatting across the project.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from utils.constants import (
    DEFAULT_LOG_LEVEL,
    LOG_DATE_FORMAT,
    LOG_FILE,
    LOG_FORMAT,
    PROJECT_ROOT,
)

_configured = False


def setup_logging(
    level: str | None = None,
    log_file: str | Path | None = None,
    console: bool = True,
) -> logging.Logger:
    """
    Configure the root logger for the whole pipeline.

    Idempotent: calling this more than once (e.g. in tests that import
    main multiple times) will not duplicate handlers.

    Parameters
    ----------
    level    : logging level name (e.g. "DEBUG", "INFO"). Defaults to
               utils.constants.DEFAULT_LOG_LEVEL.
    log_file : path to the log file. Defaults to PROJECT_ROOT / LOG_FILE
               (matching utils.constants.LOG_FILE).
    console  : whether to also log to stdout.

    Returns
    -------
    logging.Logger
        The configured root logger.
    """
    global _configured

    root_logger = logging.getLogger()

    if _configured:
        return root_logger

    level_name = (level or DEFAULT_LOG_LEVEL).upper()
    resolved_level = getattr(logging, level_name, logging.INFO)
    root_logger.setLevel(resolved_level)

    formatter = logging.Formatter(fmt=LOG_FORMAT, datefmt=LOG_DATE_FORMAT)

    resolved_log_file = Path(log_file) if log_file else (PROJECT_ROOT / LOG_FILE)
    resolved_log_file.parent.mkdir(parents=True, exist_ok=True)

    file_handler = logging.FileHandler(resolved_log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    if console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        # Console stays at INFO+ even in DEBUG mode to avoid flooding the
        # terminal; full detail still goes to the log file.
        console_handler.setLevel(max(resolved_level, logging.INFO))
        root_logger.addHandler(console_handler)

    _configured = True
    root_logger.debug("Logging initialized: level=%s file=%s", level_name, resolved_log_file)
    return root_logger


def get_logger(name: str) -> logging.Logger:
    """Thin convenience wrapper, kept for symmetry with the rest of the
    codebase's `logger = logging.getLogger(__name__)` pattern."""
    return logging.getLogger(name)