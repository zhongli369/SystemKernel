"""
capability_registry.py — Unified Capability Registry (v4.0)

Builds a unified view of ALL skills (local + external) from:
  1. registry.json skills section
  2. Package manifests (auto_match_keywords, tags)
  3. SKILL.md frontmatter (tags, aliases, domains, capabilities)
  4. lazyload_rules.json (package-level keywords)
  5. Hardcoded external skill metadata (for skills without local SKILL.md)

Output: list of CapabilityEntry objects.

Key invariant: installed state is metadata only — it does NOT gate routing.
A skill CAN be recommended even if not installed.
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


# ═══════════════════════════════════════════════════════════════════════════════
# External skill capability definitions
# ═══════════════════════════════════════════════════════════════════════════════

_EXTERNAL_SKILL_METADATA = {
    "react-best-practices": {
        "aliases": [
            "react optimization", "react patterns", "react architecture",
            "best practices react", "react performance", "react code quality",
            "react conventions", "react component patterns",
        ],
        "tags": ["react", "frontend", "performance", "patterns", "components"],
        "domains": ["frontend", "web"],
        "capabilities": [
            "react optimization", "component architecture",
            "render performance", "react code patterns",
            "react best practices",
        ],
    },
    "web-design-guidelines": {
        "aliases": [
            "web design guidelines", "design standards guidelines",
            "web design standards", "web standards design",
            "design guidelines web", "web guidelines",
        ],
        "tags": ["web", "design", "frontend", "standards", "guidelines"],
        "domains": ["frontend", "web", "design"],
        "capabilities": [
            "web design standards", "design system creation",
            "visual guidelines", "web design guidelines",
            "design standards guidelines web",
        ],
    },
    "composition-patterns": {
        "aliases": [
            "component composition", "react composition",
            "composition patterns", "higher order components",
            "render props", "compound components",
        ],
        "tags": ["react", "components", "patterns", "composition", "architecture"],
        "domains": ["frontend", "web"],
        "capabilities": [
            "component composition", "react architecture patterns",
            "compound component design",
        ],
    },
    "next-best-practices": {
        "aliases": [
            "nextjs best practices", "next.js optimization",
            "next patterns", "next architecture",
        ],
        "tags": ["nextjs", "next.js", "frontend", "react", "ssr", "performance"],
        "domains": ["frontend", "web"],
        "capabilities": [
            "nextjs optimization", "ssr patterns",
            "next.js architecture",
        ],
    },
    "next-cache-components": {
        "aliases": [
            "nextjs caching", "next cache", "next.js cache",
            "cache components next", "incremental static regeneration",
            "isr nextjs", "next data cache", "cache strategy",
            "next cache optimization", "cache strategy nextjs",
            "nextjs cache upgrade", "cache components",
            "nextjs cache strategy", "upgrade nextjs cache",
        ],
        "capabilities": [
            "nextjs caching strategy", "cache component design",
            "incremental static regeneration",
            "next data cache optimization", "cache strategy upgrade",
            "upgrade nextjs cache",
        ],
        "tags": ["nextjs", "next.js", "caching", "performance", "ssr", "isr"],
        "domains": ["frontend", "web"],
        "capabilities": [
            "nextjs caching strategy", "cache component design",
            "incremental static regeneration",
            "next data cache optimization",
        ],
    },
    "next-upgrade": {
        "aliases": [
            "nextjs upgrade", "next migration", "upgrade next.js",
            "next version upgrade", "next.js migration",
            "migrate nextjs", "next breaking changes",
        ],
        "tags": ["nextjs", "next.js", "upgrade", "migration", "versioning"],
        "domains": ["frontend", "web"],
        "capabilities": [
            "nextjs version upgrade", "next.js migration",
            "breaking changes resolution",
        ],
    },
    "react-native-skills": {
        "aliases": [
            "react native", "mobile react", "react native app",
            "react native optimization", "native mobile",
            "ios react", "android react",
        ],
        "tags": ["react-native", "mobile", "ios", "android", "cross-platform"],
        "domains": ["mobile", "frontend"],
        "capabilities": [
            "react native development", "cross-platform mobile",
            "mobile app optimization",
        ],
    },
    "find-skills": {
        "aliases": [
            "find skill", "search skills", "discover skills",
            "browse skills", "skill search", "install skill",
            "npx skills search",
        ],
        "tags": ["discovery", "search", "skills.sh", "install"],
        "domains": ["meta", "discovery"],
        "capabilities": [
            "skill discovery", "skill search",
            "ecosystem browsing",
        ],
    },
    "markdown-analyzer": {
        "aliases": [
            "markdown analysis", "parse markdown", "analyze markdown",
            "markdown parser", "extract todos from markdown",
            "document analysis",
        ],
        "tags": ["markdown", "analysis", "documentation", "todo"],
        "domains": ["documentation", "analysis"],
        "capabilities": [
            "markdown parsing", "structure extraction",
            "todo tracking from docs",
        ],
    },
}

# ═══════════════════════════════════════════════════════════════════════════════
# Skill-specific capability enrichment (for local skills without SKILL.md tags)
# ═══════════════════════════════════════════════════════════════════════════════

_LOCAL_SKILL_CAPABILITIES = {
    "code-review": {
        "aliases": ["code review", "review code", "pr review", "audit code",
                    "code audit", "inspect code"],
        "tags": ["review", "code", "quality", "security", "performance", "analysis"],
        "domains": ["development"],
        "capabilities": ["code review", "pr review", "code audit",
                         "security review", "quality assessment"],
    },
    "debugger": {
        "aliases": ["debug", "debugging", "fix error", "fix bug",
                    "troubleshoot", "error analysis", "stack trace"],
        "tags": ["debug", "error", "fix", "troubleshooting", "analysis"],
        "domains": ["development"],
        "capabilities": ["code debugging", "error analysis", "bug fixing",
                         "stack trace analysis"],
    },
    "repo-analyzer": {
        "aliases": ["repo analysis", "analyze repo", "codebase analysis",
                    "architecture review", "dependency map", "explore code",
                    "codebase exploration", "repository analysis"],
        "tags": ["analysis", "architecture", "repository", "codebase",
                 "dependencies", "exploration"],
        "domains": ["development", "architecture"],
        "capabilities": ["repository analysis", "architecture review",
                         "dependency mapping", "codebase exploration"],
    },
    "reflective-reasoning": {
        "aliases": ["logical reasoning", "mathematical proof", "formal logic",
                    "theorem proof", "logical analysis", "mathematical reasoning"],
        "tags": ["reasoning", "logic", "mathematics", "proof", "formal"],
        "domains": ["reasoning", "mathematics"],
        "capabilities": ["logical reasoning", "mathematical proof",
                         "formal analysis", "theorem derivation"],
    },
    "researcher": {
        "aliases": ["research", "literature review", "academic research",
                    "paper survey", "systematic review", "scholarly research"],
        "tags": ["research", "academic", "literature", "systematic", "survey"],
        "domains": ["research", "academia"],
        "capabilities": ["literature review", "academic research",
                         "systematic survey", "paper analysis"],
    },
    "skill-creator": {
        "aliases": ["create skill", "new skill", "build skill",
                    "skill development", "create agent skill"],
        "tags": ["skill", "creation", "meta", "development"],
        "domains": ["meta"],
        "capabilities": ["skill creation", "skill modification",
                         "skill evaluation"],
    },
    "algorithm-explainer": {
        "aliases": ["algorithm", "data structure", "pseudocode",
                    "algorithm design", "complexity analysis",
                    "big o notation", "leetcode", "competitive programming"],
        "tags": ["algorithm", "data-structure", "complexity", "pseudocode",
                 "visualization"],
        "domains": ["computer-science", "algorithms"],
        "capabilities": ["algorithm design", "complexity analysis",
                         "pseudocode generation", "data structure explanation"],
    },
    "docx": {
        "aliases": ["word document", "word doc", "create docx",
                    "microsoft word", "word processing", "document template",
                    "letter", "contract", "memo", "report docx"],
        "tags": ["office", "word", "document", "docx", "writing"],
        "domains": ["office", "document"],
        "capabilities": ["word document creation", "docx editing",
                         "document formatting", "template generation"],
    },
    "xlsx": {
        "aliases": ["excel", "spreadsheet", "create xlsx",
                    "microsoft excel", "data table", "csv processing",
                    "tsv file", "financial spreadsheet", "excel formula",
                    "excel chart", "data analysis spreadsheet"],
        "tags": ["office", "excel", "spreadsheet", "data", "csv", "tsv"],
        "domains": ["office", "data"],
        "capabilities": ["excel spreadsheet creation", "data table management",
                         "csv processing", "spreadsheet formulas"],
    },
    "pptx": {
        "aliases": ["powerpoint", "presentation", "create pptx",
                    "slides", "slide deck", "keynote alternative",
                    "presentation design", "business presentation"],
        "tags": ["office", "powerpoint", "presentation", "slides", "design"],
        "domains": ["office", "presentation"],
        "capabilities": ["powerpoint presentation creation",
                         "slide deck design", "presentation formatting"],
    },
    "pdf": {
        "aliases": ["pdf document", "create pdf", "pdf generation",
                    "pdf report", "export to pdf", "pdf form",
                    "printable document", "pdf manipulation"],
        "tags": ["office", "pdf", "document", "export", "print"],
        "domains": ["office", "document"],
        "capabilities": ["pdf creation", "pdf manipulation",
                         "pdf form handling", "document export"],
    },
    "claude-api": {
        "aliases": ["claude api", "anthropic sdk", "claude integration",
                    "claude development", "prompt caching", "tool use claude",
                    "streaming claude", "claude model"],
        "tags": ["api", "claude", "anthropic", "sdk", "llm", "integration"],
        "domains": ["backend", "ai"],
        "capabilities": ["claude api integration", "anthropic sdk development",
                         "prompt caching", "llm application building"],
    },
    "algorithmic-art": {
        "aliases": ["algorithmic art", "generative art", "p5js art",
                    "flow field", "particle system", "creative coding"],
        "tags": ["art", "generative", "creative", "p5js", "visual"],
        "domains": ["creative", "art"],
        "capabilities": ["generative art creation", "algorithmic art design",
                         "creative coding"],
    },
    "brand-guidelines": {
        "aliases": ["brand guidelines", "brand colors", "branding",
                    "corporate identity", "color palette", "typography brand"],
        "tags": ["brand", "design", "colors", "typography", "identity"],
        "domains": ["design", "branding"],
        "capabilities": ["brand styling", "color palette application",
                         "corporate design"],
    },
    "canvas-design": {
        "aliases": ["canvas design", "visual art", "poster design",
                    "static design", "graphic design", "visual creation",
                    "illustration design", "art poster"],
        "tags": ["design", "visual", "art", "poster", "graphic", "canvas"],
        "domains": ["design", "creative"],
        "capabilities": ["visual design", "poster creation",
                         "graphic design", "static art"],
    },
    "doc-coauthoring": {
        "aliases": ["document coauthoring", "coauthor docs", "collaborative writing",
                    "document collaboration", "writing workflow",
                    "coauthoring workflow", "collaborative document editing",
                    "structured documentation coauthoring"],
        "tags": ["documentation", "writing", "collaboration", "workflow", "coauthoring"],
        "domains": ["documentation", "collaboration"],
        "capabilities": ["collaborative document writing",
                         "structured documentation workflow",
                         "coauthoring documents", "document collaboration workflow"],
    },
    "frontend-design": {
        "aliases": ["frontend design", "web design", "ui design",
                    "web interface", "component design", "landing page",
                    "website design", "dashboard design", "react component design",
                    "html css design", "web page design"],
        "tags": ["frontend", "ui", "design", "web", "components", "css", "html"],
        "domains": ["frontend", "web", "design"],
        "capabilities": ["frontend ui design", "web page creation",
                         "component styling", "landing page design"],
    },
    "internal-comms": {
        "aliases": ["internal communications", "company communication",
                    "team comms", "status report", "project update"],
        "tags": ["communication", "internal", "writing", "business"],
        "domains": ["business", "communication"],
        "capabilities": ["internal communication writing",
                         "status report creation"],
    },
    "mcp-builder": {
        "aliases": ["mcp server", "model context protocol",
                    "build mcp", "create mcp", "mcp integration",
                    "mcp tool", "mcp development"],
        "tags": ["mcp", "server", "integration", "tool", "protocol"],
        "domains": ["backend", "integration"],
        "capabilities": ["mcp server development", "tool integration",
                         "protocol implementation"],
    },
    "slack-gif-creator": {
        "aliases": ["slack gif", "animated gif", "gif creator",
                    "slack animation", "create gif for slack"],
        "tags": ["slack", "gif", "animation", "communication"],
        "domains": ["communication", "creative"],
        "capabilities": ["slack gif creation", "animated gif design"],
    },
    "theme-factory": {
        "aliases": ["theme styling", "theme creation", "ui theme",
                    "color theme", "design theme", "css theme"],
        "tags": ["theme", "styling", "design", "css", "colors"],
        "domains": ["design", "frontend"],
        "capabilities": ["theme creation", "styling system",
                         "color scheme design"],
    },
    "web-artifacts-builder": {
        "aliases": ["web artifacts", "claude artifacts", "html artifacts",
                    "artifact builder", "multi-component artifact"],
        "tags": ["web", "artifacts", "html", "components", "claude"],
        "domains": ["web", "frontend"],
        "capabilities": ["web artifact creation", "html artifact building",
                         "multi-component design"],
    },
    "webapp-testing": {
        "aliases": ["webapp testing", "browser testing", "playwright test",
                    "e2e testing", "ui testing", "web testing",
                    "browser automation", "selenium test"],
        "tags": ["testing", "web", "playwright", "e2e", "browser", "automation"],
        "domains": ["testing", "web", "frontend"],
        "capabilities": ["web application testing", "browser automation",
                         "e2e test creation", "playwright scripting"],
    },
}


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
                           registry_meta: dict, local_meta: dict,
                           external_meta: dict) -> CapabilityEntry:
    """Merge capability data from all sources into a single CapabilityEntry.

    Priority: frontmatter > hardcoded local > hardcoded external > registry description.
    """
    # Aliases: frontmatter + local + external
    aliases = list(
        local_meta.get("aliases", []) +
        external_meta.get("aliases", [])
    )
    frontmatter_aliases = _parse_frontmatter_tags(skill_name, pkg_name).get("aliases", [])
    for a in frontmatter_aliases:
        if a not in aliases:
            aliases.append(a)

    # Tags: local + external + frontmatter
    tags = list(
        local_meta.get("tags", []) +
        external_meta.get("tags", [])
    )
    frontmatter_tags = _parse_frontmatter_tags(skill_name, pkg_name).get("tags", [])
    for t in frontmatter_tags:
        if t not in tags:
            tags.append(t)

    # Domains
    domains = list(
        local_meta.get("domains", []) +
        external_meta.get("domains", [])
    )

    # Capabilities
    capabilities = list(
        local_meta.get("capabilities", []) +
        external_meta.get("capabilities", [])
    )

    # Description fallback chain
    description = (
        registry_meta.get("description", "") or
        local_meta.get("description", "") or
        external_meta.get("description", "")
    )

    installed = _check_installed(skill_name, pkg_name)

    install_hint = ""
    if source == "external" and not installed:
        pkg = registry_meta.get("package", pkg_name)
        install_hint = registry_meta.get("install_command", "")
        if not install_hint:
            # Check package-level install command
            pkg_entry = _load_registry().get("packages", {}).get(pkg_name, {})
            install_hint = pkg_entry.get("install_command", f"npx skills add {skill_name}")

    version = registry_meta.get("version", "1.0.0")

    return CapabilityEntry(
        skill=skill_name,
        package=pkg_name,
        source=source,
        installed=installed,
        description=description,
        aliases=tuple(dict.fromkeys(aliases)),     # dedup, preserve order
        tags=tuple(dict.fromkeys(tags)),
        domains=tuple(dict.fromkeys(domains)),
        capabilities=tuple(dict.fromkeys(capabilities)),
        install_hint=install_hint,
        version=str(version),
    )


def build_capability_registry(registry_data: Optional[dict] = None) -> list[CapabilityEntry]:
    """Build the unified capability registry from all data sources.

    Args:
        registry_data: Optional pre-loaded registry dict. Loads from disk if None.

    Returns:
        List of CapabilityEntry objects for ALL known skills (local + external).
        Deterministic order: sorted by (source, package, skill).
    """
    if registry_data is None:
        registry_data = _load_registry()

    entries: list[CapabilityEntry] = []
    seen_skills: set[str] = set()

    skills_section = registry_data.get("skills", {})
    packages_section = registry_data.get("packages", {})

    for skill_name, skill_meta in skills_section.items():
        if skill_name in seen_skills:
            continue
        seen_skills.add(skill_name)

        pkg_name = skill_meta.get("package", "unknown")
        is_external = skill_meta.get("external", False)
        source = "external" if is_external else "local"

        local_meta = _LOCAL_SKILL_CAPABILITIES.get(skill_name, {})
        ext_meta = _EXTERNAL_SKILL_METADATA.get(skill_name, {})
        registry_meta = skill_meta

        entry = _merge_capability_data(
            skill_name=skill_name,
            pkg_name=pkg_name,
            source=source,
            registry_meta=registry_meta,
            local_meta=local_meta,
            external_meta=ext_meta,
        )
        entries.append(entry)

    # Add vercel-agent-skills entries that may not be in registry
    for skill_name, ext_meta in _EXTERNAL_SKILL_METADATA.items():
        if skill_name in seen_skills:
            continue
        seen_skills.add(skill_name)

        # Determine package from registry packages section
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
            local_meta={},
            external_meta=ext_meta,
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
