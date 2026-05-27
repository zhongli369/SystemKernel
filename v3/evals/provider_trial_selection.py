"""
Provider Trial Selection — Phase 14A.

Deterministic scoring and ranking of candidate external providers
for the next real-provider trial. No provider is executed, installed,
or contacted during this phase.

Stdlib only. Frozen dataclasses. Deterministic output.
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Tuple

ROOT = Path(__file__).resolve().parent.parent.parent

# ── Verdict constants ─────────────────────────────────────────────────────────

VERDICT_RECOMMENDED = "recommended"
VERDICT_ACCEPTABLE = "acceptable"
VERDICT_DEFER = "defer"
VERDICT_REJECT = "reject"

ALL_VERDICTS = (VERDICT_RECOMMENDED, VERDICT_ACCEPTABLE, VERDICT_DEFER, VERDICT_REJECT)


# ── Hashing ──────────────────────────────────────────────────────────────────

def _hash(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:16]


# ── Frozen dataclasses ────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ProviderTrialCandidate:
    """A candidate external provider for controlled trial."""
    candidate_id: str
    name: str
    provider_type: str
    required_plane: str
    existing_adapter_ready: bool
    requires_network: bool
    requires_install: bool
    requires_external_service: bool
    can_run_read_only: bool
    can_produce_evidence: bool
    can_be_reversed: bool
    notes: str
    candidate_hash: str = ""


@dataclass(frozen=True)
class ProviderTrialScore:
    """Scored evaluation of a trial candidate."""
    candidate_id: str
    capability_gain: int          # 0-10
    complexity_delta: int          # 0-10 (lower is better)
    kernel_risk: int               # 0-10 (lower is better)
    memory_risk: int               # 0-10 (lower is better)
    dependency_risk: int           # 0-10 (lower is better)
    execution_risk: int            # 0-10 (lower is better)
    reversibility_score: int       # 0-10 (higher is better)
    adapter_readiness_score: int   # 0-10 (higher is better)
    evidence_fit_score: int        # 0-10 (higher is better)
    manual_step_reduction_score: int  # 0-10 (higher is better)
    total_score: int
    risk_ratio: float
    verdict: str
    reasons: Tuple[str, ...]
    score_hash: str = ""


@dataclass(frozen=True)
class ProviderTrialSelectionReport:
    """Full Phase 14A provider trial selection report."""
    candidates: Tuple[ProviderTrialCandidate, ...]
    scores: Tuple[ProviderTrialScore, ...]
    recommended_candidate: str
    rejected_candidates: Tuple[str, ...]
    deferred_candidates: Tuple[str, ...]
    report_hash: str = ""


# ── Candidate builder ────────────────────────────────────────────────────────

def build_default_trial_candidates() -> Tuple[ProviderTrialCandidate, ...]:
    """Build the deterministic set of trial candidates."""
    raw = [
        ProviderTrialCandidate(
            candidate_id="repomix",
            name="Repomix — Controlled Execution via Context Engineering Plane",
            provider_type="context_pack",
            required_plane="Context Engineering Plane",
            existing_adapter_ready=True,
            requires_network=False,
            requires_install=False,
            requires_external_service=False,
            can_run_read_only=True,
            can_produce_evidence=True,
            can_be_reversed=True,
            notes="Existing repomix_context_pack adapter. Evidence model ready. Reversible output (files only). "
                  "No network/install/external-service. Highest readiness of all candidates.",
            candidate_hash="",
        ),
        ProviderTrialCandidate(
            candidate_id="ccusage",
            name="ccusage — Usage Report Refresh",
            provider_type="usage_report",
            required_plane="Context Engineering Plane",
            existing_adapter_ready=True,
            requires_network=False,
            requires_install=False,
            requires_external_service=False,
            can_run_read_only=True,
            can_produce_evidence=True,
            can_be_reversed=True,
            notes="Existing usage report adapter. Lower capability gain than Repomix "
                  "(reports only, no execution path). Safe and reversible.",
            candidate_hash="",
        ),
        ProviderTrialCandidate(
            candidate_id="ecc",
            name="ECC — Read-Only Clone/Inspection",
            provider_type="harness_enhancement",
            required_plane="Orchestration + Evaluation",
            existing_adapter_ready=False,
            requires_network=True,
            requires_install=False,
            requires_external_service=False,
            can_run_read_only=True,
            can_produce_evidence=False,
            can_be_reversed=True,
            notes="ECC is an external harness enhancement kit. Clone/inspect only. "
                  "No adapter exists. No evidence model. Requires network for git clone. "
                  "Strategic value but no integration path yet. Defer until user explicitly requests.",
            candidate_hash="",
        ),
        ProviderTrialCandidate(
            candidate_id="anthropic_skills",
            name="Anthropic Skills Format Alignment Trial",
            provider_type="skill_format",
            required_plane="Skill Evolution Plane",
            existing_adapter_ready=False,
            requires_network=False,
            requires_install=False,
            requires_external_service=False,
            can_run_read_only=True,
            can_produce_evidence=False,
            can_be_reversed=True,
            notes="Skills format alignment study. No adapter. No evidence model. "
                  "Reference-only at this stage. Low risk but also low immediate gain.",
            candidate_hash="",
        ),
        ProviderTrialCandidate(
            candidate_id="mem0",
            name="mem0 — External Memory Service Trial",
            provider_type="memory_service",
            required_plane="Memory Intelligence Plane",
            existing_adapter_ready=False,
            requires_network=True,
            requires_install=True,
            requires_external_service=True,
            can_run_read_only=False,
            can_produce_evidence=False,
            can_be_reversed=False,
            notes="External memory service. Requires network + install + external service. "
                  "Memory Intelligence Plane is removable (v4 design). "
                  "High execution risk. High dependency risk. Cannot be reversed cleanly.",
            candidate_hash="",
        ),
        ProviderTrialCandidate(
            candidate_id="graphiti",
            name="Graphiti — Knowledge Graph Service Trial",
            provider_type="knowledge_graph",
            required_plane="Memory Intelligence Plane",
            existing_adapter_ready=False,
            requires_network=True,
            requires_install=True,
            requires_external_service=True,
            can_run_read_only=False,
            can_produce_evidence=False,
            can_be_reversed=False,
            notes="External knowledge graph service. Same risk profile as mem0. "
                  "Needs running service, network, install. Memory plane is removable. "
                  "Complexity risk far outweighs capability gain.",
            candidate_hash="",
        ),
        ProviderTrialCandidate(
            candidate_id="openhands",
            name="OpenHands / SWE-agent — Agent Worker Trial",
            provider_type="agent_worker",
            required_plane="Agent Worker Plane",
            existing_adapter_ready=False,
            requires_network=True,
            requires_install=True,
            requires_external_service=True,
            can_run_read_only=False,
            can_produce_evidence=False,
            can_be_reversed=False,
            notes="External agent worker. Requires running service + network + install. "
                  "Agent execution is the highest-risk capability type. "
                  "No adapter. No evidence model. High execution risk.",
            candidate_hash="",
        ),
        ProviderTrialCandidate(
            candidate_id="continue",
            name="Continue — Workspace Provider Trial",
            provider_type="workspace_provider",
            required_plane="Workspace Context Plane",
            existing_adapter_ready=False,
            requires_network=False,
            requires_install=True,
            requires_external_service=False,
            can_run_read_only=True,
            can_produce_evidence=False,
            can_be_reversed=True,
            notes="IDE workspace provider. Requires install but no network/service. "
                  "Read-only inspection possible. Lower risk than agent/memory providers. "
                  "But no adapter or evidence model yet.",
            candidate_hash="",
        ),
    ]

    result = []
    for c in raw:
        h = _hash(c.candidate_id, c.name, c.provider_type, c.required_plane,
                  str(c.existing_adapter_ready), str(c.requires_network),
                  str(c.requires_install), str(c.requires_external_service),
                  str(c.can_run_read_only), str(c.can_produce_evidence),
                  str(c.can_be_reversed))
        result.append(ProviderTrialCandidate(
            candidate_id=c.candidate_id,
            name=c.name,
            provider_type=c.provider_type,
            required_plane=c.required_plane,
            existing_adapter_ready=c.existing_adapter_ready,
            requires_network=c.requires_network,
            requires_install=c.requires_install,
            requires_external_service=c.requires_external_service,
            can_run_read_only=c.can_run_read_only,
            can_produce_evidence=c.can_produce_evidence,
            can_be_reversed=c.can_be_reversed,
            notes=c.notes,
            candidate_hash=h,
        ))

    return tuple(result)


# ── Scoring engine ───────────────────────────────────────────────────────────

def score_trial_candidate(candidate: ProviderTrialCandidate) -> ProviderTrialScore:
    """Score a single trial candidate using deterministic criteria.

    Scoring logic (deterministic, no LLM):

    capability_gain:
      - 9: context_pack (produces real output, highest manual step reduction)
      - 7: usage_report (produces reports, useful but narrow)
      - 5: harness_enhancement, skill_format (reference value only)
      - 3: workspace_provider (inspection only)
      - 2: agent_worker, memory_service, knowledge_graph (high risk, low immediate gain)

    complexity_delta (lower is better):
      - 1: context_pack, usage_report (existing adapter, no new deps)
      - 5: skill_format (no adapter, but no runtime deps)
      - 6: harness_enhancement (needs clone, no adapter)
      - 7: workspace_provider (needs install)
      - 9: agent_worker, memory_service, knowledge_graph (needs service + install + network)

    kernel_risk (lower is better):
      - 0: context_pack, usage_report (existing plane, no kernel proximity)
      - 1: skill_format (Skill Evolution, no kernel path)
      - 2: harness_enhancement, workspace_provider
      - 5: memory_service, knowledge_graph (Memory Intelligence proximity)
      - 6: agent_worker (agent execution proximity)

    memory_risk (lower is better):
      - 0: context_pack, usage_report, skill_format, harness_enhancement
      - 1: workspace_provider
      - 8: memory_service, knowledge_graph (memory plane is the target)
      - 4: agent_worker

    dependency_risk (lower is better):
      - 0: context_pack, usage_report (zero new deps)
      - 2: skill_format (reference only)
      - 5: harness_enhancement (git clone only)
      - 6: workspace_provider (install only)
      - 9: memory_service, knowledge_graph (service + install + network)
      - 9: agent_worker (service + install + network)

    execution_risk (lower is better):
      - 0: skill_format (no execution)
      - 1: context_pack, usage_report (controlled, existing adapter)
      - 4: harness_enhancement (read-only clone)
      - 6: workspace_provider (read-only inspect)
      - 10: memory_service, knowledge_graph, agent_worker (external execution)

    reversibility_score:
      - 10: context_pack, usage_report, skill_format (delete output files)
      - 8: harness_enhancement (delete cloned repo)
      - 5: workspace_provider (uninstall)
      - 1: memory_service, knowledge_graph, agent_worker (service state, hard to reverse)

    adapter_readiness_score:
      - 9: context_pack, usage_report (existing adapter, tested)
      - 0: all others (no adapter)

    evidence_fit_score:
      - 9: context_pack (evidence model ready, truth_source pattern fits)
      - 7: usage_report (evidence model fits)
      - 0: all others (no evidence model)

    manual_step_reduction_score:
      - 9: context_pack (automates repo-to-context workflow)
      - 5: usage_report (reduces manual report inspection)
      - 3: harness_enhancement (reference value)
      - 1: others (no immediate manual step reduction)
    """
    cid = candidate.candidate_id

    # ── Capability gain ──
    _cap_gain = {
        "repomix": 9, "ccusage": 7, "ecc": 5, "anthropic_skills": 5,
        "continue": 3, "mem0": 2, "graphiti": 2, "openhands": 2,
    }
    capability_gain = _cap_gain.get(cid, 1)

    # ── Complexity delta (lower = less complex) ──
    _comp_delta = {
        "repomix": 1, "ccusage": 1, "anthropic_skills": 5, "ecc": 6,
        "continue": 7, "mem0": 9, "graphiti": 9, "openhands": 9,
    }
    complexity_delta = _comp_delta.get(cid, 5)

    # ── Kernel risk (lower = safer) ──
    _krisk = {
        "repomix": 0, "ccusage": 0, "anthropic_skills": 1, "ecc": 2,
        "continue": 2, "mem0": 5, "graphiti": 5, "openhands": 6,
    }
    kernel_risk = _krisk.get(cid, 3)

    # ── Memory risk (lower = safer) ──
    _mrisk = {
        "repomix": 0, "ccusage": 0, "anthropic_skills": 0, "ecc": 0,
        "continue": 1, "openhands": 4, "mem0": 8, "graphiti": 8,
    }
    memory_risk = _mrisk.get(cid, 3)

    # ── Dependency risk (lower = safer) ──
    _deprisk = {
        "repomix": 0, "ccusage": 0, "anthropic_skills": 2, "ecc": 5,
        "continue": 6, "mem0": 9, "graphiti": 9, "openhands": 9,
    }
    dependency_risk = _deprisk.get(cid, 5)

    # ── Execution risk (lower = safer) ──
    _execrisk = {
        "anthropic_skills": 0, "repomix": 1, "ccusage": 1, "ecc": 4,
        "continue": 6, "mem0": 10, "graphiti": 10, "openhands": 10,
    }
    execution_risk = _execrisk.get(cid, 5)

    # ── Reversibility (higher = easier to reverse) ──
    _rev = {
        "repomix": 10, "ccusage": 10, "anthropic_skills": 10, "ecc": 8,
        "continue": 5, "mem0": 1, "graphiti": 1, "openhands": 1,
    }
    reversibility_score = _rev.get(cid, 5)

    # ── Adapter readiness (higher = more ready) ──
    _adapter = {
        "repomix": 9, "ccusage": 9,
        "ecc": 0, "anthropic_skills": 0, "continue": 0,
        "mem0": 0, "graphiti": 0, "openhands": 0,
    }
    adapter_readiness_score = _adapter.get(cid, 0)

    # ── Evidence fit (higher = better fit) ──
    _evfit = {
        "repomix": 9, "ccusage": 7,
        "ecc": 0, "anthropic_skills": 0, "continue": 0,
        "mem0": 0, "graphiti": 0, "openhands": 0,
    }
    evidence_fit_score = _evfit.get(cid, 0)

    # ── Manual step reduction (higher = more reduction) ──
    _msr = {
        "repomix": 9, "ccusage": 5, "ecc": 3, "anthropic_skills": 1,
        "continue": 1, "mem0": 0, "graphiti": 0, "openhands": 0,
    }
    manual_step_reduction_score = _msr.get(cid, 0)

    # ── Total score: benefit dimensions minus cost dimensions ──
    benefit = (capability_gain * 10 + reversibility_score * 5 +
               adapter_readiness_score * 8 + evidence_fit_score * 5 +
               manual_step_reduction_score * 7)
    cost = (complexity_delta * 8 + kernel_risk * 10 + memory_risk * 6 +
            dependency_risk * 7 + execution_risk * 9)
    total_score = max(0, benefit - cost)

    # ── Risk ratio ──
    risk_sum = (complexity_delta + kernel_risk + memory_risk +
                dependency_risk + execution_risk)
    gain_sum = (capability_gain + reversibility_score // 2 +
                adapter_readiness_score // 2 + manual_step_reduction_score // 2)
    risk_ratio = round(risk_sum / max(1, gain_sum), 2) if gain_sum > 0 else 999.0

    # ── Verdict ──
    reasons = []
    if candidate.requires_external_service:
        verdict = VERDICT_REJECT
        reasons.append("requires_external_service")
    elif candidate.requires_install and candidate.requires_network and not candidate.can_produce_evidence:
        verdict = VERDICT_REJECT
        reasons.append("install_network_no_evidence")
    elif total_score >= 300:
        verdict = VERDICT_RECOMMENDED
        reasons.append("highest_total_score")
    elif total_score >= 200:
        verdict = VERDICT_ACCEPTABLE
        reasons.append("positive_score")
    elif candidate.requires_network and not candidate.existing_adapter_ready:
        verdict = VERDICT_DEFER
        reasons.append("no_adapter_requires_network")
        if total_score <= 0:
            reasons.append("zero_or_negative_score")
    elif candidate.requires_install and not candidate.existing_adapter_ready:
        verdict = VERDICT_DEFER
        reasons.append("no_adapter_requires_install")
    elif total_score > 0:
        verdict = VERDICT_ACCEPTABLE
        reasons.append("low_positive_score")
    else:
        verdict = VERDICT_DEFER
        reasons.append("insufficient_readiness")

    if capability_gain >= 8:
        reasons.append("high_capability_gain")
    if complexity_delta <= 2:
        reasons.append("low_complexity_delta")
    if existing_adapter_ready(candidate):
        reasons.append("existing_adapter")
    if candidate.can_produce_evidence:
        reasons.append("can_produce_evidence")
    if candidate.can_be_reversed:
        reasons.append("reversible")
    if candidate.requires_network:
        reasons.append("requires_network")
    if candidate.requires_install:
        reasons.append("requires_install")
    if candidate.requires_external_service:
        reasons.append("requires_external_service")

    score_hash = _hash(
        candidate.candidate_id,
        str(capability_gain), str(complexity_delta),
        str(kernel_risk), str(memory_risk), str(dependency_risk),
        str(execution_risk), str(reversibility_score),
        str(adapter_readiness_score), str(evidence_fit_score),
        str(manual_step_reduction_score), str(total_score),
        str(risk_ratio), verdict,
    )

    return ProviderTrialScore(
        candidate_id=cid,
        capability_gain=capability_gain,
        complexity_delta=complexity_delta,
        kernel_risk=kernel_risk,
        memory_risk=memory_risk,
        dependency_risk=dependency_risk,
        execution_risk=execution_risk,
        reversibility_score=reversibility_score,
        adapter_readiness_score=adapter_readiness_score,
        evidence_fit_score=evidence_fit_score,
        manual_step_reduction_score=manual_step_reduction_score,
        total_score=total_score,
        risk_ratio=risk_ratio,
        verdict=verdict,
        reasons=tuple(reasons),
        score_hash=score_hash,
    )


def existing_adapter_ready(candidate: ProviderTrialCandidate) -> bool:
    return candidate.existing_adapter_ready


# ── Selection ────────────────────────────────────────────────────────────────

def select_best_trial(
    candidates: Tuple[ProviderTrialCandidate, ...],
) -> ProviderTrialSelectionReport:
    """Score all candidates and select the best next trial.

    Returns a ProviderTrialSelectionReport with ranked scores,
    recommended candidate, and defer/reject lists.
    """
    scores = tuple(
        sorted(
            [score_trial_candidate(c) for c in candidates],
            key=lambda s: (-s.total_score, s.risk_ratio),
        )
    )

    recommended = ""
    rejected = []
    deferred = []

    for s in scores:
        if s.verdict == VERDICT_RECOMMENDED and not recommended:
            recommended = s.candidate_id
        elif s.verdict == VERDICT_REJECT:
            rejected.append(s.candidate_id)
        elif s.verdict == VERDICT_DEFER:
            deferred.append(s.candidate_id)
        elif s.verdict == VERDICT_ACCEPTABLE and not recommended:
            recommended = s.candidate_id

    if not recommended and scores:
        recommended = scores[0].candidate_id

    report_hash = _hash(
        *(s.score_hash for s in scores),
        recommended,
        *rejected,
        *deferred,
    )

    return ProviderTrialSelectionReport(
        candidates=candidates,
        scores=scores,
        recommended_candidate=recommended,
        rejected_candidates=tuple(rejected),
        deferred_candidates=tuple(deferred),
        report_hash=report_hash,
    )


# ── Ability+10 Complexity+300 risk ───────────────────────────────────────────

def compute_ability_complexity_risk(
    scores: Tuple[ProviderTrialScore, ...],
) -> str:
    """Compute the ability+10% complexity+300% risk for the recommended provider.

    Returns 'low', 'medium', or 'high'.
    """
    if not scores:
        return "low"

    best = scores[0]
    # If the recommended provider has risk_ratio >= 3.0, risk is HIGH
    if best.risk_ratio >= 3.0:
        return "high"
    # If risk_ratio >= 1.5, risk is MEDIUM
    if best.risk_ratio >= 1.5:
        return "medium"
    return "low"


# ── Report writer ────────────────────────────────────────────────────────────

def write_provider_trial_selection_report(
    report: ProviderTrialSelectionReport,
    output_dir: str,
) -> dict:
    """Write Phase 14A provider trial selection reports (JSON, MD, phase report)."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    # ── JSON ──
    json_data = {
        "phase": "14A",
        "title": "Provider Trial Selection",
        "recommended_candidate": report.recommended_candidate,
        "candidates": [
            {
                "candidate_id": c.candidate_id,
                "name": c.name,
                "provider_type": c.provider_type,
                "required_plane": c.required_plane,
                "existing_adapter_ready": c.existing_adapter_ready,
                "requires_network": c.requires_network,
                "requires_install": c.requires_install,
                "requires_external_service": c.requires_external_service,
                "can_run_read_only": c.can_run_read_only,
                "can_produce_evidence": c.can_produce_evidence,
                "can_be_reversed": c.can_be_reversed,
                "candidate_hash": c.candidate_hash,
            }
            for c in report.candidates
        ],
        "scores": [
            {
                "candidate_id": s.candidate_id,
                "capability_gain": s.capability_gain,
                "complexity_delta": s.complexity_delta,
                "kernel_risk": s.kernel_risk,
                "memory_risk": s.memory_risk,
                "dependency_risk": s.dependency_risk,
                "execution_risk": s.execution_risk,
                "reversibility_score": s.reversibility_score,
                "adapter_readiness_score": s.adapter_readiness_score,
                "evidence_fit_score": s.evidence_fit_score,
                "manual_step_reduction_score": s.manual_step_reduction_score,
                "total_score": s.total_score,
                "risk_ratio": s.risk_ratio,
                "verdict": s.verdict,
                "reasons": list(s.reasons),
                "score_hash": s.score_hash,
            }
            for s in report.scores
        ],
        "rejected_candidates": list(report.rejected_candidates),
        "deferred_candidates": list(report.deferred_candidates),
        "ability_complexity_risk": compute_ability_complexity_risk(report.scores),
        "no_provider_executed": True,
        "report_hash": report.report_hash,
    }
    json_path = out / "provider_trial_selection.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(json_data, f, indent=2, default=str)

    # ── Markdown ──
    md_lines = [
        "# Provider Trial Selection Report — Phase 14A",
        "",
        f"**Recommended:** `{report.recommended_candidate}`",
        f"**Rejected:** {', '.join(report.rejected_candidates) or 'none'}",
        f"**Deferred:** {', '.join(report.deferred_candidates)}",
        f"**Risk:** {compute_ability_complexity_risk(report.scores)}",
        "",
        "## Ranking",
        "",
        "| Rank | Candidate | Score | Risk Ratio | Verdict |",
        "|------|-----------|-------|-----------|---------|",
    ]
    for i, s in enumerate(report.scores):
        md_lines.append(
            f"| {i + 1} | `{s.candidate_id}` | {s.total_score} | {s.risk_ratio} | **{s.verdict}** |"
        )

    md_lines += [
        "",
        "## Score Details",
        "",
        "| Candidate | Cap Gain | Cpx Δ | K Risk | M Risk | Dep Risk | Exec Risk | Rev | Adapter | Evidence | MSR |",
        "|-----------|----------|-------|--------|--------|----------|-----------|-----|---------|----------|-----|",
    ]
    for s in report.scores:
        md_lines.append(
            f"| `{s.candidate_id}` | {s.capability_gain} | {s.complexity_delta} | "
            f"{s.kernel_risk} | {s.memory_risk} | {s.dependency_risk} | {s.execution_risk} | "
            f"{s.reversibility_score} | {s.adapter_readiness_score} | {s.evidence_fit_score} | "
            f"{s.manual_step_reduction_score} |"
        )

    md_lines += [
        "",
        "## Recommended Next Trial",
        "",
        f"**{report.recommended_candidate}** — see ranking above for rationale.",
        "",
        "## Safety",
        "",
        "- **No provider executed** — this is a selection phase only.",
        "- **No network used** — all scoring is deterministic and local.",
        "- **No install run** — no dependencies added.",
        "- **Kernel not modified** — scoring is external to kernel.",
    ]

    md_path = out / "provider_trial_selection_report.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))

    # ── Phase report ──
    best = report.scores[0] if report.scores else None
    phase_lines = [
        "# Phase 14A — Provider Trial Selection",
        "",
        "**Status:** COMPLETE",
        "",
        "## Summary",
        "",
        f"- Candidates evaluated: {len(report.candidates)}",
        f"- Recommended: **{report.recommended_candidate}**",
        f"- Rejected: {', '.join(report.rejected_candidates) or 'none'}",
        f"- Deferred: {', '.join(report.deferred_candidates) or 'none'}",
        f"- Ability+10 Complexity+300 risk: **{compute_ability_complexity_risk(report.scores)}**",
        "",
        "## Ranking",
        "",
    ]
    for i, s in enumerate(report.scores):
        phase_lines.append(f"{i + 1}. **`{s.candidate_id}`** — score={s.total_score}, "
                           f"risk_ratio={s.risk_ratio}, verdict={s.verdict}")
        phase_lines.append(f"   Reasons: {', '.join(s.reasons)}")

    phase_lines += [
        "",
        "## Recommendation",
        "",
        f"Proceed with **{report.recommended_candidate}** as the first real-provider trial.",
        f"Expected capability gain: {best.capability_gain}/10" if best else "",
        f"Expected complexity delta: {best.complexity_delta}/10" if best else "",
        f"Risk ratio: {best.risk_ratio}" if best else "",
        "",
        "High-risk providers (mem0, Graphiti, OpenHands/SWE-agent) are rejected for now.",
        "They require external services, network access, and installation.",
        "ECC is deferred — strategic value but no adapter, no evidence model, requires clone.",
        "",
        "## Safety",
        "",
        "- **No provider executed in this phase**",
        "- **No network access**",
        "- **No installation**",
        "- **Kernel purity: 100/100**",
        "- **Memory runtime: unchanged**",
    ]

    phase_path = out / "phase_14a_provider_trial_selection_report.md"
    with open(phase_path, "w", encoding="utf-8") as f:
        f.write("\n".join(phase_lines))

    return {
        "json": str(json_path),
        "md": str(md_path),
        "phase_report": str(phase_path),
    }


