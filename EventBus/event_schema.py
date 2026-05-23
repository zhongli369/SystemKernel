"""
event_schema.py — Unified Event Schema + Validation (v1.0)

ALL events entering SystemKernel MUST conform to this schema.
Validation is pure, deterministic, and stateless.

NO semantic interpretation. NO classification. NO content analysis.
This module ONLY checks structural validity.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
import uuid
import re


# ═══════════════════════════════════════════════════════════════════════════════
# Allowed values — closed sets, explicitly enumerated
# ═══════════════════════════════════════════════════════════════════════════════

ALLOWED_EVENT_TYPES: frozenset[str] = frozenset({
    "cli.task.create",
    "cli.task.start",
    "cli.task.complete",
    "cli.task.list",
    "github.issue.opened",
    "github.issue.closed",
    "github.pr.opened",
    "github.pr.merged",
    "github.pr.closed",
    "github.push",
    "file.changed",
    "file.created",
    "file.deleted",
})

ALLOWED_SOURCES: frozenset[str] = frozenset({
    "cli",
    "github",
    "filewatch",
})

# Whitelist: files that trigger task creation when changed
FILEWATCH_WHITELIST: frozenset[str] = frozenset({
    "CLAUDE.md",
    "registry.json",
    "manifest.json",
    ".claude/settings.json",
    ".claude/settings.local.json",
})


# ═══════════════════════════════════════════════════════════════════════════════
# Event data type (frozen)
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class Event:
    """A normalized, validated event entering the SystemKernel pipeline.

    Immutable. Created once at ingestion, never modified.
    """
    event_id: str
    event_type: str
    source: str
    payload: dict
    timestamp: str

    def summary(self) -> str:
        return f"[{self.source}] {self.event_type} ({self.event_id[:8]}...)"


# ═══════════════════════════════════════════════════════════════════════════════
# Validation errors
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class ValidationError:
    """A structural validation failure. NOT a semantic judgment."""
    field: str
    value: str
    reason: str

    def __str__(self) -> str:
        return f"ValidationError({self.field}): {self.reason} (got: {self.value!r})"


# ═══════════════════════════════════════════════════════════════════════════════
# Validation — pure function, zero intelligence
# ═══════════════════════════════════════════════════════════════════════════════

def _is_valid_event_id(value: str) -> bool:
    """UUID format check only — no semantic meaning."""
    if not value or not isinstance(value, str):
        return False
    try:
        uuid.UUID(value)
        return True
    except (ValueError, AttributeError):
        return False


def _is_valid_timestamp(value: str) -> bool:
    """ISO-8601 format check only — no timezone interpretation."""
    if not value or not isinstance(value, str):
        return False
    pattern = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$"
    return bool(re.match(pattern, value))


def validate(event_data: dict) -> tuple[Optional[Event], list[ValidationError]]:
    """Validate and normalize raw event data into an Event.

    Pure function. No side effects. No semantic analysis.

    Args:
        event_data: Raw event dict from any source.

    Returns:
        (Event, []) if valid.
        (None, [ValidationError, ...]) if invalid.
    """
    errors: list[ValidationError] = []

    # Required fields
    event_id = event_data.get("event_id", "")
    event_type = str(event_data.get("event_type", ""))
    source = str(event_data.get("source", ""))
    payload = event_data.get("payload", {})
    timestamp = event_data.get("timestamp", "")

    # event_id: must be valid UUID
    if not event_id:
        event_id = str(uuid.uuid4())
    elif not _is_valid_event_id(event_id):
        errors.append(ValidationError(
            "event_id", event_id,
            "Must be a valid UUID or empty (auto-generated)"
        ))

    # event_type: must be in allowed set
    if event_type not in ALLOWED_EVENT_TYPES:
        errors.append(ValidationError(
            "event_type", event_type,
            f"Must be one of: {', '.join(sorted(ALLOWED_EVENT_TYPES))}"
        ))

    # source: must be in allowed set
    if source not in ALLOWED_SOURCES:
        errors.append(ValidationError(
            "source", source,
            f"Must be one of: {', '.join(sorted(ALLOWED_SOURCES))}"
        ))

    # payload: must be dict
    if not isinstance(payload, dict):
        errors.append(ValidationError(
            "payload", str(type(payload)),
            "Must be a dict"
        ))
        payload = {}

    # timestamp: must be ISO-8601
    if not timestamp:
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    elif not _is_valid_timestamp(timestamp):
        errors.append(ValidationError(
            "timestamp", timestamp,
            "Must be ISO-8601 (e.g. 2026-05-23T16:00:00Z)"
        ))

    if errors:
        return None, errors

    return Event(
        event_id=event_id,
        event_type=event_type,
        source=source,
        payload=payload,
        timestamp=timestamp,
    ), []


# ═══════════════════════════════════════════════════════════════════════════════
# Normalize helpers — raw source data → standard event dict
# ═══════════════════════════════════════════════════════════════════════════════

def normalize_cli(argv: list[str]) -> dict:
    """Normalize CLI arguments into a standard event dict.

    Deterministic. No NLP. No intent parsing.

    Args:
        argv: Command-line arguments, e.g. ['task', 'create', 'fix login bug']

    Returns:
        Raw event dict ready for validate().
    """
    if len(argv) < 2:
        return {
            "event_id": str(uuid.uuid4()),
            "event_type": "cli.task.list",
            "source": "cli",
            "payload": {"args": argv, "command": "list"},
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }

    command = argv[1].lower()
    args = argv[2:] if len(argv) > 2 else []

    # Deterministic command → event_type mapping
    cmd_map = {
        "create": "cli.task.create",
        "start":  "cli.task.start",
        "complete": "cli.task.complete",
        "done":   "cli.task.complete",
        "list":   "cli.task.list",
        "show":   "cli.task.list",
    }

    event_type = cmd_map.get(command, "cli.task.create")

    return {
        "event_id": str(uuid.uuid4()),
        "event_type": event_type,
        "source": "cli",
        "payload": {
            "args": args,
            "command": command,
            "title": " ".join(args) if args else "",
        },
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def normalize_github_webhook(headers: dict, body: dict) -> dict:
    """Normalize a GitHub webhook payload into a standard event dict.

    Deterministic. Only extracts structured fields — no content analysis.

    Args:
        headers: HTTP headers from webhook request.
        body: JSON body from webhook request.

    Returns:
        Raw event dict ready for validate().
    """
    event_header = headers.get("X-GitHub-Event", "")
    action = body.get("action", "")

    # Deterministic GitHub event → internal event_type mapping
    event_map = {
        ("issues", "opened"): "github.issue.opened",
        ("issues", "closed"): "github.issue.closed",
        ("pull_request", "opened"): "github.pr.opened",
        ("pull_request", "closed"): "github.pr.closed",
        ("pull_request", "merged"): "github.pr.merged",  # action=closed + merged=true
        ("push", ""): "github.push",
    }

    # Check merged status for PR close events
    if event_header == "pull_request" and action == "closed":
        if body.get("pull_request", {}).get("merged", False):
            event_type = "github.pr.merged"
        else:
            event_type = "github.pr.closed"
    else:
        event_type = event_map.get((event_header, action), f"github.{event_header}")

    # Extract deterministic payload fields — no content parsing
    payload = {
        "repo": body.get("repository", {}).get("full_name", ""),
        "sender": body.get("sender", {}).get("login", ""),
    }

    if event_header == "issues":
        payload["issue_number"] = body.get("issue", {}).get("number")
        payload["issue_title"] = body.get("issue", {}).get("title", "")
        payload["issue_body"] = body.get("issue", {}).get("body", "")[:500]

    elif event_header == "pull_request":
        payload["pr_number"] = body.get("pull_request", {}).get("number")
        payload["pr_title"] = body.get("pull_request", {}).get("title", "")
        payload["pr_body"] = body.get("pull_request", {}).get("body", "")[:500]
        payload["base_branch"] = body.get("pull_request", {}).get("base", {}).get("ref", "")
        payload["head_branch"] = body.get("pull_request", {}).get("head", {}).get("ref", "")

    elif event_header == "push":
        payload["ref"] = body.get("ref", "")
        payload["commits"] = [
            {"id": c.get("id", ""), "message": c.get("message", "")}
            for c in body.get("commits", [])[:10]
        ]

    return {
        "event_id": str(uuid.uuid4()),
        "event_type": event_type,
        "source": "github",
        "payload": payload,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def normalize_filewatch(path: str, change_type: str) -> dict:
    """Normalize a file watch event into a standard event dict.

    Deterministic. Only checks filename against whitelist — no content reading.

    Args:
        path: Relative or absolute path to the changed file.
        change_type: "created" | "changed" | "deleted"

    Returns:
        Raw event dict ready for validate().
    """
    import os
    filename = os.path.basename(path)

    change_map = {
        "created": "file.created",
        "changed": "file.changed",
        "deleted": "file.deleted",
        "modified": "file.changed",
    }

    event_type = change_map.get(change_type, "file.changed")

    return {
        "event_id": str(uuid.uuid4()),
        "event_type": event_type,
        "source": "filewatch",
        "payload": {
            "path": path,
            "filename": filename,
            "change_type": change_type,
            "whitelisted": filename in FILEWATCH_WHITELIST,
        },
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
