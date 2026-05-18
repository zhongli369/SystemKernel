#!/usr/bin/env python3
"""
core.py — Skill System Core Module (v3.5 Architecture)

Capability Registry + Suggestion Engine (pure passive system).
No execution authority. No workflow control. No side effects.

Architecture:
  SkillRegistry  — metadata storage, package mapping, keyword tags, descriptions
  QuerySystem    — find_skill(), search_skill(), list_skills()
  SuggestionEngine — suggest_skill(task_context) — pure function

All classes are pure: they accept data at construction time and never
modify external state, write files, call subprocesses, or interact
with TaskSystem.
"""

import re
from pathlib import Path


# ═══════════════════════════════════════════════════════════════════════════════
# Tokenization (shared utility)
# ═══════════════════════════════════════════════════════════════════════════════

def _tokenize(text: str) -> set:
    """Tokenize text into lowercase keyword tokens (unigrams + bigrams)."""
    text = re.sub(r"[^a-z0-9\s]", " ", str(text).lower())
    words = text.split()
    tokens = set()
    for w in words:
        if len(w) >= 2:
            tokens.add(w)
    for i in range(len(words) - 1):
        bigram = f"{words[i]} {words[i+1]}"
        if len(bigram) >= 4:
            tokens.add(bigram)
    return tokens


# ═══════════════════════════════════════════════════════════════════════════════
# SkillRegistry — metadata storage & lookup
# ═══════════════════════════════════════════════════════════════════════════════

class SkillRegistry:
    """Pure skill metadata registry.

    Stores skill metadata, package mappings, keyword tags, and descriptions.
    No filesystem access after construction. No side effects.
    """

    def __init__(self, registry_data: dict):
        self._data = registry_data

    # ── skill-level queries ──────────────────────────────────────────────

    def get_skill(self, name: str) -> dict | None:
        """Return metadata for a single skill, or None."""
        return self._data.get("skills", {}).get(name)

    def list_skills(self, package: str = None) -> list[dict]:
        """List all skills, optionally filtered by package.

        Returns list of {name, version, description, package, ...} dicts.
        """
        result = []
        for name, meta in self._data.get("skills", {}).items():
            if package and meta.get("package") != package:
                continue
            result.append({"name": name, **meta})
        result.sort(key=lambda s: s["name"])
        return result

    def list_all_skill_names(self) -> list[str]:
        """Return sorted list of all registered skill names."""
        return sorted(self._data.get("skills", {}).keys())

    # ── package-level queries ────────────────────────────────────────────

    def list_packages(self) -> list[dict]:
        """List all packages with metadata."""
        result = []
        for name, meta in self._data.get("packages", {}).items():
            result.append({"name": name, **meta})
        result.sort(key=lambda p: p["name"])
        return result

    def get_package(self, name: str) -> dict | None:
        """Return metadata for a single package, or None."""
        return self._data.get("packages", {}).get(name)

    def get_package_skills(self, package: str) -> list[str]:
        """Return skill names belonging to a package."""
        pkg = self._data.get("packages", {}).get(package, {})
        return list(pkg.get("skills", []))

    def get_skill_package(self, skill_name: str) -> str | None:
        """Return the package name a skill belongs to, or None."""
        skill = self.get_skill(skill_name)
        return skill.get("package") if skill else None

    # ── keyword / tag queries ────────────────────────────────────────────

    def get_skill_keywords(self, name: str) -> set:
        """Extract keyword tokens from a skill's name + description."""
        skill = self.get_skill(name)
        if not skill:
            return set()
        text = f"{name.replace('-', ' ')} {skill.get('description', '')}"
        return _tokenize(text)

    # ── bulk access ──────────────────────────────────────────────────────

    @property
    def skills(self) -> dict:
        return self._data.get("skills", {})

    @property
    def packages(self) -> dict:
        return self._data.get("packages", {})

    @property
    def raw(self) -> dict:
        return self._data


# ═══════════════════════════════════════════════════════════════════════════════
# QuerySystem — pure lookup operations
# ═══════════════════════════════════════════════════════════════════════════════

