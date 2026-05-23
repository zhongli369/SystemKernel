"""
event_router.py — Deterministic Event → Task Routing Table (v1.0)

The ONLY decision point between an event arriving and a task being created.

Rules are:
  - Pure lookup tables — no AI, no ML, no semantic analysis
  - Exhaustive for all ALLOWED_EVENT_TYPES
  - Deterministic: same event_type → same task action every time

This module is the embodiment of "mechanical, not intelligent."
"""

from dataclasses import dataclass
from typing import Optional, Callable

from EventBus.event_schema import Event, FILEWATCH_WHITELIST


# ═══════════════════════════════════════════════════════════════════════════════
# Routing decision output
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class RoutingDecision:
    """What to do with an event. Immutable, auditable."""
    event_id: str
    action: str          # "create_task" | "start_task" | "complete_task" | "skip"
    title: str           # Task title (for create_task)
    priority: str        # "P0" | "P1" | "P2"
    reason: str          # Why this decision was made — for audit trail
    metadata: dict       # Additional task metadata


# ═══════════════════════════════════════════════════════════════════════════════
# Rule table — the ENTIRE routing intelligence
# ═══════════════════════════════════════════════════════════════════════════════

# Format: event_type → (action, priority, title_template)
# title_template uses {field} placeholders from event payload
_ROUTE_TABLE: dict[str, tuple[str, str, str]] = {

    # ── CLI events ──────────────────────────────────────────────────────────
    "cli.task.create": (
        "create_task", "P1",
        "{title}"  # title comes from CLI args
    ),
    "cli.task.start": (
        "start_task", "P1",
        "{title}"
    ),
    "cli.task.complete": (
        "complete_task", "P1",
        "{title}"
    ),
    "cli.task.list": (
        "skip", "P1",
        ""  # List is read-only — no task creation
    ),

    # ── GitHub issue events ─────────────────────────────────────────────────
    "github.issue.opened": (
        "create_task", "P1",
        "[GitHub Issue #{issue_number}] {issue_title}"
    ),
    "github.issue.closed": (
        "create_task", "P2",
        "[GitHub Issue #{issue_number} closed] {issue_title}"
    ),

    # ── GitHub PR events ────────────────────────────────────────────────────
    "github.pr.opened": (
        "create_task", "P0",
        "[PR #{pr_number}] {pr_title}"
    ),
    "github.pr.merged": (
        "create_task", "P1",
        "[PR #{pr_number} merged] {pr_title}"
    ),
    "github.pr.closed": (
        "create_task", "P2",
        "[PR #{pr_number} closed (unmerged)] {pr_title}"
    ),

    # ── GitHub push ─────────────────────────────────────────────────────────
    "github.push": (
        "create_task", "P2",
        "[Push to {ref}] {num_commits} commit(s)"
    ),

    # ── FileWatch events ────────────────────────────────────────────────────
    "file.changed": (
        "create_task", "P1",
        "[File changed] {filename}"
    ),
    "file.created": (
        "create_task", "P1",
        "[File created] {filename}"
    ),
    "file.deleted": (
        "create_task", "P1",
        "[File deleted] {filename}"
    ),
}


# ═══════════════════════════════════════════════════════════════════════════════
# Title formatter — pure string interpolation, no AI
# ═══════════════════════════════════════════════════════════════════════════════

def _format_title(template: str, event: Event) -> str:
    """Fill title template with event payload fields.

    Pure string formatting. No NLP. No summarization. No content generation.

    Supported placeholders:
      {title}       — from payload.title
      {issue_number}— from payload.issue_number
      {issue_title} — from payload.issue_title
      {pr_number}   — from payload.pr_number
      {pr_title}    — from payload.pr_title
      {filename}    — from payload.filename
      {ref}         — from payload.ref
      {num_commits} — len(payload.commits)
    """
    p = event.payload
    result = template

    # Simple field substitution
    result = result.replace("{title}", str(p.get("title", "")))
    result = result.replace("{issue_number}", str(p.get("issue_number", "?")))
    result = result.replace("{issue_title}", str(p.get("issue_title", "")))
    result = result.replace("{pr_number}", str(p.get("pr_number", "?")))
    result = result.replace("{pr_title}", str(p.get("pr_title", "")))
    result = result.replace("{filename}", str(p.get("filename", "")))
    result = result.replace("{ref}", str(p.get("ref", "")))
    result = result.replace("{num_commits}", str(len(p.get("commits", []))))

    return result.strip()


# ═══════════════════════════════════════════════════════════════════════════════
# FileWatch gate — only whitelisted files create tasks
# ═══════════════════════════════════════════════════════════════════════════════

def _is_filewatch_actionable(event: Event) -> bool:
    """FileWatch events only trigger tasks for whitelisted files.

    Pure membership check. No content analysis.
    """
    if event.source != "filewatch":
        return True  # Non-filewatch events always pass

    whitelisted = event.payload.get("whitelisted", False)
    if not whitelisted:
        # Check filename directly as fallback
        filename = event.payload.get("filename", "")
        return filename in FILEWATCH_WHITELIST

    return True


# ═══════════════════════════════════════════════════════════════════════════════
# Public API — the ONLY routing function
# ═══════════════════════════════════════════════════════════════════════════════

def route(event: Event) -> RoutingDecision:
    """Map an event to a task action.

    THE ONLY ROUTING FUNCTION IN EVENTBUS.
    Pure lookup. Deterministic. No side effects.

    Args:
        event: A validated Event.

    Returns:
        RoutingDecision with action, title, priority, and reason.
        action="skip" means no task should be created.

    Guarantees:
        - Same event → same RoutingDecision every time
        - No external state read (except FILEWATCH_WHITELIST which is frozen)
        - No API calls, no LLM, no disk access
    """
    event_type = event.event_type
    rule = _ROUTE_TABLE.get(event_type)

    if rule is None:
        # Unknown event type — skip safely
        return RoutingDecision(
            event_id=event.event_id,
            action="skip",
            title="",
            priority="P2",
            reason=f"No routing rule for event_type: {event_type}",
            metadata={"event_type": event_type},
        )

    action, priority, title_template = rule

    # FileWatch gate: non-whitelisted files are silently skipped
    if not _is_filewatch_actionable(event):
        return RoutingDecision(
            event_id=event.event_id,
            action="skip",
            title="",
            priority="P2",
            reason=f"File '{event.payload.get('filename', '')}' not in whitelist",
            metadata={"filename": event.payload.get("filename", "")},
        )

    # If the rule says skip, honor it
    if action == "skip":
        return RoutingDecision(
            event_id=event.event_id,
            action="skip",
            title="",
            priority="P2",
            reason=f"Event type '{event_type}' is read-only (no task creation)",
            metadata={"event_type": event_type},
        )

    # Build task title
    title = _format_title(title_template, event)
    if not title:
        title = f"[{event.source}] {event_type}"

    return RoutingDecision(
        event_id=event.event_id,
        action=action,
        title=title,
        priority=priority,
        reason=(
            f"Matched rule: {event_type} → {action} "
            f"(priority={priority}, source={event.source})"
        ),
        metadata={
            "event_type": event_type,
            "source": event.source,
            "timestamp": event.timestamp,
            "payload": event.payload,
        },
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Inspection — for debugging / audit
# ═══════════════════════════════════════════════════════════════════════════════

def get_routing_table() -> dict:
    """Return a copy of the routing table (read-only inspection)."""
    return dict(_ROUTE_TABLE)
