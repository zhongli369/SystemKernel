"""
external_skill_adapter.py — External Skill Integration Adapter (v4.0)

Ensures external skills (external=true, npx-installable) participate in routing
on EQUAL footing with local skills.

Key invariant:
  installed=false does NOT prevent recommendation.
  If an external skill is the top match, include install_hint in output.

Responsibilities:
  - Detect external skills in capability registry
  - Provide install_hint for top matches that are external + not installed
  - Flag install_required in RoutingResult when appropriate
  - NEVER auto-execute installation
"""

from . import CapabilityEntry


def is_external(entry: CapabilityEntry) -> bool:
    """Check if a capability entry is external."""
    return entry.source == "external"


def needs_install(entry: CapabilityEntry) -> bool:
    """Check if a skill needs installation (external + not installed)."""
    return is_external(entry) and not entry.installed


def get_install_hint(entry: CapabilityEntry) -> str | None:
    """Get the install hint for an external skill, if applicable."""
    if not needs_install(entry):
        return None
    return entry.install_hint or f"npx skills add {entry.skill}"


def enrich_external_match(match: dict) -> dict:
    """Enrich a match result with external skill metadata.

    Adds 'install_required' and 'install_hint' fields if the matched
    skill is external and not installed.
    """
    entry = match.get("entry")
    if entry is None:
        return match

    match["install_required"] = needs_install(entry)
    match["install_hint"] = get_install_hint(entry)
    match["source"] = entry.source
    match["installed"] = entry.installed
    return match


def filter_installable(entries: list[CapabilityEntry]) -> list[CapabilityEntry]:
    """Filter to only external entries that have install hints.

    Used for suggesting which external packages to install.
    """
    return [e for e in entries if is_external(e) and e.install_hint]


def external_skill_summary(entries: list[CapabilityEntry]) -> dict:
    """Produce a summary of external skills available.

    Returns {total_external, installed_external, not_installed_external, hints}.
    """
    external = [e for e in entries if is_external(e)]
    installed = [e for e in external if e.installed]
    not_installed = [e for e in external if not e.installed]

    return {
        "total_external": len(external),
        "installed_external": len(installed),
        "not_installed_external": len(not_installed),
        "install_hints": {
            e.skill: get_install_hint(e) for e in not_installed
        },
    }
