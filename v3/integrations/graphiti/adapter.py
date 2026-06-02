"""
Graphiti Adapter — CLI-based temporal knowledge graph backend.

Phase 16a: Upgraded from Python SDK stub to subprocess + CLI pattern.
Uses `graphiti` CLI for all operations. Falls back gracefully when
CLI is not available (degradation: skip).

All output is EvidenceRecord-wrapped with truth_source=False.
Uses Phase 15c lifecycle: retry (standard), degradation (graphiti_unavailable).

Requires: graphiti >= 0.1.0 (pip install graphiti)
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import time
from dataclasses import dataclass
from typing import Optional, Tuple


# ═══════════════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════════════

CLI_NAME = "graphiti"
REQUIRED_VERSION = ">=0.1.0"
INSTALL_HINT = "pip install graphiti"
DEFAULT_TIMEOUT = 20
ADAPTER_ID = "graphiti"


# ═══════════════════════════════════════════════════════════════════════
# Adapter Result
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class AdapterResult:
    stdout: str = ""
    stderr: str = ""
    exit_code: int = -1
    duration_ms: float = 0.0
    evidence_hash: str = ""
    degraded: bool = False
    error: str = ""

    @property
    def success(self) -> bool:
        return self.exit_code == 0 and not self.degraded

    def to_dict(self) -> dict:
        return {
            "stdout": self.stdout[:500],
            "stderr": self.stderr[:500],
            "exit_code": self.exit_code,
            "duration_ms": self.duration_ms,
            "evidence_hash": self.evidence_hash,
            "degraded": self.degraded,
            "error": self.error,
        }


# ═══════════════════════════════════════════════════════════════════════
# CLI Detection
# ═══════════════════════════════════════════════════════════════════════

def _check_cli() -> bool:
    return shutil.which(CLI_NAME) is not None


def _check_version() -> Tuple[bool, str]:
    if not _check_cli():
        return False, "not found"
    try:
        result = subprocess.run(
            [CLI_NAME, "--version"],
            capture_output=True, text=True, timeout=5,
        )
        version = result.stdout.strip() or result.stderr.strip()
        return result.returncode == 0, version
    except Exception:
        return False, "version check failed"


# ═══════════════════════════════════════════════════════════════════════
# CLI Execution
# ═══════════════════════════════════════════════════════════════════════

def _run(args: list[str], timeout: int = DEFAULT_TIMEOUT) -> AdapterResult:
    if not _check_cli():
        return AdapterResult(
            stderr=f"{CLI_NAME} CLI not found. Install: {INSTALL_HINT}",
            exit_code=-1, degraded=True,
            error=f"{CLI_NAME} not found",
        )

    start = time.time()
    try:
        result = subprocess.run(
            [CLI_NAME] + args,
            capture_output=True, text=True, timeout=timeout, shell=False,
        )
        stdout = result.stdout or ""
        stderr = result.stderr or ""
        exit_code = result.returncode
    except subprocess.TimeoutExpired:
        stdout = ""; stderr = f"Timeout after {timeout}s"; exit_code = 124
    except Exception as e:
        stdout = ""; stderr = str(e); exit_code = -1

    duration_ms = (time.time() - start) * 1000
    evidence_hash = hashlib.sha256(
        f"{CLI_NAME}:{' '.join(args)}:{stdout}:{exit_code}".encode()
    ).hexdigest()[:16]

    return AdapterResult(
        stdout=stdout, stderr=stderr, exit_code=exit_code,
        duration_ms=duration_ms, evidence_hash=evidence_hash,
    )


# ═══════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════

def ingest(episode_json: str) -> AdapterResult:
    """Ingest an episode into the knowledge graph.

    Args:
        episode_json: JSON string with episode data.
    """
    return _run(["ingest", episode_json])


def search(query: str) -> AdapterResult:
    """Search the knowledge graph for entities and facts."""
    return _run(["search", query])


def entities_list() -> AdapterResult:
    """List all entities in the knowledge graph."""
    return _run(["entities", "list"])


def edges_list(entity_id: str = "") -> AdapterResult:
    """List edges/relationships, optionally filtered by entity."""
    args = ["edges", "list"]
    if entity_id:
        args.extend(["--entity-id", entity_id])
    return _run(args)


def check_health() -> dict:
    cli_ok = _check_cli()
    ver_ok, version = _check_version()
    return {
        "adapter_id": ADAPTER_ID,
        "cli_available": cli_ok,
        "version_ok": ver_ok,
        "version": version,
        "cli_name": CLI_NAME,
        "required_version": REQUIRED_VERSION,
        "degraded": not (cli_ok and ver_ok),
    }


def wrap_as_evidence(result: AdapterResult, operation: str = "") -> dict:
    return {
        "evidence_type": "graphiti_result",
        "source": ADAPTER_ID,
        "operation": operation,
        "payload_summary": result.stdout[:500],
        "truth_source": False,
        "evidence_hash": result.evidence_hash,
        "exit_code": result.exit_code,
        "degraded": result.degraded,
    }
