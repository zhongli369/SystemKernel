"""
SystemKernel CLI — intelligence plane commands: context-plane, memory-intel,
workspace, agent-worker, skill-evolution, orchestrate.

Extracted from systemkernel.py during Phase 13D CLI Surface Compression.
All behavior preserved. No new capability added.
"""
from __future__ import annotations

import json as _json
import os
import sys

from v3.cli._helpers import ROOT


# ═══════════════════════════════════════════════════════════════════════
# Context engineering plane commands
# ═══════════════════════════════════════════════════════════════════════

def cmd_context_plane_plan(target: str, output: str = "", style: str = "markdown") -> int:
    """Plan a context pack through the Context Engineering Plane. No execution."""
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)

    from v3.external.context_plane import (
        plan_context_pack,
        default_context_budget_policy,
        validate_context_budget,
        BUDGET_PASS,
        BUDGET_REVIEW,
        BUDGET_BLOCKED,
    )

    policy = default_context_budget_policy()
    plan = plan_context_pack(target, output=output, style=style, policy=policy)
    budget = validate_context_budget(plan, policy)

    print("=" * 60)
    print("  SystemKernel v4.0 — Context Engineering Plane")
    print("=" * 60)
    print()
    print(f"  Adapter:              {plan.adapter_id}")
    print(f"  Target:               {plan.target_path}")
    print(f"  Output:               {plan.output_path}")
    print(f"  Style:                {plan.style}")
    print(f"  Estimated files:      {plan.estimated_files}")
    print(f"  Estimated size:       {plan.estimated_bytes:,} bytes")
    print(f"  Estimated tokens:     {plan.estimated_tokens:,}")
    print(f"  Budget status:        {plan.budget_status}")
    print(f"  Plan hash:            {plan.plan_hash}")

    if plan.command:
        print(f"\n  Planned command:")
        print(f"    {plan.command}")

    if budget.violations:
        print(f"\n  Budget Violations:")
        for v in budget.violations:
            print(f"    [BLOCKED] {v}")

    if budget.warnings:
        print(f"\n  Budget Warnings:")
        for w in budget.warnings:
            print(f"    [WARN] {w}")

    if plan.warnings:
        print(f"\n  Adapter Warnings:")
        for w in plan.warnings:
            if w not in budget.violations and w not in budget.warnings:
                print(f"    - {w}")

    print()
    if plan.budget_status == BUDGET_BLOCKED:
        return 1
    return 0


def cmd_context_plane_inspect(path: str) -> int:
    """Inspect an existing context pack through the Context Engineering Plane."""
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)

    from v3.external.context_plane import (
        inspect_context_pack,
        default_context_budget_policy,
        validate_context_budget,
    )

    policy = default_context_budget_policy()
    inspection = inspect_context_pack(path, policy=policy)
    budget = validate_context_budget(inspection, policy)

    print("=" * 60)
    print("  SystemKernel v4.0 — Context Engineering Plane")
    print("=" * 60)
    print()
    print(f"  Path:                 {inspection.output_path}")
    print(f"  Size:                 {inspection.size_bytes:,} bytes")
    print(f"  Lines:                {inspection.line_count:,}")
    print(f"  Token estimate:       {inspection.token_estimate:,}")
    print(f"  Included files:       {len(inspection.included_files)}")
    print(f"  Sections detected:    {len(inspection.detected_sections)}")
    print(f"  Sensitive hits:       {len(inspection.sensitive_pattern_hits)}")
    print(f"  Pack hash:            {inspection.pack_hash}")
    print(f"  Inspection hash:      {inspection.inspection_hash}")

    if inspection.sensitive_pattern_hits:
        print(f"\n  Sensitive Pattern Hits:")
        for hit in inspection.sensitive_pattern_hits:
            print(f"    [WARN] Pattern detected: {hit}")

    if budget.warnings:
        print(f"\n  Budget Warnings:")
        for w in budget.warnings:
            print(f"    [WARN] {w}")

    if inspection.detected_sections:
        print(f"\n  Sections ({len(inspection.detected_sections)}):")
        for s in inspection.detected_sections:
            print(f"    - {s}")

    if inspection.included_files:
        print(f"\n  Files ({len(inspection.included_files)}):")
        for f in inspection.included_files[:20]:
            print(f"    - {f}")
        if len(inspection.included_files) > 20:
            print(f"    ... and {len(inspection.included_files) - 20} more")

    print()
    return 0


