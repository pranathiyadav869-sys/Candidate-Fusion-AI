"""
parsers/github_parser.py
------------------------
Fetches and parses a GitHub user's public profile via the GitHub REST API.

Design Decisions:
- PyGithub is the primary client; requests is used as a fallback when a
  token is not available (unauthenticated rate limit: 60 req/hr).
- Extracts languages from the top N public repos to infer technical skills.
- Returns a canonical dict compatible with the merge engine. GitHub data
  fills in skills and links but is not authoritative for name/email.
- All network errors (404, rate limit, timeout) are caught; partial data
  is returned when possible so the pipeline can still proceed.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any

from utils.constants import (
    GITHUB_API_BASE_URL,
    GITHUB_MAX_LANGUAGES,
    GITHUB_MAX_REPOS,
    SOURCE_GITHUB,
)
from utils.exceptions import GitHubParseError
from utils.helpers import generate_candidate_id

logger = logging.getLogger(__name__)

# Language → canonical skill name (skills.json covers the rest)
_LANGUAGE_TO_SKILL: dict[str, str] = {
    "Python": "Python",
    "JavaScript": "JavaScript",
    "TypeScript": "TypeScript",
    "Java": "Java",
    "C++": "C++",
    "C#": "C#",
    "Go": "Go",
    "Rust": "Rust",
    "Ruby": "Ruby",
    "Scala": "Scala",
    "Kotlin": "Kotlin",
    "Swift": "Swift",
    "R": "R",
    "MATLAB": "MATLAB",
    "Shell": "Shell Scripting",
    "PowerShell": "PowerShell",
    "PHP": "PHP",
    "Dart": "Dart",
    "Lua": "Lua",
    "Haskell": "Haskell",
    "Elixir": "Elixir",
    "Erlang": "Erlang",
    "Clojure": "Clojure",
    "Julia": "Julia",
    "HTML": "HTML",
    "CSS": "CSS",
    "Jupyter Notebook": "Python",  # map to Python
}


# ---------------------------------------------------------------------------
# PyGithub strategy
# ---------------------------------------------------------------------------

def _fetch_via_pygithub(username: str, token: str | None) -> dict[str, Any]:
    """
    Fetch GitHub profile using the PyGithub library.
    Raises GitHubParseError on unrecoverable errors.
    """
    try:
        from github import Github, GithubException, UnknownObjectException, RateLimitExceededException
    except ImportError:
        raise GitHubParseError(username, "PyGithub is not installed (pip install PyGithub)")

    gh = Github(token) if token else Github()

    try:
        user = gh.get_user(username)
        # Trigger lazy load to detect 404 early
        _ = user.name
    except UnknownObjectException:
        raise GitHubParseError(username, f"User '{username}' not found on GitHub (404)")
    except RateLimitExceededException:
        reset_time = gh.get_rate_limit().core.reset
        logger.warning("GitHub rate limit exceeded. Resets at %s", reset_time)
        raise GitHubParseError(username, "GitHub API rate limit exceeded")
    except GithubException as exc:
        raise GitHubParseError(username, f"GitHub API error: {exc.status} {exc.data}")
    except Exception as exc:
        raise GitHubParseError(username, f"Unexpected error fetching user: {exc}")

    # ── Fetch repos ────────────────────────────────────────────────────────
    repos_data: list[dict[str, Any]] = []
    languages_count: dict[str, int] = {}

    try:
        repos = user.get_repos(type="public", sort="updated")
        count = 0
        for repo in repos:
            if count >= GITHUB_MAX_REPOS:
                break
            if repo.fork:
                continue  # skip forks – they don't reflect the candidate's skills
            repos_data.append({
                "name": repo.name,
                "description": repo.description,
                "url": repo.html_url,
                "stars": repo.stargazers_count,
                "language": repo.language,
            })
            if repo.language:
                languages_count[repo.language] = (
                    languages_count.get(repo.language, 0) + 1
                )
            count += 1
    except Exception as exc:
        logger.warning("Could not fetch repos for %s: %s", username, exc)

    return _build_canonical(user, repos_data, languages_count, username)


# ---------------------------------------------------------------------------
# Requests fallback strategy
# ---------------------------------------------------------------------------

def _fetch_via_requests(username: str, token: str | None) -> dict[str, Any]:
    """
    Fetch GitHub profile using raw HTTP requests as a fallback.
    Useful when PyGithub is unavailable or for lightweight usage.
    """
    try:
        import requests
    except ImportError:
        raise GitHubParseError(username, "requests library is not installed")

    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    def _get(url: str) -> dict | list:
        try:
            resp = requests.get(url, headers=headers, timeout=10)
        except requests.exceptions.ConnectionError as exc:
            raise GitHubParseError(username, f"Network error: {exc}") from exc
        except requests.exceptions.Timeout:
            raise GitHubParseError(username, "Request timed out")

        if resp.status_code == 404:
            raise GitHubParseError(username, f"User '{username}' not found on GitHub (404)")
        if resp.status_code == 403:
            reset = resp.headers.get("X-RateLimit-Reset", "unknown")
            raise GitHubParseError(
                username, f"GitHub rate limit hit (resets at {reset})"
            )
        if not resp.ok:
            raise GitHubParseError(
                username, f"GitHub API returned {resp.status_code}"
            )
        return resp.json()

    user_data = _get(f"{GITHUB_API_BASE_URL}/users/{username}")
    if not isinstance(user_data, dict):
        raise GitHubParseError(username, "Unexpected response format from GitHub API")

    # ── Repos ─────────────────────────────────────────────────────────────
    repos_data: list[dict[str, Any]] = []
    languages_count: dict[str, int] = {}

    try:
        repos = _get(
            f"{GITHUB_API_BASE_URL}/users/{username}/repos"
            f"?type=public&sort=updated&per_page={GITHUB_MAX_REPOS}"
        )
        if isinstance(repos, list):
            for repo in repos:
                if repo.get("fork"):
                    continue
                repos_data.append({
                    "name": repo.get("name"),
                    "description": repo.get("description"),
                    "url": repo.get("html_url"),
                    "stars": repo.get("stargazers_count", 0),
                    "language": repo.get("language"),
                })
                lang = repo.get("language")
                if lang:
                    languages_count[lang] = languages_count.get(lang, 0) + 1
    except GitHubParseError:
        logger.warning("Could not fetch repos for %s via requests", username)

    # Build a user-like namespace for _build_canonical
    class _User:
        name = user_data.get("name")
        login = user_data.get("login")
        email = user_data.get("email")
        bio = user_data.get("bio")
        blog = user_data.get("blog")
        location = user_data.get("location")
        company = user_data.get("company")
        html_url = user_data.get("html_url")
        followers = user_data.get("followers", 0)
        public_repos = user_data.get("public_repos", 0)
        avatar_url = user_data.get("avatar_url")

    return _build_canonical(_User(), repos_data, languages_count, username)


# ---------------------------------------------------------------------------
# Canonical dict builder
# ---------------------------------------------------------------------------

def _build_canonical(
    user: Any,
    repos_data: list[dict[str, Any]],
    languages_count: dict[str, int],
    username: str,
) -> dict[str, Any]:
    """Assemble the canonical dictionary from a fetched GitHub user object."""

    # ── Skills from languages ──────────────────────────────────────────────
    sorted_langs = sorted(languages_count.items(), key=lambda x: x[1], reverse=True)
    skill_names: list[str] = []
    for lang, _ in sorted_langs[:GITHUB_MAX_LANGUAGES]:
        canonical_skill = _LANGUAGE_TO_SKILL.get(lang, lang)
        if canonical_skill not in skill_names:
            skill_names.append(canonical_skill)

    # ── Links ─────────────────────────────────────────────────────────────
    profile_url = getattr(user, "html_url", None) or f"https://github.com/{username}"
    links: list[dict[str, str]] = [{"url": profile_url, "label": "GitHub"}]

    blog = getattr(user, "blog", None)
    if blog and blog.strip():
        blog_url = blog if blog.startswith("http") else f"https://{blog}"
        links.append({"url": blog_url, "label": "Portfolio"})

    # ── Contact ───────────────────────────────────────────────────────────
    emails: list[str] = []
    raw_email = getattr(user, "email", None)
    if raw_email:
        from engine.normalize import normalize_email
        ne = normalize_email(raw_email)
        if ne:
            emails.append(ne)

    # ── Location ──────────────────────────────────────────────────────────
    from engine.normalize import normalize_location, normalize_name
    location = normalize_location(getattr(user, "location", None))
    full_name = normalize_name(getattr(user, "name", None))

    # ── Candidate ID ──────────────────────────────────────────────────────
    seed = emails[0] if emails else username
    candidate_id = generate_candidate_id(seed)

    canonical: dict[str, Any] = {
        "candidate_id": candidate_id,
        "full_name": full_name,
        "emails": emails,
        "phones": [],
        "location": location,
        "headline": getattr(user, "bio", None),  # bio ≈ headline on GitHub
        "skills": skill_names,
        "links": links,
        "experience": [],       # GitHub doesn't expose structured experience
        "education": [],        # GitHub doesn't expose structured education
        "years_experience": None,
        # Extra GitHub-specific metadata (informational, not in core schema)
        "_github_username": getattr(user, "login", username),
        "_github_followers": getattr(user, "followers", 0),
        "_github_public_repos": getattr(user, "public_repos", 0),
        "_github_repos": repos_data,
        "_github_languages": dict(sorted_langs),
        "_source": SOURCE_GITHUB,
    }

    logger.info(
        "GitHub: parsed user=%s name=%r skills=%d repos=%d",
        username, full_name, len(skill_names), len(repos_data),
    )
    return canonical


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_github(username: str, token: str | None = None) -> dict[str, Any]:
    """
    Fetch and parse a GitHub user's public profile.

    Parameters
    ----------
    username : str
        GitHub username (e.g. "octocat").
    token : str | None
        Personal access token for higher rate limits (optional).
        If None, checks the GITHUB_TOKEN environment variable.

    Returns
    -------
    dict[str, Any]
        Canonical intermediate dictionary ready for the merge engine.

    Raises
    ------
    GitHubParseError
        On 404, rate limit, or unrecoverable network errors.
    """
    if not username or not username.strip():
        raise GitHubParseError("", "username must not be empty")

    username = username.strip().lstrip("@")
    token = token or os.environ.get("GITHUB_TOKEN")

    logger.info("Fetching GitHub profile for: %s", username)

    # Try PyGithub first, fall back to requests
    try:
        return _fetch_via_pygithub(username, token)
    except ImportError:
        logger.debug("PyGithub unavailable, falling back to requests")
        return _fetch_via_requests(username, token)
    except GitHubParseError:
        raise
    except Exception as exc:
        logger.debug("PyGithub failed (%s), trying requests fallback", exc)
        try:
            return _fetch_via_requests(username, token)
        except GitHubParseError:
            raise
        except Exception as exc2:
            raise GitHubParseError(username, f"All fetch strategies failed: {exc2}") from exc2
