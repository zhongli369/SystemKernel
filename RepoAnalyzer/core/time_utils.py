"""Centralized timestamp utility for RepoAnalyzer outputs."""
from datetime import datetime, timezone


def current_utc_iso8601() -> str:
    """Return current UTC time as ISO 8601 string with Z suffix."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
