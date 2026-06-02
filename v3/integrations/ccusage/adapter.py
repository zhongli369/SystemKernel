"""
ccusage Adapter — CLI-based token usage and cost tracking.

Phase 16a: New subprocess + CLI adapter. Uses `ccusage` CLI
(npm package) or `npx ccusage` as fallback.

Fetches token usage reports from Claude Code and other AI coding tools.
Cost data is EVIDENCE, never truth — cached when CLI unavailable.

All output is EvidenceRecord-wrapped with truth_source=False.
Uses Phase 15c lifecycle: retry (quick: 2 attempts, 0.5s),
degradation (ccusage_unavailable → use_cache).

Requires: ccusage >= 0.1.0 (npm install -g ccusage, or npx ccusage)
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

CLI_NAME = "ccusage"
NPX_CLI = "npx"
REQUIRED_VERSION = ">=0.1.0"
INSTALL_HINT = "npm install -g ccusage"
DEFAULT_TIMEOUT = 10
ADAPTER_ID = "ccusage"

# Cache for degraded mode
_cache: Optional[dict] = None


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
# CLI Detection (with npx fallback)
# ═══════════════════════════════════════════════════════════════════════

def _resolve_cli() -> Optional[list[str]]:
    if shutil.which(CLI_NAME):
        return [CLI_NAME]
    if shutil.which(NPX_CLI):
        return [NPX_CLI, CLI_NAME]
    return None


def _check_cli() -> bool:
    return _resolve_cli() is not None


def _check_version() -> Tuple[bool, str]:
    cli = _resolve_cli()
    if not cli:
        return False, "not found"
    try:
        result = subprocess.run(
            cli + ["--version"],
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
    cli = _resolve_cli()
    if not cli:
        return AdapterResult(
            stderr=f"{CLI_NAME} CLI not found. Install: {INSTALL_HINT}",
            exit_code=-1, degraded=True,
            error=f"{CLI_NAME} not found",
        )

    start = time.time()
    try:
        result = subprocess.run(
            cli + args,
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

def report() -> AdapterResult:
    """Get token usage report as JSON.

    If CLI unavailable, returns cached data (degraded mode).
    """
    result = _run(["report", "--format", "json"])

    if result.success:
        global _cache
        try:
            _cache = json.loads(result.stdout)
        except json.JSONDecodeError:
            pass
    elif not _check_cli() and _cache is not None:
        # Degraded: return cached data
        return AdapterResult(
            stdout=json.dumps(_cache),
            exit_code=0, degraded=True,
            evidence_hash=hashlib.sha256(
                f"ccusage:cache:{json.dumps(_cache)}:0".encode()
            ).hexdigest()[:16],
        )

    return result


def daily(date: str = "") -> AdapterResult:
    """Get daily token usage summary."""
    args = ["daily"]
    if date:
        args.extend(["--date", date])
    return _run(args)


def check_health() -> dict:
    cli_ok = _check_cli()
    ver_ok, version_str = _check_version()
    return {
        "adapter_id": ADAPTER_ID,
        "cli_available": cli_ok,
        "version_ok": ver_ok,
        "version": version_str,
        "cli_name": CLI_NAME,
        "npx_fallback": shutil.which(NPX_CLI) is not None,
        "required_version": REQUIRED_VERSION,
        "degraded": not (cli_ok and ver_ok),
        "cache_available": _cache is not None,
    }


def wrap_as_evidence(result: AdapterResult, operation: str = "") -> dict:
    return {
        "evidence_type": "ccusage_result",
        "source": ADAPTER_ID,
        "operation": operation,
        "payload_summary": result.stdout[:500],
        "truth_source": False,
        "evidence_hash": result.evidence_hash,
        "exit_code": result.exit_code,
        "degraded": result.degraded,
    }
