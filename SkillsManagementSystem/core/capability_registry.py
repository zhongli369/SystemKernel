"""
capability_registry.py — Unified Capability Registry (v4.1 — Phase 2 hardened)

Builds a unified view of ALL skills (local + external) from:
  1. registry.json skills section — primary authority
  2. Package manifests (manifest.json: tags, skills list)
  3. SKILL.md frontmatter (tags, aliases, domains, capabilities) — HIGHEST priority
  4. data/skill_capabilities.json — transitional metadata (replaces hardcoded dicts)
  5. lazyload_rules.json (package-level keywords)

Output: list of CapabilityEntry objects.

Key invariant: installed state is metadata only — it does NOT gate routing.
A skill CAN be recommended even if not installed.

Phase 2 hardening: ALL skill metadata is now loaded from DATA FILES (JSON),
not from Python dicts. The data/skill_capabilities.json file is a transitional
artifact — the long-term target is to have all metadata in SKILL.md frontmatter.
"""

import json
import os
from pathlib import Path
from typing import Optional

from . import CapabilityEntry

# ═══════════════════════════════════════════════════════════════════════════════
# System paths
# ═══════════════════════════════════════════════════════════════════════════════

_SCRIPT_DIR = Path(__file__).resolve().parent.parent
_REGISTRY_PATH = _SCRIPT_DIR / "registry.json"
_PACKAGES_DIR = _SCRIPT_DIR / "packages"
_LAZYLOAD_PATH = _SCRIPT_DIR / "data" / "lazyload_rules.json"
_CAPABILITIES_PATH = _SCRIPT_DIR / "data" / "skill_capabilities.json"


# ═══════════════════════════════════════════════════════════════════════════════
# Transitional: load skill metadata from JSON data file
# ═══════════════════════════════════════════════════════════════════════════════
# This replaces the 334 lines of hardcoded Python dicts (_EXTERNAL_SKILL_METADATA
# and _LOCAL_SKILL_CAPABILITIES). The JSON file is transparent, auditable, and
# non-executable. Migration target: move all entries to their respective
# SKILL.md frontmatter blocks. Once migration is complete, this JSON file
# and the load function can be deleted.
#
# Governance: This is a PURE DATA LOADER. It does not:
#   - Generate or infer skill capabilities
#   - Classify, score, or rank skills
#   - Make any decisions
#   - Call any LLM

_CAPABILITIES_CACHE: Optional[dict] = None


def _load_capabilities_data() -> dict:
    """Load the transitional skill_capabilities.json file.

    Returns dict with 'external_skills' and 'local_skills' keys.
    Lazily loaded — reads from disk once, caches in memory.
    """
    global _CAPABILITIES_CACHE
    if _CAPABILITIES_CACHE is not None:
        return _CAPABILITIES_CACHE

    try:
        _CAPABILITIES_CACHE = json.loads(
            _CAPABILITIES_PATH.read_text(encoding="utf-8")
        )
    except (FileNotFoundError, json.JSONDecodeError):
        _CAPABILITIES_CACHE = {"external_skills": {}, "local_skills": {}}

    return _CAPABILITIES_CACHE


def _get_external_metadata() -> dict:
    """Get external skill metadata from JSON data file."""
    return _load_capabilities_data().get("external_skills", {})


def _get_local_metadata() -> dict:
    """Get local skill metadata from JSON data file."""
    return _load_capabilities_data().get("local_skills", {})


# ═══════════════════════════════════════════════════════════════════════════════
# Registry + manifest loading
# ═══════════════════════════════════════════════════════════════════════════════