def cmd_context_plane_evidence(path: str, output: str = "", target: str = "") -> int:
    """Build evidence bundle from an existing inspected context pack."""
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)

    from v3.external.context_plane import (
        plan_context_pack,
        inspect_context_pack,
        context_pack_to_evidence,
        build_context_engineering_report,
        write_context_report,
        default_context_budget_policy,
    )
    from v3.external.default_capabilities import build_default_registry

    policy = default_context_budget_policy()
    inspection = inspect_context_pack(path, policy=policy)
    plan = plan_context_pack(
        target=target or path, output=path, style="markdown", policy=policy,
    )

    registry = build_default_registry()
    evidence_bundle = context_pack_to_evidence(
        plan, inspection, registry_hash=registry.registry_hash,
    )
    report = build_context_engineering_report(plan, inspection, evidence_bundle)

    if not output:
        output = f"{path}.evidence.json"
    written = write_context_report(report, output)

    print("=" * 60)
    print("  SystemKernel v4.0 — Context Engineering Plane")
    print("=" * 60)
    print()
    print(f"  Evidence bundle:      {evidence_bundle.bundle_id}")
    print(f"  Evidence records:     {len(evidence_bundle.records)}")
    print(f"  Budget status:        {report.budget_status}")
    print(f"  Truth source:         {report.truth_source}")
    print(f"  Report hash:          {report.report_hash}")
    print(f"  Report written:       {written}")

    print()
    return 0


# ═══════════════════════════════════════════════════════════════════════
# Memory intelligence plane commands (Phase 5)
# ═══════════════════════════════════════════════════════════════════════

def cmd_memory_intel_profiles() -> int:
    """List all memory intelligence provider profiles and policy status."""
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)

    from v3.external.memory_intelligence_profiles import (
        get_all_profiles, evaluate_all_profiles,
    )
    from v3.external.memory_intelligence_policy import (
        default_memory_intelligence_policy,
    )

    policy = default_memory_intelligence_policy()
    profiles = get_all_profiles()
    statuses = evaluate_all_profiles(policy)

    print("=" * 60)
    print("  SystemKernel v4.0 — Memory Intelligence Plane")
    print("=" * 60)
    print()
    print(f"  Policy hash:           {policy.policy_hash}")
    print(f"  Allow LLM providers:   {policy.allow_llm_providers}")
    print(f"  Allow vector DB:       {policy.allow_vector_db_providers}")
    print(f"  Allow graph DB:        {policy.allow_graph_db_providers}")
    print(f"  Allow external svcs:   {policy.allow_external_services}")
    print()
    print(f"  {'Provider':<35} {'Type':<22} {'Allowed':<10} {'LLM':<6} {'VecDB':<7} {'Graph':<7} {'ExtSvc':<8}")
    print(f"  {'-'*35} {'-'*22} {'-'*10} {'-'*6} {'-'*7} {'-'*7} {'-'*8}")

    status_map = {s.provider_id: s for s in statuses}
    for p in profiles:
        st = status_map.get(p.provider_id)
        allowed = "YES" if (st and st.allowed) else "NO"
        print(f"  {p.provider_id:<35} {p.provider_type:<22} {allowed:<10} "
              f"{'Y' if p.requires_llm else 'N':<6} "
              f"{'Y' if p.requires_vector_db else 'N':<7} "
              f"{'Y' if p.requires_graph_db else 'N':<7} "
              f"{'Y' if p.external_service_required else 'N':<8}")

    print()
    print(f"  Profiles:              {len(profiles)}")
    print("  External integrations: NONE (Phase 5 is contract only)")
    print()
    return 0


def cmd_memory_intel_mock(provider_id: str = "deterministic_mock_memory",
                          signals: int = 3) -> int:
    """Generate deterministic mock memory intelligence result."""
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)

    from v3.external.memory_intelligence import (
        build_memory_intelligence_request,
        mock_memory_intelligence_result,
        validate_memory_intelligence_result,
        MODE_INSPECT_ONLY,
    )
    from v3.external.memory_intelligence_profiles import get_profile
    from v3.external.memory_intelligence_policy import (
        default_memory_intelligence_policy,
        validate_provider_against_policy,
    )

    provider = get_profile(provider_id)
    if provider is None:
        print(f"Unknown provider: {provider_id}")
        return 1

    policy = default_memory_intelligence_policy()
    allowed, reason = validate_provider_against_policy(provider, policy)

    print("=" * 60)
    print("  SystemKernel v4.0 — Memory Intelligence Plane")
    print("=" * 60)
    print()
    print(f"  Provider:              {provider.provider_id}")
    print(f"  Type:                  {provider.provider_type}")
    print(f"  Policy allowed:        {allowed}")
    if not allowed:
        print(f"  Reason:                {reason}")
        return 1

    request = build_memory_intelligence_request(
        provider_id=provider_id,
        input_record_refs=("mem-001", "mem-002", "mem-003"),
        input_evidence_refs=("ev-001",),
        mode=MODE_INSPECT_ONLY,
        max_signals=signals,
    )
    result = mock_memory_intelligence_result(request, signal_count=signals)
    validation = validate_memory_intelligence_result(result)

    print(f"  Request ID:            {request.request_id}")
    print(f"  Request mode:          {request.mode}")
    print(f"  Signals generated:     {len(result.signals)}")
    print(f"  Blocked:               {result.blocked}")
    print(f"  Truth source:          {result.truth_source}")
    print(f"  Result hash:           {result.result_hash}")
    print(f"  Validation:            {'PASS' if validation.valid else 'FAIL'}")

    if result.signals:
        print(f"\n  Signals:")
        for s in result.signals:
            print(f"    [{s.signal_type}] {s.signal_id[:8]} "
                  f"confidence={s.confidence:.1f} content='{s.content[:50]}...'")

    print()
    return 0


