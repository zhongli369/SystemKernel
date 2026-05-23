"""
cli_source.py — CLI Event Source (v1.0)

Emits events from command-line invocation. The simplest event source.

PURELY an event emitter — no processing, no routing, no task creation.
All it does: parse argv → emit event dict.
"""

import sys
from typing import Optional


def listen(argv: Optional[list[str]] = None) -> dict:
    """Parse CLI arguments and emit a normalized event dict.

    This is an EVENT EMITTER only. It does NOT:
      - Create tasks
      - Route skills
      - Parse intent
      - Validate beyond basic structure

    Args:
        argv: Command-line arguments. Uses sys.argv[1:] if None.

    Returns:
        Raw event dict ready for EventBus.ingest().
    """
    if argv is None:
        argv = sys.argv[1:]

    from EventBus.event_schema import normalize_cli
    return normalize_cli(argv)


# ═══════════════════════════════════════════════════════════════════════════════
# CLI entry point — for direct invocation
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import json

    event_dict = listen()
    print(json.dumps(event_dict, indent=2, ensure_ascii=False))
