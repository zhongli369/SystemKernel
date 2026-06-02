"""
Crawl4AI Adapter — URL to LLM-friendly Markdown.

Phase 16b-1: New core provider. Uses crawl4ai CLI for web scraping.
Follows the Phase 16a unified adapter pattern: subprocess + EvidenceRecord.

All output is EvidenceRecord-wrapped with truth_source=False.
Uses sandbox_policy.network_readonly (GET only, no file writes).

Requires: crawl4ai (pip install crawl4ai)
Type: context
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import time
from dataclasses import dataclass
from typing import Optional


# ═══════════════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════════════

CLI_NAME = "crawl4ai"
INSTALL_HINT = "pip install crawl4ai"
DEFAULT_TIMEOUT = 30
ADAPTER_ID = "crawl4ai"


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


def _check_cli() -> bool:
    return shutil.which(CLI_NAME) is not None


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

def crawl(url: str) -> AdapterResult:
    """Crawl a URL and return LLM-friendly Markdown content.

    Uses crawl4ai's built-in Markdown extraction. JS rendering is
    available via the underlying playwright integration.

    Timeout: 30s (reasonable for web page fetching).
    Retry: policy_quick (2 attempts, 0.5s backoff).
    Degradation: error (crawl failure should be visible, not silent).
    """
    return _run(["crawl", url, "--format", "markdown", "--output", "-"])


def check_health() -> dict:
    cli_ok = _check_cli()
    return {
        "adapter_id": ADAPTER_ID,
        "cli_available": cli_ok,
        "capability_type": "context",
        "degraded": not cli_ok,
        "cli_name": CLI_NAME,
        "install_hint": INSTALL_HINT,
        "timeout_s": DEFAULT_TIMEOUT,
        "retry_policy": "quick",
        "degradation": "error",
        "network_required": True,
    }


def wrap_as_evidence(result: AdapterResult, operation: str = "") -> dict:
    return {
        "evidence_type": "crawl4ai_result",
        "source": ADAPTER_ID,
        "operation": operation,
        "payload_summary": result.stdout[:500],
        "truth_source": False,
        "evidence_hash": result.evidence_hash,
        "exit_code": result.exit_code,
        "degraded": result.degraded,
    }
