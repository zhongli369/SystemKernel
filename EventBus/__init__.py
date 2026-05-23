"""
EventBus/ — Deterministic Event Ingestion Layer (v1.0)

SystemKernel Phase 1: unified event entry point.

All events enter SystemKernel through EventBus. No task is created,
no skill is routed, no execution is triggered — except through this module.

Architecture:
  Source → normalize → validate → route → dispatch → TaskSystem

Key guarantees:
  - ZERO LLM calls in the entire pipeline
  - Deterministic: same event → same task every time
  - Pure rule-based routing (lookup tables only)
  - Every event is traceable from source to task

Usage:
    from EventBus import ingest, ingest_cli, ingest_github, ingest_filewatch

    # CLI event
    result = ingest_cli(["task", "create", "fix login bug"])

    # GitHub webhook event
    result = ingest_github(headers, body)

    # FileWatch event
    result = ingest_filewatch("CLAUDE.md", "changed")
"""

from EventBus.event_bus import (
    ingest,
    ingest_cli,
    ingest_github,
    ingest_filewatch,
    EventResult,
    register_source,
    list_sources,
    get_source,
)
from EventBus.event_schema import Event, validate, ALLOWED_EVENT_TYPES, ALLOWED_SOURCES, FILEWATCH_WHITELIST
from EventBus.event_router import route, RoutingDecision, get_routing_table

__all__ = [
    # Public API
    "ingest",
    "ingest_cli",
    "ingest_github",
    "ingest_filewatch",
    # Data types
    "Event",
    "EventResult",
    "RoutingDecision",
    # Inspection
    "validate",
    "route",
    "get_routing_table",
    "register_source",
    "list_sources",
    "get_source",
    # Constants
    "ALLOWED_EVENT_TYPES",
    "ALLOWED_SOURCES",
    "FILEWATCH_WHITELIST",
]
