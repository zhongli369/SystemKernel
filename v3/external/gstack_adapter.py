"""
gstack Direction Adapter — v4.1.

Deterministic methodology adapter that produces direction intelligence
signals using the gstack framework as an evaluation rubric.

gstack principles (from ETHOS.md, DESIGN.md, README.md):
  - Boil the Lake: completeness is cheap, do the complete thing
  - Search Before Building: three layers of knowledge
  - User Sovereignty: AI recommends, human decides
  - Build for Yourself: the best tools solve your own problem

This adapter:
  - Analyzes task intent against gstack strategic principles
  - Produces direction signals (intent clusters, priorities, constraints, risks)
  - NEVER executes the gstack repo or any external tool
  - NEVER makes decisions — only provides advisory signals
  - truth_source is ALWAYS False

Stdlib only. No LLM. No external execution.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Optional, Tuple


# ═══════════════════════════════════════════════════════════════════════
# gstack Methodology Constants (from ETHOS.md)
# ═══════════════════════════════════════════════════════════════════════

# Core principles used as evaluation dimensions
PRINCIPLE_BOIL_THE_LAKE = "boil_the_lake"
PRINCIPLE_SEARCH_BEFORE_BUILD = "search_before_building"
PRINCIPLE_USER_SOVEREIGNTY = "user_sovereignty"
PRINCIPLE_BUILD_FOR_YOURSELF = "build_for_yourself"

GSTACK_PRINCIPLES = (
    PRINCIPLE_BOIL_THE_LAKE,
    PRINCIPLE_SEARCH_BEFORE_BUILD,
    PRINCIPLE_USER_SOVEREIGNTY,
    PRINCIPLE_BUILD_FOR_YOURSELF,
)

# Direction analysis dimensions
DIMENSION_SCOPE = "scope"
DIMENSION_PRIORITY = "priority"
DIMENSION_RISK = "risk"
DIMENSION_COMPLETENESS = "completeness"
DIMENSION_KNOWLEDGE = "knowledge"

ANALYSIS_DIMENSIONS = (
    DIMENSION_SCOPE,
    DIMENSION_PRIORITY,
    DIMENSION_RISK,
    DIMENSION_COMPLETENESS,
    DIMENSION_KNOWLEDGE,
)

# Known anti-patterns from gstack ETHOS
ANTI_PATTERNS = {
    "shortcut_over_completeness": (
        "Choosing a shortcut that covers 90% when the complete implementation "
        "costs minutes more. 'Ship the shortcut' is legacy thinking."
    ),
    "skip_research": (
        "Building from scratch without checking if the problem is already solved. "
        "The 1000x engineer searches first."
    ),
    "override_user_direction": (
        "AI models agreeing on a change and acting without user approval. "
        "User sovereignty overrides model consensus."
    ),
    "hypothetical_solution": (
        "Building for an abstract user instead of solving a real problem. "
        "The specificity of a real problem beats generality."
    ),
    "skip_completeness": (
        "Deferring tests or edge cases. Tests are the cheapest lake to boil."
    ),
}

# Office Hours — Six Forcing Questions (from gstack README)
OFFICE_HOURS_QUESTIONS = (
    "What is the actual pain — not the feature request?",
    "Who experiences this pain, and how often?",
    "What have you already tried?",
    "What does success look like — specifically?",
    "What is the narrowest wedge that proves the hypothesis?",
    "What premises am I challenging that you haven't questioned?",
)

# CEO Review — Four Scope Modes (from gstack README)
CEO_REVIEW_MODES = ("Expansion", "Selective Expansion", "Hold Scope", "Reduction")


# ═══════════════════════════════════════════════════════════════════════
# Config
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class GstackAdapterConfig:
    """Configuration for the gstack direction adapter.

    Controls which analysis dimensions and principles to apply.
    """
    task_intent: str = ""
    project_context: str = ""
    system_state_refs: Tuple[str, ...] = ()
    enabled_principles: Tuple[str, ...] = GSTACK_PRINCIPLES
    enabled_dimensions: Tuple[str, ...] = ANALYSIS_DIMENSIONS
    max_signals: int = 10
    dry_run: bool = True
    config_hash: str = ""

    def to_dict(self) -> dict:
        return {
            "task_intent": self.task_intent,
            "project_context": self.project_context,
            "system_state_refs": list(self.system_state_refs),
            "enabled_principles": list(self.enabled_principles),
            "enabled_dimensions": list(self.enabled_dimensions),
            "max_signals": self.max_signals,
            "dry_run": self.dry_run,
            "config_hash": self.config_hash,
        }


# ═══════════════════════════════════════════════════════════════════════
# Analysis Result
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class GstackAnalysisResult:
    """Result of gstack methodology analysis.

    Contains all direction signals produced by the analysis.
    truth_source is ALWAYS False.
    """
    config: Optional[GstackAdapterConfig] = None
    signals: Tuple = ()
    intent_clusters_summary: str = ""
    top_priority: str = ""
    primary_risk: str = ""
    completeness_gaps: Tuple[str, ...] = ()
    warnings: Tuple[str, ...] = ()
    truth_source: bool = False
    analysis_hash: str = ""


# ═══════════════════════════════════════════════════════════════════════
# Helper: Deterministic analysis from keyword-based rubrics
# ═══════════════════════════════════════════════════════════════════════

def _detect_intent_clusters(task_intent: str) -> Tuple[str, ...]:
    """Detect intent clusters from task description using keyword analysis.

    Deterministic. Same input → same output. No LLM.
    """
    clusters = []
    intent_lower = task_intent.lower()

    cluster_keywords = {
        "feature_development": ("build", "create", "implement", "add", "new feature"),
        "bug_fix": ("fix", "bug", "error", "broken", "regression", "crash"),
        "refactoring": ("refactor", "clean", "improve", "restructure", "reorganize"),
        "performance": ("faster", "performance", "optimize", "slow", "speed"),
        "security": ("security", "auth", "vulnerability", "protect", "secure"),
        "integration": ("integrate", "connect", "api", "external", "third-party"),
        "documentation": ("document", "readme", "doc", "explain", "describe"),
        "testing": ("test", "coverage", "verify", "validate", "assert"),
        "design_system": ("design", "ui", "ux", "style", "layout", "visual"),
        "devops_infra": ("deploy", "infra", "ci", "cd", "pipeline", "docker"),
    }

    for cluster, keywords in cluster_keywords.items():
        for kw in keywords:
            if kw in intent_lower:
                clusters.append(cluster)
                break

    return tuple(clusters) if clusters else ("general_development",)


def _detect_constraints(task_intent: str, project_context: str) -> Tuple[str, ...]:
    """Detect potential constraints from context. Deterministic."""
    constraints = []
    combined = (task_intent + " " + project_context).lower()

    constraint_patterns = {
        "existing_codebase": ("existing", "codebase", "current", "legacy"),
        "backward_compatibility": ("backward", "compatible", "breaking change"),
        "performance_bound": ("latency", "throughput", "memory", "budget"),
        "team_capacity": ("solo", "team of", "part-time", "weekend"),
        "deadline": ("deadline", "urgent", "asap", "by friday", "this week"),
        "dependency_lock": ("depends on", "blocked by", "waiting for"),
    }

    for constraint, keywords in constraint_patterns.items():
        for kw in keywords:
            if kw in combined:
                constraints.append(constraint)
                break

    return tuple(constraints)


def _assess_risks(intent_clusters: Tuple[str, ...],
                  constraints: Tuple[str, ...]) -> Tuple[str, ...]:
    """Assess risks based on intent clusters and constraints. Deterministic."""
    risks = []

    risk_mapping = {
        "feature_development": "Scope creep — new features tend to expand beyond initial spec",
        "refactoring": "Regression risk — refactoring without tests can introduce bugs",
        "integration": "Dependency risk — external API changes can break integration",
        "security": "Incomplete coverage — security fixes may leave attack vectors open",
        "performance": "Premature optimization — optimizing before measuring",
        "bug_fix": "Symptom vs root cause — fixing the symptom, not the cause",
    }

    for cluster in intent_clusters:
        if cluster in risk_mapping:
            risks.append(risk_mapping[cluster])

    if "deadline" in constraints:
        risks.append("Time pressure may force shortcuts over completeness")

    if "backward_compatibility" in constraints:
        risks.append("Backward compatibility may constrain design choices")

    return tuple(risks) if risks else ("No specific risks detected — insufficient context",)


def _generate_priority_ranking(intent_clusters: Tuple[str, ...],
                                task_intent: str) -> Tuple[str, ...]:
    """Generate priority ranking based on gstack principles. Deterministic.

    Priorities follow "Boil the Lake" — prefer completeness.
    """
    priorities = []

    priority_rules = (
        ("Understand the real pain before building", True),
        ("Search for existing solutions before creating new ones", True),
        ("Define success criteria — what does 'done' look like?", True),
        ("Ship the narrowest wedge that proves value", True),
        ("Do the complete thing — tests, edge cases, error handling", True),
        ("Verify with real usage before expanding scope", True),
        ("Document decisions and rationale", False),
        ("Plan for removability — keep integrations replaceable", False),
    )

    for i, (rule, is_primary) in enumerate(priority_rules):
        if is_primary:
            priorities.append(f"P{i}: {rule}")
        elif len(intent_clusters) > 2:
            priorities.append(f"P{i}: {rule}")

    return tuple(priorities)


def _compute_completeness_analysis(intent_clusters: Tuple[str, ...]) -> Tuple[str, ...]:
    """Compute completeness gaps based on 'Boil the Lake' principle."""
    gaps = []

    completeness_checklist = {
        "testing": ("testing" not in intent_clusters,
                     "Tests are the cheapest lake to boil — ensure test coverage"),
        "error_handling": (True,
                           "Complete error handling costs seconds with AI — do it now"),
        "edge_cases": (True,
                       "Edge cases are included in 'the complete thing' — don't skip"),
        "documentation": ("documentation" not in intent_clusters,
                          "Document decisions, not just code — future you will thank you"),
    }

    for gap_id, (condition, message) in completeness_checklist.items():
        if condition:
            gaps.append(message)

    return tuple(gaps)


# ═══════════════════════════════════════════════════════════════════════
# Adapter
# ═══════════════════════════════════════════════════════════════════════

class GstackDirectionAdapter:
    """Deterministic direction intelligence adapter using gstack methodology.

    This adapter APPLIES gstack's principles as an evaluation rubric.
    It does NOT execute the gstack repo.
    It does NOT connect to external services.
    It does NOT use LLMs.

    All outputs are EVIDENCE, never TRUTH.
    """

    PROVIDER_ID = "gstack_direction_intelligence"
    SOURCE = "gstack"

    @staticmethod
    def analyze(config: GstackAdapterConfig) -> GstackAnalysisResult:
        """Analyze task intent using gstack methodology.

        Returns a deterministic analysis with direction signals.
        Same input → same output. Always.
        """
        from v3.external.direction_intelligence import (
            make_direction_signal,
            SIGNAL_TYPE_INTENT_CLUSTER,
            SIGNAL_TYPE_PRIORITY_RANKING,
            SIGNAL_TYPE_CONSTRAINT_DETECTED,
            SIGNAL_TYPE_RISK_ASSESSMENT,
            SIGNAL_TYPE_SCOPE_RECOMMENDATION,
        )

        task_intent = config.task_intent
        project_context = config.project_context
        provenance = f"gstack_adapter:{hashlib.sha256(task_intent.encode()).hexdigest()[:8]}"

        # Step 1: Detect intent clusters
        intent_clusters = _detect_intent_clusters(task_intent)

        # Step 2: Detect constraints
        constraints = _detect_constraints(task_intent, project_context)

        # Step 3: Assess risks
        risks = _assess_risks(intent_clusters, constraints)

        # Step 4: Generate priority ranking
        priority_ranking = _generate_priority_ranking(intent_clusters, task_intent)

        # Step 5: Completeness analysis (Boil the Lake)
        completeness_gaps = _compute_completeness_analysis(intent_clusters)

        # Build signals
        signals = []

        # Signal 1: Intent clusters
        signals.append(make_direction_signal(
            signal_type=SIGNAL_TYPE_INTENT_CLUSTER,
            source=GstackDirectionAdapter.SOURCE,
            intent_clusters=intent_clusters,
            confidence=0.9,
            risk_flags=(),
            provenance=provenance,
        ))

        # Signal 2: Priority ranking
        signals.append(make_direction_signal(
            signal_type=SIGNAL_TYPE_PRIORITY_RANKING,
            source=GstackDirectionAdapter.SOURCE,
            priority_ranking=priority_ranking,
            recommendations=("Follow priority order — completeness before speed",),
            confidence=0.85,
            risk_flags=(),
            provenance=provenance,
        ))

        # Signal 3: Constraints detected
        if constraints:
            signals.append(make_direction_signal(
                signal_type=SIGNAL_TYPE_CONSTRAINT_DETECTED,
                source=GstackDirectionAdapter.SOURCE,
                constraints_detected=constraints,
                confidence=0.75,
                risk_flags=tuple(constraints),
                provenance=provenance,
            ))

        # Signal 4: Risk assessment
        signals.append(make_direction_signal(
            signal_type=SIGNAL_TYPE_RISK_ASSESSMENT,
            source=GstackDirectionAdapter.SOURCE,
            risk_assessment=risks,
            confidence=0.7,
            risk_flags=("advisory_only",),
            provenance=provenance,
        ))

        # Signal 5: Scope recommendation (CEO Review)
        scope_rec = (
            "Consider Reduction mode — narrowest wedge first. "
            "Ship the simplest thing that proves the hypothesis, "
            "then expand based on real usage feedback."
        )
        signals.append(make_direction_signal(
            signal_type=SIGNAL_TYPE_SCOPE_RECOMMENDATION,
            source=GstackDirectionAdapter.SOURCE,
            recommendations=(scope_rec,),
            confidence=0.8,
            risk_flags=(),
            provenance=provenance,
        ))

        # Trim to max_signals
        signals = signals[:config.max_signals]

        # Build result
        result = GstackAnalysisResult(
            config=config,
            signals=tuple(signals),
            intent_clusters_summary=f"Detected {len(intent_clusters)} intent cluster(s): {', '.join(intent_clusters)}",
            top_priority=priority_ranking[0] if priority_ranking else "",
            primary_risk=risks[0] if risks else "",
            completeness_gaps=completeness_gaps,
            warnings=(),
            truth_source=False,
        )
        hash_input = json.dumps({
            "task_intent": task_intent,
            "clusters": list(intent_clusters),
            "risks": list(risks),
        }, sort_keys=True, ensure_ascii=False)
        object.__setattr__(result, "analysis_hash",
                           hashlib.sha256(hash_input.encode()).hexdigest()[:16])
        return result

    @staticmethod
    def analyze_to_result(config: GstackAdapterConfig):
        """Full analysis pipeline: config → analysis → DirectionIntelligenceResult.

        Returns a DirectionIntelligenceResult ready for EventStore injection.
        """
        from v3.external.direction_intelligence import (
            DirectionIntelligenceResult,
            build_direction_intelligence_request,
            _compute_hash,
        )

        # Build request
        request = build_direction_intelligence_request(
            provider_id=GstackDirectionAdapter.PROVIDER_ID,
            task_intent=config.task_intent,
            project_context=config.project_context,
            system_state_refs=config.system_state_refs,
            max_signals=config.max_signals,
        )

        # Run analysis
        analysis = GstackDirectionAdapter.analyze(config)

        # Package as DirectionIntelligenceResult
        result = DirectionIntelligenceResult(
            request_id=request.request_id,
            provider_id=GstackDirectionAdapter.PROVIDER_ID,
            signals=analysis.signals,
            warnings=analysis.warnings,
            blocked=False,
            reason="",
            truth_source=False,
        )
        object.__setattr__(result, "result_hash", _compute_hash(result))
        return result

    @staticmethod
    def quick_analyze(task_intent: str, project_context: str = "") -> dict:
        """Quick analysis returning the external output contract format.

        Convenience method that returns normalized EEP outputs directly.
        """
        config = GstackAdapterConfig(
            task_intent=task_intent,
            project_context=project_context,
        )
        result = GstackDirectionAdapter.analyze_to_result(config)

        return {
            "provider": GstackDirectionAdapter.PROVIDER_ID,
            "source": GstackDirectionAdapter.SOURCE,
            "signal_type": "direction",
            "outputs": result.to_external_outputs(),
            "result_hash": result.result_hash,
            "blocked": result.blocked,
        }


# ═══════════════════════════════════════════════════════════════════════
# EventStore injection helper
# ═══════════════════════════════════════════════════════════════════════

def inject_gstack_direction_event(
    task_intent: str,
    project_context: str = "",
    system_state_refs: Tuple[str, ...] = (),
    registry_hash: str = "",
    adapter_spec_hash: str = "",
) -> dict:
    """Full injection pipeline for gstack direction signals.

    External System (gstack methodology)
    → GstackDirectionAdapter
    → Schema Validation
    → Evidence Bundle
    → Ready for EventStore.append()

    Returns a dict with:
      - result: DirectionIntelligenceResult
      - evidence_bundle: EvidenceBundle
      - status: "ready" | "blocked" | "validation_failed"
    """
    from v3.external.direction_intelligence import (
        validate_direction_intelligence_result,
        direction_signals_to_evidence,
    )
    from v3.external.direction_intelligence_policy import (
        default_direction_intelligence_policy,
        validate_result_against_policy,
    )
    from v3.external.direction_intelligence_profiles import gstack_direction_profile

    profile = gstack_direction_profile()
    policy = default_direction_intelligence_policy()

    config = GstackAdapterConfig(
        task_intent=task_intent,
        project_context=project_context,
        system_state_refs=system_state_refs,
    )

    result = GstackDirectionAdapter.analyze_to_result(config)

    # Schema validation
    validation = validate_direction_intelligence_result(result)
    if not validation.valid:
        return {
            "status": "validation_failed",
            "violations": validation.violations,
            "result": result,
            "evidence_bundle": None,
        }

    # Policy check
    policy_valid, policy_reason = validate_result_against_policy(result, policy)
    if not policy_valid:
        return {
            "status": "blocked",
            "reason": policy_reason,
            "result": result,
            "evidence_bundle": None,
        }

    # Evidence bundle
    evidence_bundle = direction_signals_to_evidence(
        result,
        registry_hash=registry_hash,
        adapter_spec_hash=adapter_spec_hash,
    )

    return {
        "status": "ready",
        "result": result,
        "evidence_bundle": evidence_bundle,
        "policy": policy,
        "profile": profile,
    }
