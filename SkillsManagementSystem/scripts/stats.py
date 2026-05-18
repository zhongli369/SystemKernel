#!/usr/bin/env python3
"""
stats.py — Usage statistics tracker for Skill Package Manager.

Usage:
    python scripts/stats.py summary
    python scripts/stats.py log <event> [--pkg <name>] [--skill <name>] [--query "..."]
    python scripts/stats.py recent [--n 10]
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = SCRIPT_DIR / "data"
STATS_PATH = DATA_DIR / "usage_stats.json"

DEFAULT_STATS = {
    "version": "1.0.0",
    "created": "",
    "counts": {
        "install": 0,
        "uninstall": 0,
        "search": 0,
        "register": 0,
        "find-skill": 0,
    },
    "events": [],
}

VALID_EVENTS = {"install", "uninstall", "search", "register", "find-skill"}


def load_stats():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not STATS_PATH.exists():
        default = dict(DEFAULT_STATS)
        default["created"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        STATS_PATH.write_text(
            json.dumps(default, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        print("[INFO] Created default usage_stats.json")
        return default
    try:
        return json.loads(STATS_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"[ERROR] Corrupted usage_stats.json: {e}")
        sys.exit(1)


def save_stats(stats):
    tmp = str(STATS_PATH) + ".tmp"
    Path(tmp).write_text(
        json.dumps(stats, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    Path(tmp).replace(STATS_PATH)


def log_event(event_type, pkg=None, skill=None, query=None):
    if event_type not in VALID_EVENTS:
        print(f"[ERROR] Invalid event type: {event_type}")
        return None

    stats = load_stats()
    event = {
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "event_type": event_type,
    }
    details = {}
    if pkg:
        details["package"] = pkg
    if skill:
        details["skill"] = skill
    if query:
        details["query"] = query
    if details:
        event["details"] = details

    stats["events"].append(event)
    stats["counts"][event_type] += 1
    save_stats(stats)
    print(f"[INFO] Event recorded: {event_type}" + (f" (package: {pkg})" if pkg else ""))
    return event


def get_summary():
    stats = load_stats()
    total = sum(stats["counts"].values())
    return {
        "counts": stats["counts"],
        "total_events": total,
        "created": stats.get("created", "unknown"),
        "last_event": stats["events"][-1]["timestamp"] if stats["events"] else "none",
    }


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/stats.py <command> [options]", file=sys.stderr)
        print("  summary              Show usage summary", file=sys.stderr)
        print("  log <event>          Record an event", file=sys.stderr)
        print("  recent [--n N]       Show recent events", file=sys.stderr)
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "summary":
        s = get_summary()
        print("=== Usage Summary ===")
        for ev, count in s["counts"].items():
            print(f"  {ev:12s} : {count}")
        print(f"  {'total':12s} : {s['total_events']}")
        print(f"  created: {s['created']}")
        print(f"  last:    {s['last_event']}")

    elif cmd == "log":
        if len(sys.argv) < 3:
            print("[ERROR] log requires event type", file=sys.stderr)
            sys.exit(1)
        event_type = sys.argv[2]
        pkg = None
        skill = None
        query = None
        args = sys.argv[3:]
        i = 0
        while i < len(args):
            if args[i] == "--pkg" and i + 1 < len(args):
                pkg = args[i + 1]
                i += 2
            elif args[i] == "--skill" and i + 1 < len(args):
                skill = args[i + 1]
                i += 2
            elif args[i] == "--query" and i + 1 < len(args):
                query = args[i + 1]
                i += 2
            else:
                i += 1
        log_event(event_type, pkg=pkg, skill=skill, query=query)

    elif cmd == "recent":
        n = 10
        args = sys.argv[2:]
        i = 0
        while i < len(args):
            if args[i] == "--n" and i + 1 < len(args):
                n = int(args[i + 1])
                i += 2
            else:
                i += 1
        stats = load_stats()
        events = stats["events"][-n:]
        if not events:
            print("[INFO] No events recorded yet")
        for ev in reversed(events):
            ts = ev["timestamp"]
            et = ev["event_type"]
            details = ev.get("details", {})
            detail_str = ", ".join(f"{k}={v}" for k, v in details.items())
            print(f"  {ts}  {et:12s}  {detail_str}")

    else:
        print(f"[ERROR] Unknown command: {cmd}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