def cmd_memory_intel_evidence(provider_id: str = "deterministic_mock_memory",
                              output: str = "") -> int:
    """Build evidence bundle from mock memory intelligence result."""
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)

    from v3.external.memory_intelligence import (
        build_memory_intelligence_request,
        mock_memory_intelligence_result,
        memory_signals_to_evidence,
        build_memory_intelligence_report,
        MODE_INSPECT_ONLY,
    )
    from v3.external.memory_intelligence_profiles import get_profile
    from v3.external.memory_intelligence_policy import (
        default_memory_intelligence_policy,
        validate_provider_against_policy,
    )
    from v3.external.default_capabilities import build_default_registry

    provider = get_profile(provider_id)
    if provider is None:
        print(f"Unknown provider: {provider_id}")
        return 1

    policy = default_memory_intelligence_policy()
    allowed, reason = validate_provider_against_policy(provider, policy)

    if not allowed:
        print(f"Provider blocked: {reason}")
        return 1

    request = build_memory_intelligence_request(
        provider_id=provider_id,
        input_record_refs=("mem-001", "mem-002", "mem-003"),
        input_evidence_refs=("ev-001",),
        mode=MODE_INSPECT_ONLY,
        max_signals=5,
    )
    result = mock_memory_intelligence_result(request, signal_count=3)
    registry = build_default_registry()
    bundle = memory_signals_to_evidence(
        result, registry_hash=registry.registry_hash,
    )
    report = build_memory_intelligence_report(
        provider, request, result, bundle, policy_status="pass",
    )

    if not output:
        output = f"/tmp/memory_intel_evidence_{result.result_hash}.json"
    with open(output, "w", encoding="utf-8") as f:
        _json.dump(report.to_dict(), f, indent=2, ensure_ascii=False, sort_keys=True)

    print("=" * 60)
    print("  SystemKernel v4.0 — Memory Intelligence Plane")
    print("=" * 60)
    print()
    print(f"  Evidence bundle:       {bundle.bundle_id}")
    print(f"  Evidence records:      {len(bundle.records)}")
    print(f"  Truth source:          {bundle.truth_source}")
    print(f"  Policy status:         {report.policy_status}")
    print(f"  Report hash:           {report.report_hash}")
    print(f"  Report written:        {output}")

    print()
    return 0


# ═══════════════════════════════════════════════════════════════════════
# Workspace context plane commands (Phase 7)
# ═══════════════════════════════════════════════════════════════════════

def cmd_workspace_profiles() -> int:
    """List all workspace provider profiles and policy status."""
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)

    from v3.external.workspace_context_profiles import (
        get_all_profiles, evaluate_all_profiles,
    )
    from v3.external.workspace_context_policy import (
        default_workspace_context_policy,
    )

    policy = default_workspace_context_policy()
    profiles = get_all_profiles()
    statuses = evaluate_all_profiles(policy)

    print("=" * 60)
    print("  SystemKernel v4.0 — Workspace Context Plane")
    print("=" * 60)
    print()
    print(f"  Policy hash:            {policy.policy_hash}")
    print(f"  Allow IDE API:          {policy.allow_ide_api}")
    print(f"  Allow file watch:       {policy.allow_file_watch}")
    print(f"  Allow file read:        {policy.allow_file_read}")
    print(f"  Allow file write:       {policy.allow_file_write}")
    print(f"  Allow terminal:         {policy.allow_terminal_execution}")
    print(f"  Allow external svcs:    {policy.allow_external_services}")
    print(f"  Require redaction:      {policy.require_redaction}")
    print(f"  Require human approval: {policy.require_human_approval}")
    print()
    print(f"  {'Provider':<35} {'Type':<22} {'Allowed':<10} {'IDE':<6} {'Watch':<7} {'Read':<6} {'Write':<7} {'Term':<6} {'ExtSvc':<8}")
    print(f"  {'-'*35} {'-'*22} {'-'*10} {'-'*6} {'-'*7} {'-'*6} {'-'*7} {'-'*6} {'-'*8}")

    status_map = {s.provider_id: s for s in statuses}
    for p in profiles:
        st = status_map.get(p.provider_id)
        allowed = "YES" if (st and st.allowed) else "NO"
        print(f"  {p.provider_id:<35} {p.provider_type:<22} {allowed:<10} "
              f"{'Y' if p.requires_ide_api else 'N':<6} "
              f"{'Y' if p.requires_file_watch else 'N':<7} "
              f"{'Y' if p.can_read_files else 'N':<6} "
              f"{'Y' if p.can_write_files else 'N':<7} "
              f"{'Y' if p.can_execute_terminal else 'N':<6} "
              f"{'Y' if p.external_service_required else 'N':<8}")

    print()
    print(f"  Profiles:               {len(profiles)}")
    print("  External integrations:  NONE (Phase 7 is contract only)")
    print()
    return 0


