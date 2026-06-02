"""
superpowers Quality Adapter — v4.1.

Deterministic methodology adapter that produces quality intelligence
signals using the superpowers framework as an evaluation rubric.

superpowers principles (from README.md, CLAUDE.md, skills/):
  - Test-Driven Development: RED-GREEN-REFACTOR, tests first always
  - Systematic over ad-hoc: Process over guessing
  - Complexity reduction: Simplicity as primary goal
  - Evidence over claims: Verify before declaring success
  - Subagent-driven development: Two-stage review per task

This adapter:
  - Evaluates plans/code/traces against superpowers quality standards
  - Produces quality signals (defects, anti-patterns, improvements, refinements)
  - NEVER executes the superpowers repo or any external tool
  - NEVER rewrites code or overrides kernel decisions
  - truth_source is ALWAYS False

Stdlib only. No LLM. No external execution.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Optional, Tuple


# ═══════════════════════════════════════════════════════════════════════
# superpowers Methodology Constants
# ═══════════════════════════════════════════════════════════════════════

# Core principles used as evaluation dimensions
PRINCIPLE_TDD = "test_driven_development"
PRINCIPLE_SYSTEMATIC = "systematic_over_ad_hoc"
PRINCIPLE_COMPLEXITY_REDUCTION = "complexity_reduction"
PRINCIPLE_EVIDENCE_OVER_CLAIMS = "evidence_over_claims"

SUPERPOWERS_PRINCIPLES = (
    PRINCIPLE_TDD,
    PRINCIPLE_SYSTEMATIC,
    PRINCIPLE_COMPLEXITY_REDUCTION,
    PRINCIPLE_EVIDENCE_OVER_CLAIMS,
)

# Quality evaluation dimensions
DIMENSION_CORRECTNESS = "correctness"
DIMENSION_COMPLETENESS = "completeness"
DIMENSION_TESTABILITY = "testability"
DIMENSION_SIMPLICITY = "simplicity"
DIMENSION_MAINTAINABILITY = "maintainability"

QUALITY_DIMENSIONS = (
    DIMENSION_CORRECTNESS,
    DIMENSION_COMPLETENESS,
    DIMENSION_TESTABILITY,
    DIMENSION_SIMPLICITY,
    DIMENSION_MAINTAINABILITY,
)

# Known anti-patterns from superpowers skills
ANTI_PATTERNS = {
    "skip_tests": (
        "Writing code before tests. TDD requires RED first — "
        "write the failing test, watch it fail, then write code."
    ),
    "large_diff": (
        "Changes are too large for effective review. "
        "superpowers writing-plans enforces bite-sized tasks (2-5 min each)."
    ),
    "missing_verification": (
        "Declaring success without verification. "
        "verification-before-completion requires evidence the fix works."
    ),
    "no_root_cause": (
        "Fixing symptoms without finding root cause. "
        "systematic-debugging requires 4-phase root cause analysis."
    ),
    "premature_abstraction": (
        "Adding abstractions before they're needed. "
        "YAGNI — you aren't gonna need it. Three similar lines > premature abstraction."
    ),
    "magic_numbers": (
        "Unnamed constants in code. "
        "Use named constants for meaningful thresholds, delays, and limits."
    ),
    "deep_nesting": (
        "Code nesting exceeds 4 levels. "
        "Prefer early returns over nested conditionals."
    ),
    "large_function": (
        "Function exceeds 50 lines. "
        "Split large functions into focused pieces with clear responsibilities."
    ),
}

# superpowers workflow checklist (from README)
WORKFLOW_CHECKLIST = (
    "brainstorming: Was the design refined through Socratic questioning?",
    "writing-plans: Are tasks bite-sized (2-5 min) with exact file paths?",
    "test-driven-development: Were tests written and seen FAILING before code?",
    "subagent-driven-development: Was each task reviewed for spec + code quality?",
    "requesting-code-review: Were issues reported by severity?",
    "verification-before-completion: Is there evidence the change works?",
    "finishing-a-development-branch: Was the branch properly merged/PR'd?",
)

# Severity mapping for quality issues
SEVERITY_MAP = {
    "missing_tests": "critical",
    "no_verification": "critical",
    "large_function": "medium",
    "deep_nesting": "medium",
    "skip_tests": "critical",
    "large_diff": "medium",
    "missing_verification": "high",
    "no_root_cause": "high",
    "premature_abstraction": "low",
    "magic_numbers": "low",
}


# ═══════════════════════════════════════════════════════════════════════
# Config
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class SuperpowersAdapterConfig:
    """Configuration for the superpowers quality adapter."""
    target_type: str = ""
    target_content: str = ""
    target_refs: Tuple[str, ...] = ()
    enabled_principles: Tuple[str, ...] = SUPERPOWERS_PRINCIPLES
    enabled_dimensions: Tuple[str, ...] = QUALITY_DIMENSIONS
    max_signals: int = 20
    dry_run: bool = True
    config_hash: str = ""

    def to_dict(self) -> dict:
        return {
            "target_type": self.target_type,
            "target_content": self.target_content,
            "target_refs": list(self.target_refs),
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
class SuperpowersAnalysisResult:
    """Result of superpowers methodology quality analysis.

    Contains all quality signals produced by the analysis.
    truth_source is ALWAYS False.
    """
    config: Optional[SuperpowersAdapterConfig] = None
    signals: Tuple = ()
    overall_quality_score: float = 0.0
    defect_count: int = 0
    improvement_count: int = 0
    checklist_status: Tuple[str, ...] = ()
    warnings: Tuple[str, ...] = ()
    truth_source: bool = False
    analysis_hash: str = ""


# ═══════════════════════════════════════════════════════════════════════
# Deterministic Analysis Helpers
# ═══════════════════════════════════════════════════════════════════════

def _detect_defects(target_content: str, target_type: str) -> Tuple[Tuple[str, ...], ...]:
    """Detect potential defects in code/plan content. Deterministic keyword-based.

    Returns tuple of (defect_id, description, severity).
    """
    defects = []
    content_lower = target_content.lower()

    defect_patterns = {
        "missing_error_handling": (
            ("try" not in content_lower and "catch" not in content_lower and
             "error" in content_lower),
            "Error handling mentioned but no try/catch pattern detected",
            "high",
        ),
        "no_tests": (
            ("test" not in content_lower and target_type in ("code", "implementation")),
            "No test references found in code — TDD requires tests first",
            "critical",
        ),
        "hardcoded_secret": (
            any(kw in content_lower for kw in ("password", "secret", "api_key", "token"))
            and "env" not in content_lower,
            "Potential hardcoded credentials — use environment variables",
            "critical",
        ),
        "missing_pagination": (
            ("query" in content_lower or "select" in content_lower)
            and "limit" not in content_lower
            and "offset" not in content_lower,
            "Database query without pagination — add LIMIT constraint",
            "high",
        ),
        "console_log": (
            "console.log" in content_lower or "print(" in content_lower,
            "Debug output left in code — remove console.log/print statements",
            "low",
        ),
        "todo_comment": (
            "todo" in content_lower or "fixme" in content_lower or "hack" in content_lower,
            "Unresolved TODO/FIXME/HACK comments — address before shipping",
            "medium",
        ),
    }

    for defect_id, (condition, description, severity) in defect_patterns.items():
        if condition:
            defects.append((defect_id, description, severity))

    return tuple(defects)


def _detect_anti_patterns(target_content: str) -> Tuple[Tuple[str, ...], ...]:
    """Detect anti-patterns from superpowers methodology. Deterministic."""
    found = []
    content_lower = target_content.lower()

    # Deep nesting check: count indentation patterns
    lines = target_content.split("\n")
    max_indent = 0
    for line in lines:
        stripped = line.lstrip()
        if stripped and not stripped.startswith(("#", "//", "/*", "*", "<!--")):
            indent = len(line) - len(stripped)
            max_indent = max(max_indent, indent)

    if max_indent > 80:  # >5 levels of 4-space indent = > 80 leading spaces or >4 tabs
        found.append(("deep_nesting",
                       f"Maximum nesting depth detected: {max_indent // 4} levels. "
                       "Prefer early returns over deep nesting (>4 levels).",
                       "medium"))

    # Large function check (heuristic: count consecutive non-blank lines)
    consecutive = 0
    max_consecutive = 0
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith(("#", "//", "/*", "*", "<!--")):
            consecutive += 1
        else:
            max_consecutive = max(max_consecutive, consecutive)
            consecutive = 0
    max_consecutive = max(max_consecutive, consecutive)

    if max_consecutive > 50:
        found.append(("large_function",
                       f"Long function detected (~{max_consecutive} consecutive lines). "
                       "Split into focused pieces (<50 lines each).",
                       "medium"))

    # Magic numbers check
    import re
    magic_numbers = re.findall(r'(?<!\w)(?<!")(?<!-)(?<!#)\b(\d{2,6})\b(?!")', target_content)
    if len(magic_numbers) > 5:
        found.append(("magic_numbers",
                       f"Multiple magic numbers detected ({len(magic_numbers)}). "
                       "Use named constants for meaningful thresholds.",
                       "low"))

    return tuple(found)


def _generate_improvements(defects: Tuple,
                           anti_patterns: Tuple) -> Tuple[str, ...]:
    """Generate improvement suggestions from detected issues. Deterministic."""
    improvements = []

    improvement_map = {
        "missing_error_handling": "Add explicit error handling with try/catch blocks",
        "no_tests": "Write tests first (RED phase) before implementing (GREEN phase)",
        "hardcoded_secret": "Move credentials to environment variables or secret manager",
        "missing_pagination": "Add LIMIT/OFFSET or cursor-based pagination to queries",
        "console_log": "Replace console.log with proper logging framework",
        "todo_comment": "Address or track TODO items in issue tracker, remove comments",
        "deep_nesting": "Use early returns or extract nested blocks into helper functions",
        "large_function": "Split function into smaller, focused pieces with clear names",
        "magic_numbers": "Define named constants for all numeric thresholds",
    }

    for defect_id, _, _ in defects:
        if defect_id in improvement_map:
            improvements.append(improvement_map[defect_id])

    for ap_id, _, _ in anti_patterns:
        if ap_id in improvement_map:
            improvements.append(improvement_map[ap_id])

    # Add general superpowers workflow improvements
    improvements.append(
        "Consider following the full superpowers workflow: "
        "brainstorming → writing-plans → TDD → subagent-driven-development → "
        "code-review → verification → finish-branch"
    )

    return tuple(improvements)


def _compute_quality_score(defects: Tuple, anti_patterns: Tuple) -> float:
    """Compute a deterministic quality score from detected issues.

    Starts at 1.0, subtracts for each issue weighted by severity.
    """
    score = 1.0

    severity_penalties = {
        "critical": 0.25,
        "high": 0.15,
        "medium": 0.08,
        "low": 0.03,
    }

    for _, _, severity in defects:
        score -= severity_penalties.get(severity, 0.05)

    for _, _, severity in anti_patterns:
        score -= severity_penalties.get(severity, 0.05)

    return max(0.0, min(1.0, score))


def _evaluate_workflow_checklist(target_type: str,
                                  target_content: str) -> Tuple[str, ...]:
    """Evaluate against the superpowers workflow checklist. Deterministic."""
    results = []
    content_lower = target_content.lower()

    checklist_indicators = {
        "brainstorming": ("design" in content_lower or "brainstorm" in content_lower),
        "writing-plans": ("plan" in content_lower or "task" in content_lower),
        "test-driven-development": ("test" in content_lower and "fail" in content_lower),
        "subagent-driven-development": ("subagent" in content_lower or "review" in content_lower),
        "requesting-code-review": ("review" in content_lower),
        "verification-before-completion": ("verify" in content_lower or "evidence" in content_lower),
        "finishing-a-development-branch": ("merge" in content_lower or "branch" in content_lower),
    }

    for step, indicator in checklist_indicators.items():
        status = "PASS" if indicator else "MISSING"
        results.append(f"[{status}] {step}")

    return tuple(results)


# ═══════════════════════════════════════════════════════════════════════
# Adapter
# ═══════════════════════════════════════════════════════════════════════

class SuperpowersQualityAdapter:
    """Deterministic quality intelligence adapter using superpowers methodology.

    This adapter APPLIES superpowers' principles as an evaluation rubric.
    It does NOT execute the superpowers repo.
    It does NOT connect to external services.
    It does NOT use LLMs.

    All outputs are EVIDENCE, never TRUTH.
    """

    PROVIDER_ID = "superpowers_quality_intelligence"
    SOURCE = "superpowers"

    @staticmethod
    def analyze(config: SuperpowersAdapterConfig) -> SuperpowersAnalysisResult:
        """Analyze code/plan using superpowers methodology.

        Returns a deterministic analysis with quality signals.
        Same input → same output. Always.
        """
        from v3.external.quality_intelligence import (
            make_quality_signal,
            SIGNAL_TYPE_DEFECT,
            SIGNAL_TYPE_ANTI_PATTERN,
            SIGNAL_TYPE_IMPROVEMENT,
            SIGNAL_TYPE_REFINEMENT,
            SIGNAL_TYPE_COMPLETENESS_GAP,
            SIGNAL_TYPE_TESTING_GAP,
            SEVERITY_CRITICAL,
            SEVERITY_HIGH,
            SEVERITY_MEDIUM,
            SEVERITY_LOW,
        )

        target_type = config.target_type
        target_content = config.target_content
        provenance = f"superpowers_adapter:{hashlib.sha256(target_content.encode()[:200]).hexdigest()[:8]}"

        # Step 1: Detect defects
        defects = _detect_defects(target_content, target_type)

        # Step 2: Detect anti-patterns
        anti_patterns = _detect_anti_patterns(target_content)

        # Step 3: Generate improvements
        improvements = _generate_improvements(defects, anti_patterns)

        # Step 4: Compute quality score
        quality_score = _compute_quality_score(defects, anti_patterns)

        # Step 5: Evaluate workflow checklist
        checklist_status = _evaluate_workflow_checklist(target_type, target_content)

        # Build signals
        signals = []

        # Signal 1: Defects
        for defect_id, desc, severity in defects:
            signals.append(make_quality_signal(
                signal_type=SIGNAL_TYPE_DEFECT,
                source=SuperpowersQualityAdapter.SOURCE,
                quality_score=quality_score,
                defects=(desc,),
                severity=severity,
                confidence=0.9,
                risk_flags=("advisory_only",),
                provenance=provenance,
            ))

        # Signal 2: Anti-patterns
        for ap_id, desc, severity in anti_patterns:
            signals.append(make_quality_signal(
                signal_type=SIGNAL_TYPE_ANTI_PATTERN,
                source=SuperpowersQualityAdapter.SOURCE,
                quality_score=quality_score,
                anti_patterns=(desc,),
                severity=severity,
                confidence=0.85,
                risk_flags=("advisory_only",),
                provenance=provenance,
            ))

        # Signal 3: Improvements
        if improvements:
            signals.append(make_quality_signal(
                signal_type=SIGNAL_TYPE_IMPROVEMENT,
                source=SuperpowersQualityAdapter.SOURCE,
                quality_score=quality_score,
                improvements=improvements,
                severity=SEVERITY_MEDIUM,
                confidence=0.8,
                risk_flags=(),
                provenance=provenance,
            ))

        # Signal 4: Refinement suggestions (from superpowers workflow)
        refinement = (
            "Apply RED-GREEN-REFACTOR cycle: write failing test → minimal code → refactor. "
            "Use subagent-driven development with two-stage review per task. "
            "Verify before declaring completion — evidence over claims."
        )
        signals.append(make_quality_signal(
            signal_type=SIGNAL_TYPE_REFINEMENT,
            source=SuperpowersQualityAdapter.SOURCE,
            quality_score=quality_score,
            refinement_suggestions=(refinement,),
            severity=SEVERITY_MEDIUM,
            confidence=0.75,
            risk_flags=(),
            provenance=provenance,
        ))

        # Signal 5: Completeness gaps
        completeness_gaps = []
        if not checklist_status:
            completeness_gaps.append("No workflow steps detected — consider superpowers workflow")
        for status_line in checklist_status:
            if "MISSING" in status_line:
                completeness_gaps.append(status_line)

        if completeness_gaps:
            signals.append(make_quality_signal(
                signal_type=SIGNAL_TYPE_COMPLETENESS_GAP,
                source=SuperpowersQualityAdapter.SOURCE,
                quality_score=quality_score,
                anti_patterns=tuple(completeness_gaps),
                severity=SEVERITY_MEDIUM,
                confidence=0.7,
                risk_flags=(),
                provenance=provenance,
            ))

        # Signal 6: Testing gaps
        if target_type in ("code", "implementation") and "test" not in target_content.lower():
            signals.append(make_quality_signal(
                signal_type=SIGNAL_TYPE_TESTING_GAP,
                source=SuperpowersQualityAdapter.SOURCE,
                quality_score=quality_score,
                defects=("No test evidence found — TDD requires tests before code",),
                severity=SEVERITY_CRITICAL,
                confidence=0.95,
                risk_flags=("advisory_only",),
                provenance=provenance,
            ))

        # Trim to max_signals
        signals = signals[:config.max_signals]

        result = SuperpowersAnalysisResult(
            config=config,
            signals=tuple(signals),
            overall_quality_score=quality_score,
            defect_count=len(defects),
            improvement_count=len(improvements),
            checklist_status=checklist_status,
            warnings=(),
            truth_source=False,
        )
        hash_input = json.dumps({
            "target_type": target_type,
            "score": quality_score,
            "defect_count": len(defects),
        }, sort_keys=True, ensure_ascii=False)
        object.__setattr__(result, "analysis_hash",
                           hashlib.sha256(hash_input.encode()).hexdigest()[:16])
        return result

    @staticmethod
    def analyze_to_result(config: SuperpowersAdapterConfig):
        """Full analysis pipeline: config → analysis → QualityIntelligenceResult.

        Returns a QualityIntelligenceResult ready for EventStore injection.
        """
        from v3.external.quality_intelligence import (
            QualityIntelligenceResult,
            build_quality_intelligence_request,
            _compute_hash,
        )

        request = build_quality_intelligence_request(
            provider_id=SuperpowersQualityAdapter.PROVIDER_ID,
            target_type=config.target_type,
            target_content=config.target_content,
            target_refs=config.target_refs,
            max_signals=config.max_signals,
        )

        analysis = SuperpowersQualityAdapter.analyze(config)

        result = QualityIntelligenceResult(
            request_id=request.request_id,
            provider_id=SuperpowersQualityAdapter.PROVIDER_ID,
            signals=analysis.signals,
            quality_score=analysis.overall_quality_score,
            warnings=analysis.warnings,
            blocked=False,
            reason="",
            truth_source=False,
        )
        object.__setattr__(result, "result_hash", _compute_hash(result))
        return result

    @staticmethod
    def quick_analyze(target_content: str, target_type: str = "code") -> dict:
        """Quick analysis returning the external output contract format.

        Convenience method that returns normalized EEP outputs directly.
        """
        config = SuperpowersAdapterConfig(
            target_type=target_type,
            target_content=target_content,
        )
        result = SuperpowersQualityAdapter.analyze_to_result(config)

        return {
            "provider": SuperpowersQualityAdapter.PROVIDER_ID,
            "source": SuperpowersQualityAdapter.SOURCE,
            "signal_type": "quality",
            "quality_score": result.quality_score,
            "outputs": result.to_external_outputs(),
            "result_hash": result.result_hash,
            "blocked": result.blocked,
        }


# ═══════════════════════════════════════════════════════════════════════
# EventStore injection helper
# ═══════════════════════════════════════════════════════════════════════

def inject_superpowers_quality_event(
    target_content: str,
    target_type: str = "code",
    target_refs: Tuple[str, ...] = (),
    registry_hash: str = "",
    adapter_spec_hash: str = "",
) -> dict:
    """Full injection pipeline for superpowers quality signals.

    External System (superpowers methodology)
    → SuperpowersQualityAdapter
    → Schema Validation
    → Evidence Bundle
    → Ready for EventStore.append()

    Returns a dict with:
      - result: QualityIntelligenceResult
      - evidence_bundle: EvidenceBundle
      - status: "ready" | "blocked" | "validation_failed"
    """
    from v3.external.quality_intelligence import (
        validate_quality_intelligence_result,
        quality_signals_to_evidence,
    )
    from v3.external.quality_intelligence_policy import (
        default_quality_intelligence_policy,
        validate_result_against_policy,
    )
    from v3.external.quality_intelligence_profiles import superpowers_quality_profile

    profile = superpowers_quality_profile()
    policy = default_quality_intelligence_policy()

    config = SuperpowersAdapterConfig(
        target_type=target_type,
        target_content=target_content,
        target_refs=target_refs,
    )

    result = SuperpowersQualityAdapter.analyze_to_result(config)

    # Schema validation
    validation = validate_quality_intelligence_result(result)
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
    evidence_bundle = quality_signals_to_evidence(
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
