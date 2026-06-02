"""
Trivy Adapter — Vulnerability and configuration scanner.

Phase 16b-1: New core provider. Uses trivy CLI for security scanning.
Follows the Phase 16a unified adapter pattern: subprocess + EvidenceRecord.

Scans filesystem paths for known vulnerabilities (CVEs) and
misconfigurations. Output is JSON structured for downstream analysis.

All output is EvidenceRecord-wrapped with truth_source=False.
Uses sandbox_policy.isolated_build (read-only access to target).

Requires: trivy (brew install trivy / apt install trivy / docker)
Type: tool (capability_type)

Warning: Scans can take 120s+ on large repositories. Timeout enforced.
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

CLI_NAME = "trivy"
INSTALL_HINT = "brew install trivy / apt install trivy / docker run aquasec/trivy"
DEFAULT_TIMEOUT = 120
ADAPTER_ID = "trivy"


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

def scan_filesystem(target_path: str) -> AdapterResult:
    """Scan a filesystem path for vulnerabilities and misconfigurations.

    Reports only HIGH and CRITICAL severity findings.
    Output is JSON for structured downstream analysis.

    Timeout: 120s (large repos can be slow).
    Retry: policy_resilient (5 attempts, 2s initial, backoff=3.0).
    Degradation: error (security scan failure should be visible).
    """
    return _run([
        "fs", target_path,
        "--format", "json",
        "--severity", "HIGH,CRITICAL",
    ])


def scan_image(image: str) -> AdapterResult:
    """Scan a container image for vulnerabilities."""
    return _run(["image", "--format", "json", "--severity", "HIGH,CRITICAL", image])


def parse_vulnerabilities(result: AdapterResult) -> Tuple[dict, ...]:
    """Parse trivy JSON output into a tuple of vulnerability dicts.

    Returns empty tuple on parse failure (never raises).
    """
    if not result.success:
        return ()
    try:
        data = json.loads(result.stdout)
        vulns = []
        for finding in data.get("Results", []):
            for vuln in finding.get("Vulnerabilities", []):
                vulns.append({
                    "id": vuln.get("VulnerabilityID", ""),
                    "severity": vuln.get("Severity", ""),
                    "package": vuln.get("PkgName", ""),
                    "installed_version": vuln.get("InstalledVersion", ""),
                    "fixed_version": vuln.get("FixedVersion", ""),
                    "title": vuln.get("Title", "")[:200],
                })
        return tuple(vulns)
    except (json.JSONDecodeError, KeyError, TypeError):
        return ()


def check_health() -> dict:
    cli_ok = _check_cli()
    return {
        "adapter_id": ADAPTER_ID,
        "cli_available": cli_ok,
        "capability_type": "tool",
        "degraded": not cli_ok,
        "cli_name": CLI_NAME,
        "install_hint": INSTALL_HINT,
        "timeout_s": DEFAULT_TIMEOUT,
        "retry_policy": "resilient",
        "degradation": "error",
        "network_required": False,
    }


def wrap_as_evidence(result: AdapterResult, operation: str = "") -> dict:
    return {
        "evidence_type": "trivy_result",
        "source": ADAPTER_ID,
        "operation": operation,
        "payload_summary": result.stdout[:500],
        "truth_source": False,
        "evidence_hash": result.evidence_hash,
        "exit_code": result.exit_code,
        "degraded": result.degraded,
    }