def cmd_workspace_mock(provider_id: str = "deterministic_mock_workspace",
                       files: int = 3, diagnostics: int = 2) -> int:
    """Generate deterministic mock workspace snapshot."""
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)

    from v3.external.workspace_context import (
        mock_workspace_snapshot,
        validate_workspace_provider,
        validate_workspace_snapshot,
    )
    from v3.external.workspace_context_profiles import get_profile
    from v3.external.workspace_context_policy import (
        default_workspace_context_policy,
        validate_provider_against_policy,
    )

    provider = get_profile(provider_id)
    if provider is None:
        print(f"Unknown provider: {provider_id}")
        return 1

    policy = default_workspace_context_policy()
    allowed, reason = validate_provider_against_policy(provider, policy)

    print("=" * 60)
    print("  SystemKernel v4.0 — Workspace Context Plane")
    print("=" * 60)
    print()
    print(f"  Provider:               {provider.provider_id}")
    print(f"  Type:                   {provider.provider_type}")
    print(f"  Policy allowed:         {allowed}")
    if not allowed:
        print(f"  Reason:                 {reason}")
        return 1

    provider_valid = validate_workspace_provider(provider)
    snapshot = mock_workspace_snapshot(
        provider_id=provider_id,
        file_count=files,
        diagnostic_count=diagnostics,
    )
    snapshot_valid = validate_workspace_snapshot(snapshot)

    print(f"  Snapshot ID:            {snapshot.snapshot_id}")
    print(f"  Root path:              {snapshot.root_path}")
    print(f"  File refs:              {len(snapshot.file_refs)}")
    print(f"  Diagnostics:            {len(snapshot.diagnostics)}")
    print(f"  Open files:             {len(snapshot.open_files)}")
    if snapshot.active_file:
        print(f"  Active file:            {snapshot.active_file}")
    if snapshot.git_state:
        print(f"  Git branch:             {snapshot.git_state.branch}")
        print(f"  Modified count:         {snapshot.git_state.modified_count}")
    print(f"  Truth source:           {snapshot.truth_source}")
    print(f"  Snapshot hash:          {snapshot.snapshot_hash}")
    print(f"  Provider validation:    {'PASS' if provider_valid.valid else 'FAIL'}")
    print(f"  Snapshot validation:    {'PASS' if snapshot_valid.valid else 'FAIL'}")

    if snapshot.file_refs:
        print(f"\n  File Refs:")
        for ref in snapshot.file_refs:
            print(f"    {ref.path}  ({ref.language}, {ref.size_bytes:,} bytes)")

    if snapshot.diagnostics:
        print(f"\n  Diagnostics:")
        for d in snapshot.diagnostics:
            print(f"    [{d.severity}] {d.source}: {d.message_summary}")

    print()
    return 0


def cmd_workspace_evidence(provider_id: str = "deterministic_mock_workspace",
                           output: str = "") -> int:
    """Build evidence bundle from mock workspace snapshot."""
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)

    from v3.external.workspace_context import (
        mock_workspace_snapshot,
        workspace_snapshot_to_evidence,
        build_workspace_context_report,
    )
    from v3.external.workspace_context_profiles import get_profile
    from v3.external.workspace_context_policy import (
        default_workspace_context_policy,
        validate_provider_against_policy,
    )
    from v3.external.default_capabilities import build_default_registry

    provider = get_profile(provider_id)
    if provider is None:
        print(f"Unknown provider: {provider_id}")
        return 1

    policy = default_workspace_context_policy()
    allowed, reason = validate_provider_against_policy(provider, policy)

    if not allowed:
        print(f"Provider blocked: {reason}")
        return 1

    snapshot = mock_workspace_snapshot(provider_id=provider_id, file_count=3, diagnostic_count=2)
    registry = build_default_registry()
    bundle = workspace_snapshot_to_evidence(
        snapshot, registry_hash=registry.registry_hash,
    )
    report = build_workspace_context_report(
        provider, snapshot, bundle, policy_status="pass",
    )

    if not output:
        output = f"/tmp/workspace_evidence_{snapshot.snapshot_hash}.json"
    with open(output, "w", encoding="utf-8") as f:
        _json.dump(report.to_dict(), f, indent=2, ensure_ascii=False, sort_keys=True)

    print("=" * 60)
    print("  SystemKernel v4.0 — Workspace Context Plane")
    print("=" * 60)
    print()
    print(f"  Evidence bundle:        {bundle.bundle_id}")
    print(f"  Evidence records:       {len(bundle.records)}")
    print(f"  Truth source:           {bundle.truth_source}")
    print(f"  Policy status:          {report.policy_status}")
    print(f"  Report hash:            {report.report_hash}")
    print(f"  Report written:         {output}")

    print()
    return 0


