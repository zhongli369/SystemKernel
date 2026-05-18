#!/usr/bin/env python3
"""Minimal end-to-end example of the SystemKernel execution flow.

Demonstrates the standard sequence:
  1. Route an intent → skill via Adapter
  2. Resolve to a capability
  3. Execute + verify via ExecutionLoop
  4. Print the result

No modifications, no side effects. Run from the SystemKernel directory:

    cd F:\\Claude\\SystemKernel
    python examples/basic_usage.py
"""

import sys
from pathlib import Path

# Ensure SystemKernel root is on sys.path
_WORKSPACE = str(Path(__file__).resolve().parent.parent)
if _WORKSPACE not in sys.path:
    sys.path.insert(0, _WORKSPACE)

from SkillsManagementSystem.core.adapter import (
    resolve,
    get_registry_info,
    get_skill_metadata,
    CapabilityRequest,
)
from ExecutionLoop.loop import (
    run,
    ExecutionRequest,
    ResolvedCapability,
    ExecutionResult,
)


def demo_routing():
    """Step 1: Route an intent to a skill via Adapter."""
    print("=" * 52)
    print("  STEP 1 — Adapter.resolve()")
    print("=" * 52)

    request = CapabilityRequest(
        intent="refactor",
        context="reduce coupling in utils/helpers.py",
        source="demo-script",
    )

    binding = resolve(request)

    print(f"  Intent:    {request.intent}")
    print(f"  Context:   {request.context}")
    print(f"  Skill:     {binding.skill_id or '(no match)'}")
    print(f"  Confidence: {binding.confidence:.2f}")
    print(f"  Reason:    {binding.reason}")
    print(f"  Alts:      {', '.join(binding.alternatives) if binding.alternatives else '(none)'}")
    print()

    return binding


def demo_execution(binding):
    """Step 2: Execute via ExecutionLoop with verification."""
    print("=" * 52)
    print("  STEP 2 — ExecutionLoop.run()")
    print("=" * 52)

    if not binding.skill_id:
        print("  (skipped — no skill resolved)")
        return None

    capability = ResolvedCapability(
        skill_id=binding.skill_id,
        confidence=binding.confidence,
    )

    # Use ruff for lint check if available, otherwise a lightweight check
    verification = ("lint",)  # 'ruff check .'

    result = run(ExecutionRequest(
        capability=capability,
        target="utils/helpers.py",
        verification=verification,
    ))

    print(f"  Success:     {result.success}")
    print(f"  Corrected:   {result.corrected}")
    print(f"  Attempt:     {result.attempt}/2")
    print(f"  Can correct: {result.correction_remaining}")
    print()

    return result


def demo_metadata():
    """Step 3: Inspect the registry (read-only)."""
    print("=" * 52)
    print("  STEP 3 — Registry Inspection")
    print("=" * 52)

    info = get_registry_info()
    skills = info.get("all_skills", [])
    print(f"  Registered skills: {len(skills)}")
    for s in skills[:5]:
        print(f"    - {s.get('name', '?')}  ({s.get('package', '?')})")
    if len(skills) > 5:
        print(f"    ... and {len(skills) - 5} more")
    print()


def main():
    print()
    print("╔══════════════════════════════════════════════════════╗")
    print("║  SystemKernel — Basic Usage Demo                    ║")
    print("╚══════════════════════════════════════════════════════╝")
    print()

    binding = demo_routing()
    demo_execution(binding)
    demo_metadata()

    print("=" * 52)
    print("  Demo complete.")
    print("=" * 52)


if __name__ == "__main__":
    main()