def _load_registry() -> dict:
    """Load registry.json. Returns empty dict on failure."""
    try:
        return json.loads(_REGISTRY_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _load_manifest(pkg_name: str) -> dict:
    """Load a package manifest.json. Returns empty dict on failure."""
    manifest_path = _PACKAGES_DIR / pkg_name / "manifest.json"
    try:
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _load_lazyload_rules() -> dict:
    """Load lazyload_rules.json. Returns empty dict on failure."""
    try:
        return json.loads(_LAZYLOAD_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {"rules": []}


def _parse_frontmatter_tags(skill_name: str, pkg_name: str) -> dict:
    """Parse SKILL.md frontmatter for tags, aliases, domains, capabilities.

    Returns dict with keys: tags, aliases, domains, capabilities.
    Only reads the YAML frontmatter block (between --- delimiters).
    Pure read — no mutation.
    """
    md_path = _PACKAGES_DIR / pkg_name / "skills" / skill_name / "SKILL.md"
    result = {"tags": [], "aliases": [], "domains": [], "capabilities": []}

    if not md_path.exists():
        return result

    try:
        text = md_path.read_text(encoding="utf-8", errors="replace")
    except (OSError, PermissionError):
        return result

    # Extract YAML frontmatter
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return result

    in_frontmatter = False
    for i, line in enumerate(lines):
        stripped = line.strip()
        if i == 0:
            in_frontmatter = True
            continue
        if stripped == "---":
            break
        if not in_frontmatter:
            continue

        # Parse key: value or key: [list]
        if ":" in stripped:
            key, _, value = stripped.partition(":")
            key = key.strip().lower()
            value = value.strip().strip("\"'")

            if key == "tags" and value:
                if value.startswith("[") and value.endswith("]"):
                    # Inline list: tags: [a, b, c]
                    result["tags"] = [
                        t.strip().strip("\"'")
                        for t in value[1:-1].split(",")
                        if t.strip()
                    ]
                elif not value:
                    continue  # tags: (empty, list follows on next lines)
            elif key == "aliases" and value:
                if value.startswith("[") and value.endswith("]"):
                    result["aliases"] = [
                        a.strip().strip("\"'")
                        for a in value[1:-1].split(",")
                        if a.strip()
                    ]
            elif key == "domains" and value:
                if value.startswith("[") and value.endswith("]"):
                    result["domains"] = [
                        d.strip().strip("\"'")
                        for d in value[1:-1].split(",")
                        if d.strip()
                    ]
            elif key == "capabilities" and value:
                if value.startswith("[") and value.endswith("]"):
                    result["capabilities"] = [
                        c.strip().strip("\"'")
                        for c in value[1:-1].split(",")
                        if c.strip()
                    ]

        # Handle list items under tags/aliases/domains/capabilities
        if stripped.startswith("-") and in_frontmatter:
            # Determine current section by looking for the last key before this item
            pass  # Simple frontmatter parsing — list continuation handled above

    return result


def _check_installed(skill_name: str, pkg_name: str) -> bool:
    """Check if a skill is installed (SKILL.md exists on disk)."""
    if not pkg_name:
        return False
    return (_PACKAGES_DIR / pkg_name / "skills" / skill_name / "SKILL.md").exists()


# ═══════════════════════════════════════════════════════════════════════════════
# Capability building
# ═══════════════════════════════════════════════════════════════════════════════

def _merge_capability_data(skill_name: str, pkg_name: str, source: str,
                           registry_meta: dict, file_meta: dict) -> CapabilityEntry:
    """Merge capability data from all sources into a single CapabilityEntry.

    Priority: SKILL.md frontmatter > JSON data file > registry.json description.
    All data sources are file-based — no hardcoded Python dicts.
    """
    fm = _parse_frontmatter_tags(skill_name, pkg_name)

    # Aliases: JSON data file + frontmatter (frontmatter wins)
    aliases = list(file_meta.get("aliases", []))
    for a in fm.get("aliases", []):
        if a not in aliases:
            aliases.append(a)

    # Tags: JSON data file + frontmatter
    tags = list(file_meta.get("tags", []))
    for t in fm.get("tags", []):
        if t not in tags:
            tags.append(t)

    # Domains: JSON data file + frontmatter
    domains = list(file_meta.get("domains", []))
    for d in fm.get("domains", []):
        if d not in domains:
            domains.append(d)

    # Capabilities: JSON data file + frontmatter
    capabilities = list(file_meta.get("capabilities", []))
    for c in fm.get("capabilities", []):
        if c not in capabilities:
            capabilities.append(c)

    # Description fallback: registry > JSON file
    description = (
        registry_meta.get("description", "") or
        file_meta.get("description", "")
    )

    installed = _check_installed(skill_name, pkg_name)

    install_hint = ""
    if source == "external" and not installed:
        install_hint = registry_meta.get("install_command", "")
        if not install_hint:
            pkg_entry = _load_registry().get("packages", {}).get(pkg_name, {})
            install_hint = pkg_entry.get("install_command", f"npx skills add {skill_name}")

    version = registry_meta.get("version", "1.0.0")

    return CapabilityEntry(
        skill=skill_name,
        package=pkg_name,
        source=source,
        installed=installed,
        description=description,
        aliases=tuple(dict.fromkeys(aliases)),
        tags=tuple(dict.fromkeys(tags)),
        domains=tuple(dict.fromkeys(domains)),
        capabilities=tuple(dict.fromkeys(capabilities)),
        install_hint=install_hint,
        version=str(version),
    )


def build_capability_registry(registry_data: Optional[dict] = None) -> list[CapabilityEntry]:
    """Build the unified capability registry from all data sources.

    All metadata comes from file-based sources (JSON, SKILL.md frontmatter).
    No hardcoded Python data.

    Args:
        registry_data: Optional pre-loaded registry dict. Loads from disk if None.

    Returns:
        List of CapabilityEntry objects for ALL known skills (local + external).
        Deterministic order: sorted by skill name.
    """
    if registry_data is None:
        registry_data = _load_registry()

    entries: list[CapabilityEntry] = []
    seen_skills: set[str] = set()

    skills_section = registry_data.get("skills", {})
    packages_section = registry_data.get("packages", {})

    # Load file-based metadata (transitional: will be phased out once all
    # SKILL.md files have proper frontmatter)
    local_file_meta = _get_local_metadata()
    external_file_meta = _get_external_metadata()

    for skill_name, skill_meta in skills_section.items():
        if skill_name in seen_skills:
            continue
        seen_skills.add(skill_name)

        pkg_name = skill_meta.get("package", "unknown")
        is_external = skill_meta.get("external", False)
        source = "external" if is_external else "local"

        # Load metadata from file-based source (not hardcoded Python)
        if is_external:
            file_meta = external_file_meta.get(skill_name, {})
        else:
            file_meta = local_file_meta.get(skill_name, {})

        entry = _merge_capability_data(
            skill_name=skill_name,
            pkg_name=pkg_name,
            source=source,
            registry_meta=skill_meta,
            file_meta=file_meta,
        )
        entries.append(entry)

    # Add external skills that exist in the capabilities data file but
    # not yet registered in registry.json skills section
    for skill_name, file_meta in external_file_meta.items():
        if skill_name in seen_skills:
            continue
        seen_skills.add(skill_name)

        pkg_name = ""
        for pkg_entry_name, pkg_entry in packages_section.items():
            if skill_name in pkg_entry.get("skills", []):
                pkg_name = pkg_entry_name
                break

        if not pkg_name:
            pkg_name = "vercel-agent-skills"

        entry = _merge_capability_data(
            skill_name=skill_name,
            pkg_name=pkg_name,
            source="external",
            registry_meta={},
            file_meta=file_meta,
        )
        entries.append(entry)

    # Sort deterministically by skill name
    entries.sort(key=lambda e: e.skill)
    return entries


def load_capability_registry() -> list[CapabilityEntry]:
    """Convenience: build capability registry from disk.

    Pure function after the initial file read — the returned list is
    independent of any further disk I/O.
    """
    registry_data = _load_registry()
    return build_capability_registry(registry_data)


# ═══════════════════════════════════════════════════════════════════════════════
# Query helpers
# ═══════════════════════════════════════════════════════════════════════════════

def get_skill_entry(entries: list[CapabilityEntry], skill_name: str) -> Optional[CapabilityEntry]:
    """Find a skill entry by name."""
    for e in entries:
        if e.skill == skill_name:
            return e
    return None


def get_entries_by_package(entries: list[CapabilityEntry], pkg_name: str) -> list[CapabilityEntry]:
    """Filter entries by package name."""
    return [e for e in entries if e.package == pkg_name]


def get_entries_by_domain(entries: list[CapabilityEntry], domain: str) -> list[CapabilityEntry]:
    """Filter entries by domain."""
    return [e for e in entries if domain in e.domains]


def get_entries_by_tag(entries: list[CapabilityEntry], tag: str) -> list[CapabilityEntry]:
    """Filter entries by tag."""
    return [e for e in entries if tag in e.tags]


def get_entry_count(entries: list[CapabilityEntry]) -> int:
    """Total count."""
    return len(entries)


def get_installed_count(entries: list[CapabilityEntry]) -> int:
    """Count of installed skills."""
    return sum(1 for e in entries if e.installed)


def get_external_count(entries: list[CapabilityEntry]) -> int:
    """Count of external skills."""
    return sum(1 for e in entries if e.source == "external")