# ═══════════════════════════════════════════════════════════════════════
# Agent worker plane commands (Phase 6)
# ═══════════════════════════════════════════════════════════════════════

def cmd_agent_worker_profiles() -> int:
    """List all agent worker provider profiles and policy status."""
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)

    from v3.external.agent_worker_profiles import (
        get_all_profiles, evaluate_all_profiles,
    )
    from v3.external.agent_worker_policy import (
        default_agent_worker_policy,
    )

    policy = default_agent_worker_policy()
    profiles = get_all_profiles()
    statuses = evaluate_all_profiles(policy)

    print("=" * 60)
    print("  SystemKernel v4.0 — Agent Worker Plane")
    print("=" * 60)
    print()
    print(f"  Policy hash:            {policy.policy_hash}")
    print(f"  Allow LLM providers:    {policy.allow_llm_providers}")
    print(f"  Allow network:          {policy.allow_network}")
    print(f"  Allow file mod:         {policy.allow_file_modification}")
    print(f"  Allow cmd exec:         {policy.allow_command_execution}")
    print(f"  Allow external svcs:    {policy.allow_external_services}")
    print(f"  Require sandbox:        {policy.require_sandbox}")
    print(f"  Require human approval: {policy.require_human_approval}")
    print()
    print(f"  {'Provider':<35} {'Type':<22} {'Allowed':<10} {'LLM':<6} {'Net':<6} {'File':<6} {'Cmd':<6} {'ExtSvc':<8}")
    print(f"  {'-'*35} {'-'*22} {'-'*10} {'-'*6} {'-'*6} {'-'*6} {'-'*6} {'-'*8}")

    status_map = {s.provider_id: s for s in statuses}
    for p in profiles:
        st = status_map.get(p.provider_id)
        allowed = "YES" if (st and st.allowed) else "NO"
        print(f"  {p.provider_id:<35} {p.provider_type:<22} {allowed:<10} "
              f"{'Y' if p.requires_llm else 'N':<6} "
              f"{'Y' if p.requires_network else 'N':<6} "
              f"{'Y' if p.can_modify_files else 'N':<6} "
              f"{'Y' if p.can_execute_commands else 'N':<6} "
              f"{'Y' if p.external_service_required else 'N':<8}")

    print()
    print(f"  Profiles:               {len(profiles)}")
    print("  External integrations:  NONE (Phase 6 is contract only)")
    print()
    return 0


def cmd_agent_worker_mock(provider_id: str = "deterministic_mock_agent",
                          proposals: int = 2) -> int:
    """Generate deterministic mock agent worker result."""
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)

    from v3.external.agent_worker import (
        build_agent_worker_task,
        mock_agent_worker_result,
        validate_agent_worker_provider,
        validate_agent_worker_result,
    )
    from v3.external.agent_worker_profiles import get_profile
    from v3.external.agent_worker_policy import (
        default_agent_worker_policy,
        validate_provider_against_policy,
    )

    provider = get_profile(provider_id)
    if provider is None:
        print(f"Unknown provider: {provider_id}")
        return 1

    policy = default_agent_worker_policy()
    allowed, reason = validate_provider_against_policy(provider, policy)

    print("=" * 60)
    print("  SystemKernel v4.0 — Agent Worker Plane")
    print("=" * 60)
    print()
    print(f"  Provider:               {provider.provider_id}")
    print(f"  Type:                   {provider.provider_type}")
    print(f"  Policy allowed:         {allowed}")
    if not allowed:
        print(f"  Reason:                 {reason}")
        return 1

    provider_valid = validate_agent_worker_provider(provider)
    task = build_agent_worker_task(
        provider_id=provider_id,
        task_summary="Mock agent worker task for testing",
        input_refs=("file-1.py", "file-2.py"),
        allowed_paths=("./src",),
        max_runtime_seconds=300,
        dry_run=True,
    )
    result = mock_agent_worker_result(task, proposal_count=proposals)
    result_valid = validate_agent_worker_result(result)

    print(f"  Task ID:                {task.task_id}")
    print(f"  Task dry_run:           {task.dry_run}")
    print(f"  Proposals generated:    {len(result.proposals)}")
    print(f"  Status:                 {result.status}")
    print(f"  Truth source:           {result.truth_source}")
    print(f"  Result hash:            {result.result_hash}")
    print(f"  Provider validation:    {'PASS' if provider_valid.valid else 'FAIL'}")
    print(f"  Result validation:      {'PASS' if result_valid.valid else 'FAIL'}")

    if result.proposals:
        print(f"\n  Proposals:")
        for p in result.proposals:
            print(f"    [{p.proposal_id[:8]}] confidence={p.confidence:.1f} "
                  f"plan='{p.proposed_plan[:60]}...'")

    print()
    return 0


