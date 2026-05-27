# Phase 14A — Provider Trial Selection

**Status:** COMPLETE

## Summary

- Candidates evaluated: 8
- Recommended: **repomix**
- Rejected: openhands, mem0, graphiti
- Deferred: ecc, continue
- Ability+10 Complexity+300 risk: **low**

## Ranking

1. **`repomix`** — score=303, risk_ratio=0.09, verdict=recommended
   Reasons: highest_total_score, high_capability_gain, low_complexity_delta, existing_adapter, can_produce_evidence, reversible
2. **`ccusage`** — score=245, risk_ratio=0.11, verdict=acceptable
   Reasons: positive_score, low_complexity_delta, existing_adapter, can_produce_evidence, reversible
3. **`anthropic_skills`** — score=43, risk_ratio=0.8, verdict=acceptable
   Reasons: low_positive_score, reversible
4. **`ecc`** — score=0, risk_ratio=1.7, verdict=defer
   Reasons: no_adapter_requires_network, zero_or_negative_score, reversible, requires_network
5. **`continue`** — score=0, risk_ratio=4.4, verdict=defer
   Reasons: no_adapter_requires_install, reversible, requires_install
6. **`openhands`** — score=0, risk_ratio=19.0, verdict=reject
   Reasons: requires_external_service, requires_network, requires_install, requires_external_service
7. **`mem0`** — score=0, risk_ratio=20.5, verdict=reject
   Reasons: requires_external_service, requires_network, requires_install, requires_external_service
8. **`graphiti`** — score=0, risk_ratio=20.5, verdict=reject
   Reasons: requires_external_service, requires_network, requires_install, requires_external_service

## Recommendation

Proceed with **repomix** as the first real-provider trial.
Expected capability gain: 9/10
Expected complexity delta: 1/10
Risk ratio: 0.09

High-risk providers (mem0, Graphiti, OpenHands/SWE-agent) are rejected for now.
They require external services, network access, and installation.
ECC is deferred — strategic value but no adapter, no evidence model, requires clone.

## Safety

- **No provider executed in this phase**
- **No network access**
- **No installation**
- **Kernel purity: 100/100**
- **Memory runtime: unchanged**