class QuerySystem:
    """Pure query operations over the skill registry.

    All methods are read-only: registry lookup only, no task context,
    no intelligent execution decisions.
    """

    def __init__(self, registry: SkillRegistry):
        self.registry = registry

    def find_skill(self, query: str) -> list[dict]:
        """Search skills by name + description keyword overlap.

        Returns list of {name, score, description, package} sorted by relevance.
        """
        query_tokens = _tokenize(query)
        if not query_tokens:
            return []

        results = []
        for skill_name, skill in self.registry.skills.items():
            name_text = skill_name.replace("-", " ").replace("_", " ")
            desc_text = skill.get("description", "").lower()

            name_tokens = _tokenize(name_text)
            desc_tokens = _tokenize(desc_text)

            name_overlap = query_tokens & name_tokens
            desc_overlap = query_tokens & desc_tokens

            name_score = len(name_overlap) / max(len(query_tokens), 1)
            desc_score = len(desc_overlap) / max(len(query_tokens), 1) * 0.3
            score = round(name_score * 0.7 + desc_score, 4)

            if score > 0.05:
                results.append({
                    "name": skill_name,
                    "score": score,
                    "description": skill.get("description", ""),
                    "package": skill.get("package", ""),
                })

        results.sort(key=lambda r: r["score"], reverse=True)
        return results

    def search_skill(self, query: str) -> list[dict]:
        """Alias for find_skill — standard query interface."""
        return self.find_skill(query)

    def list_skills(self, package: str = None) -> list[dict]:
        """List skills, optionally filtered by package."""
        return self.registry.list_skills(package=package)

    def list_packages(self) -> list[dict]:
        """List all packages."""
        return self.registry.list_packages()

    def get_skill_info(self, name: str) -> dict | None:
        """Get full metadata for a specific skill."""
        return self.registry.get_skill(name)


# ═══════════════════════════════════════════════════════════════════════════════
# SuggestionEngine — delegated to v4.0 capability-based routing pipeline
# ═══════════════════════════════════════════════════════════════════════════════

class SuggestionEngine:
    """Pure suggestion system — delegates to v4.0 capability-based routing.

    Maintains backward compatibility with v3.5 API while using the new
    routing engine (core/routing_pipeline.py) under the hood.

    No hardcoded keyword rules. No ML. No side effects.
    """

    def __init__(self, registry: SkillRegistry = None,
                 keyword_map: list = None):
        # keyword_map is accepted for backward compat but IGNORED
        self.registry = registry

    def suggest_skill(self, task_context: dict) -> dict:
        """Suggest a skill based on task context.

        Delegates to v4.0 capability-based routing pipeline.
        Maintains v3.5 output format for backward compatibility.

        This is a PURE function — no filesystem access, no subprocess calls,
        no state modification, no TaskSystem interaction.
        """
        from core.routing_pipeline import suggest as _pipeline_suggest

        step_content = task_context.get("step_content", "")
        context_log = task_context.get("context_log", "")
        query = f"{step_content} {context_log or ''}".strip()

        if not query:
            return {
                "skill": None,
                "package": None,
                "confidence": 0.0,
                "reason": "No step content or context provided",
                "applicable_step": task_context.get("step_id", ""),
                "alternatives": [],
            }

        result = _pipeline_suggest(query)
        tm = result.get("top_match")

        output = {
            "skill": tm["skill"] if tm else None,
            "package": tm["package"] if tm else None,
            "confidence": tm["confidence"] if tm else 0.0,
            "reason": (tm["reason"] if tm else
                       result.get("score_breakdown", {}).get("reason", "No match found")),
            "applicable_step": task_context.get("step_id", ""),
            "alternatives": result.get("alternatives", []),
            "install_required": result.get("install_required", False),
            "install_hint": result.get("install_hint"),
        }

        if result.get("ambiguity"):
            output["ambiguity"] = True
            output["ambiguity_detail"] = result.get("ambiguity_detail")

        return output


# ═══════════════════════════════════════════════════════════════════════════════
# Convenience loader — load registry from disk (one-time, at init)
# ═══════════════════════════════════════════════════════════════════════════════

def load_registry_from_disk(path: str = None) -> SkillRegistry:
    """Load registry.json into a SkillRegistry instance.

    This is the ONLY filesystem interaction — one-time load at initialization.
    After this, all operations are pure.
    """
    import json

    if path is None:
        path = Path(__file__).resolve().parent / "registry.json"
    else:
        path = Path(path)

    data = json.loads(path.read_text(encoding="utf-8"))
    return SkillRegistry(data)


def create_query_system(path: str = None) -> QuerySystem:
    """Create a QuerySystem from registry.json on disk."""
    return QuerySystem(load_registry_from_disk(path))


def create_suggestion_engine(path: str = None) -> SuggestionEngine:
    """Create a SuggestionEngine (v4.0 capability-based routing).

    The path parameter is accepted for backward compatibility but ignored —
    the v4.0 engine uses the unified capability registry from core/routing_pipeline.py.
    """
    return SuggestionEngine()