def cmd_agent_worker_evidence(provider_id: str = "deterministic_mock_agent",
                              output: str = "") -> int:
    """Build evidence bundle from mock agent worker result."""
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)

    from v3.external.agent_worker import (
        build_agent_worker_task,
        mock_agent_worker_result,
        agent_proposals_to_evidence,
        build_agent_worker_report,
    )
    from v3.external.agent_worker_profiles import get_profile
    from v3.external.agent_worker_policy import (
        default_agent_worker_policy,
        validate_provider_against_policy,
    )
    from v3.external.default_capabilities import build_default_registry

    provider = get_profile(provider_id)
    if provider is None:
        print(f"Unknown provider: {provider_id}")
        return 1

    policy = default_agent_worker_policy()
    allowed, reason = validate_provider_against_policy(provider, policy)

    if not allowed:
        print(f"Provider blocked: {reason}")
        return 1

    task = build_agent_worker_task(
        provider_id=provider_id,
        task_summary="Mock agent worker task for evidence mapping",
        input_refs=("file-1.py", "file-2.py"),
        allowed_paths=("./src",),
        max_runtime_seconds=300,
        dry_run=True,
    )
    result = mock_agent_worker_result(task, proposal_count=3)
    registry = build_default_registry()
    bundle = agent_proposals_to_evidence(
        result, registry_hash=registry.registry_hash,
    )
    report = build_agent_worker_report(
        provider, task, result, bundle, policy_status="pass",
    )

    if not output:
        output = f"/tmp/agent_worker_evidence_{result.result_hash}.json"
    with open(output, "w", encoding="utf-8") as f:
        _json.dump(report.to_dict(), f, indent=2, ensure_ascii=False, sort_keys=True)

    print("=" * 60)
    print("  SystemKernel v4.0 — Agent Worker Plane")
    print("=" * 60)
    print()
    print(f"  Evidence bundle:        {bundle.bundle_id}")
    print(f"  Evidence records:       {len(bundle.records)}")
    print(f"  Truth source:           {bundle.truth_source}")
    print(f"  Policy status:          {report.policy_status}")
    print(f"  Report hash:            {report.report_hash}")
    print(f"  Report written:         {output}")

    print()
    return 0


# ═══════════════════════════════════════════════════════════════════════
# Skill evolution plane commands (Phase 8)
# ═══════════════════════════════════════════════════════════════════════

def cmd_skill_evolution_profiles() -> int:
    """List all skill evolution provider profiles and policy status."""
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)

    from v3.external.skill_evolution_profiles import (
        get_all_profiles, evaluate_all_profiles,
    )
    from v3.external.skill_evolution_policy import (
        default_skill_evolution_policy,
    )

    policy = default_skill_evolution_policy()
    profiles = get_all_profiles()
    statuses = evaluate_all_profiles(policy)

    print("=" * 60)
    print("  SystemKernel v4.0 — Skill Evolution Plane")
    print("=" * 60)
    print()
    print(f"  Policy hash:             {policy.policy_hash}")
    print(f"  Allow LLM providers:     {policy.allow_llm_providers}")
    print(f"  Allow skill mod:         {policy.allow_skill_file_modification}")
    print(f"  Allow registry update:   {policy.allow_registry_update}")
    print(f"  Allow skill install:     {policy.allow_skill_installation}")
    print(f"  Require tests:           {policy.require_tests_for_changes}")
    print(f"  Require human approval:  {policy.require_human_approval}")
    print()
    print(f"  {'Provider':<40} {'Type':<25} {'Allowed':<10} {'LLM':<6} {'Mod':<6} {'Reg':<6} {'Inst':<7} {'ExtSvc':<8}")
    print(f"  {'-'*40} {'-'*25} {'-'*10} {'-'*6} {'-'*6} {'-'*6} {'-'*7} {'-'*8}")

    status_map = {s.provider_id: s for s in statuses}
    for p in profiles:
        st = status_map.get(p.provider_id)
        allowed = "YES" if (st and st.allowed) else "NO"
        print(f"  {p.provider_id:<40} {p.provider_type:<25} {allowed:<10} "
              f"{'Y' if p.requires_llm else 'N':<6} "
              f"{'Y' if p.can_modify_skills else 'N':<6} "
              f"{'Y' if p.can_update_registry else 'N':<6} "
              f"{'Y' if p.can_install_skills else 'N':<7} "
              f"{'Y' if p.external_service_required else 'N':<8}")

    print()
    print(f"  Profiles:                {len(profiles)}")
    print("  Skill evolution:         PROPOSAL-ONLY (no automatic modification)")
    print()
    return 0