# ── CLI entry ─────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  Phase 14A — Provider Trial Selection")
    print("=" * 60)
    print()

    candidates = build_default_trial_candidates()
    report = select_best_trial(candidates)

    print("  Candidates evaluated:", len(report.candidates))
    print()
    print("  Ranking:")
    for i, s in enumerate(report.scores):
        flag = " ← RECOMMENDED" if s.candidate_id == report.recommended_candidate else ""
        print(f"  {i + 1}. [{s.verdict:>12}] {s.candidate_id:<20} "
              f"score={s.total_score:>4}  risk_ratio={s.risk_ratio}{flag}")
    print()
    print(f"  Recommended:  {report.recommended_candidate}")
    print(f"  Rejected:     {', '.join(report.rejected_candidates) or 'none'}")
    print(f"  Deferred:     {', '.join(report.deferred_candidates) or 'none'}")
    print(f"  A+10/C+300 risk: {compute_ability_complexity_risk(report.scores)}")
    print()
    print("  No provider executed. Selection only.")
    print()

    exports_dir = str(ROOT / "v3" / "exports")
    paths = write_provider_trial_selection_report(report, exports_dir)
    print("  Reports written:")
    for k, v in paths.items():
        print(f"    {k}: {v}")
    print()
    print("  Phase 14A complete.")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