def cmd_skill_evolution_mock(provider_id: str = "deterministic_mock_skill_evolution",
                              proposals: int = 2, signals: int = 3) -> int:
    """Generate deterministic mock skill evolution result."""
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)

    from v3.external.skill_evolution import (
        mock_skill_evolution_result,
        validate_skill_provider,
        validate_skill_result,
    )
    from v3.external.skill_evolution_profiles import get_profile
    from v3.external.skill_evolution_policy import (
        default_skill_evolution_policy,
        validate_provider_against_policy,
    )

    provider = get_profile(provider_id)
    if provider is None:
        print(f"Unknown provider: {provider_id}")
        return 1

    policy = default_skill_evolution_policy()
    allowed, reason = validate_provider_against_policy(provider, policy)

    print("=" * 60)
    print("  SystemKernel v4.0 — Skill Evolution Plane")
    print("=" * 60)
    print()
    print(f"  Provider:                {provider.provider_id}")
    print(f"  Type:                    {provider.provider_type}")
    print(f"  Policy allowed:          {allowed}")
    if not allowed:
        print(f"  Reason:                  {reason}")
        return 1

    provider_valid = validate_skill_provider(provider)
    result = mock_skill_evolution_result(
        provider_id=provider_id,
        proposal_count=proposals,
        signal_count=signals,
    )
    result_valid = validate_skill_result(result)

    print(f"  Proposals generated:     {len(result.proposals)}")
    print(f"  Status:                  {result.status}")
    print(f"  Truth source:            {result.truth_source}")
    print(f"  Result hash:             {result.result_hash}")
    print(f"  Provider validation:     {'PASS' if provider_valid.valid else 'FAIL'}")
    print(f"  Result validation:       {'PASS' if result_valid.valid else 'FAIL'}")

    if result.proposals:
        print(f"\n  Proposals:")
        for p in result.proposals:
            print(f"    [{p.proposal_id[:8]}] type={p.proposal_type} "
                  f"approval={p.approval_required} "
                  f"summary='{p.proposed_changes_summary[:50]}...'")

    if result.warnings:
        print(f"\n  Warnings:")
        for w in result.warnings:
            print(f"    - {w}")

    print()
    return 0


def cmd_skill_evolution_evidence(provider_id: str = "deterministic_mock_skill_evolution",
                                  output: str = "") -> int:
    """Build evidence bundle from mock skill evolution result."""
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)

    from v3.external.skill_evolution import (
        mock_skill_evolution_result,
        skill_proposals_to_evidence,
        build_skill_evolution_report,
    )
    from v3.external.skill_evolution_profiles import get_profile
    from v3.external.skill_evolution_policy import (
        default_skill_evolution_policy,
        validate_provider_against_policy,
    )
    from v3.external.default_capabilities import build_default_registry

    provider = get_profile(provider_id)
    if provider is None:
        print(f"Unknown provider: {provider_id}")
        return 1

    policy = default_skill_evolution_policy()
    allowed, reason = validate_provider_against_policy(provider, policy)

    if not allowed:
        print(f"Provider blocked: {reason}")
        return 1

    result = mock_skill_evolution_result(provider_id=provider_id, proposal_count=3, signal_count=3)
    registry = build_default_registry()
    bundle = skill_proposals_to_evidence(
        result, registry_hash=registry.registry_hash,
    )
    report = build_skill_evolution_report(
        provider, result, bundle, policy_status="pass",
    )

    if not output:
        output = f"/tmp/skill_evolution_evidence_{result.result_hash}.json"
    with open(output, "w", encoding="utf-8") as f:
        _json.dump(report.to_dict(), f, indent=2, ensure_ascii=False, sort_keys=True)

    print("=" * 60)
    print("  SystemKernel v4.0 — Skill Evolution Plane")
    print("=" * 60)
    print()
    print(f"  Evidence bundle:         {bundle.bundle_id}")
    print(f"  Evidence records:        {len(bundle.records)}")
    print(f"  Truth source:            {bundle.truth_source}")
    print(f"  Policy status:           {report.policy_status}")
    print(f"  Report hash:             {report.report_hash}")
    print(f"  Report written:          {output}")

    print()
    return 0


# ═══════════════════════════════════════════════════════════════════════
# Orchestration policy commands (Phase 9)
# ═══════════════════════════════════════════════════════════════════════

def cmd_orchestrate_policies() -> int:
    """List all orchestration policy profiles."""
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)

    from v3.external.orchestration_profiles import (
        get_all_profiles, get_all_profile_statuses,
    )

    profiles = get_all_profiles()
    statuses = get_all_profile_statuses()
    status_map = {s.policy_id: s for s in statuses}

    print("=" * 60)
    print("  SystemKernel v4.0 — Orchestration Policy Layer")
    print("=" * 60)
    print()
    print(f"  {'Profile':<30} {'Types':<30} {'Run':<8} {'Risk':<8} {'Exec':<6} {'Net':<6} {'File':<6}")
    print(f"  {'-'*30} {'-'*30} {'-'*8} {'-'*8} {'-'*6} {'-'*6} {'-'*6}")

    for p in profiles:
        types_str = ",".join(p.allowed_capability_types[:3])
        if len(p.allowed_capability_types) > 3:
            types_str += "..."
        if not p.allowed_capability_types:
            types_str = "(all)"
        print(f"  {p.policy_id:<30} {types_str:<30} "
              f"{'dry' if p.dry_run_only else 'live':<8} "
              f"{p.max_risk_level:<8} "
              f"{'Y' if p.allow_external_execution else 'N':<6} "
              f"{'Y' if p.allow_network else 'N':<6} "
              f"{'Y' if p.allow_file_modification else 'N':<6}")

    print()
    print(f"  Profiles:                {len(profiles)}")
    print("  Execution:               NONE (Phase 9 is planning only)")
    print()
    return 0


def cmd_orchestrate_plan(profile_id: str = "safe_context_only",
                          objective: str = "Dry-run orchestration plan") -> int:
    """Build a dry-run orchestration plan."""
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)

    from v3.external.orchestration_policy import (
        build_orchestration_request,
        plan_orchestration,
        validate_orchestration_plan,
    )
    from v3.external.orchestration_profiles import get_profile
    from v3.external.default_capabilities import build_default_registry

    policy = get_profile(profile_id)
    if policy is None:
        print(f"Unknown profile: {profile_id}")
        print(f"Use 'orchestrate policies' to list available profiles.")
        return 1

    registry = build_default_registry()
    request = build_orchestration_request(
        objective=objective,
        requested_capability_types=policy.allowed_capability_types,
    )
    plan = plan_orchestration(request, registry, policy)
    validation = validate_orchestration_plan(plan, registry, policy)

    print("=" * 60)
    print("  SystemKernel v4.0 — Orchestration Policy Layer")
    print("=" * 60)
    print()
    print(f"  Profile:                {policy.policy_id}")
    print(f"  Policy hash:            {policy.policy_hash}")
    print(f"  Objective:              {objective}")
    print(f"  Plan ID:                {plan.plan_id}")
    print(f"  Steps:                  {len(plan.steps)}")
    print(f"  Blocked steps:          {len(plan.blocked_steps)}")
    print(f"  Warnings:               {len(plan.warnings)}")
    print(f"  Truth source:           {plan.truth_source}")
    print(f"  Plan hash:              {plan.plan_hash}")
    print(f"  Validation:             {'PASS' if validation.valid else 'FAIL'}")

    if plan.steps:
        print(f"\n  Planned Steps:")
        for s in plan.steps:
            print(f"    [{s.capability_type}] {s.adapter_id}")
            print(f"      mode={s.execution_mode} evidence={s.expected_evidence_type}")

    if plan.blocked_steps:
        print(f"\n  Blocked Steps:")
        for s in plan.blocked_steps:
            print(f"    [BLOCKED] {s.adapter_id} — {s.block_reason[:70]}")

    if plan.warnings:
        print(f"\n  Warnings:")
        for w in plan.warnings:
            print(f"    - {w}")

    print()
    return 0


def cmd_orchestrate_evidence(profile_id: str = "safe_context_only",
                               objective: str = "Dry-run orchestration plan",
                               output: str = "") -> int:
    """Build evidence bundle from orchestration plan."""
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)

    from v3.external.orchestration_policy import (
        build_orchestration_request,
        plan_orchestration,
        build_orchestration_policy_report,
        orchestration_plan_to_evidence,
    )
    from v3.external.orchestration_profiles import get_profile
    from v3.external.default_capabilities import build_default_registry

    policy = get_profile(profile_id)
    if policy is None:
        print(f"Unknown profile: {profile_id}")
        return 1

    registry = build_default_registry()
    request = build_orchestration_request(
        objective=objective,
        requested_capability_types=policy.allowed_capability_types,
    )
    plan = plan_orchestration(request, registry, policy)
    bundle = orchestration_plan_to_evidence(
        plan, registry_hash=registry.registry_hash,
    )
    report = build_orchestration_policy_report(
        policy, request, plan, registry_hash=registry.registry_hash,
    )

    if not output:
        output = f"/tmp/orchestration_evidence_{plan.plan_hash}.json"
    with open(output, "w", encoding="utf-8") as f:
        _json.dump(report.to_dict(), f, indent=2, ensure_ascii=False, sort_keys=True)

    print("=" * 60)
    print("  SystemKernel v4.0 — Orchestration Policy Layer")
    print("=" * 60)
    print()
    print(f"  Evidence bundle:         {bundle.bundle_id}")
    print(f"  Evidence records:        {len(bundle.records)}")
    print(f"  Truth source:            {bundle.truth_source}")
    print(f"  Validation status:       {report.validation_status}")
    print(f"  Report hash:             {report.report_hash}")
    print(f"  Report written:          {output}")

    print()
    return 0
