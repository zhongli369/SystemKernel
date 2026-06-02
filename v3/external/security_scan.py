"""
Security Scanning Harness — Phase 17c.

Wraps the trivy adapter (Phase 16b-1) as a SecurityScan pipeline.
Integrates with existing security review triggers — does NOT
create a new security system. trivy output is EVIDENCE, not truth.

Reuses:
  - trivy adapter (v3/integrations/trivy/adapter.py) — Phase 16b-1
  - sandbox_policy (v3/external/sandbox/) — Phase 14c-2
  - lifecycle_manager + retry_policy (v3/external/lifecycle/) — Phase 15c

When trivy CLI is not installed, scans degrade gracefully (skip, not error).
When trivy is installed, the same code works immediately.

Stdlib only. No new dependencies.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Optional, Tuple


# ═══════════════════════════════════════════════════════════════════════
# Vulnerability
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class Vulnerability:
    """A single vulnerability finding from a security scan.

    Populated from trivy JSON output. All fields are trivy's data,
    not SystemKernel's interpretation. truth_source is always False
    at the result level.
    """

    cve_id: Optional[str] = None
    severity: str = ""            # CRITICAL, HIGH, MEDIUM, LOW
    title: str = ""
    description: str = ""
    package_name: Optional[str] = None
    installed_version: Optional[str] = None
    fixed_version: Optional[str] = None
    file_path: Optional[str] = None                   # os-level path

    def to_dict(self) -> dict:
        return {
            "cve_id": self.cve_id,
            "severity": self.severity,
            "title": self.title[:200],
            "description": self.description[:500],
            "package_name": self.package_name,
            "installed_version": self.installed_version,
            "fixed_version": self.fixed_version,
            "file_path": self.file_path,
        }

    @staticmethod
    def from_trivy_finding(finding: dict) -> "Vulnerability":
        """Parse a single trivy vulnerability dict into a Vulnerability."""
        return Vulnerability(
            cve_id=finding.get("VulnerabilityID"),
            severity=finding.get("Severity", "UNKNOWN"),
            title=finding.get("Title", ""),
            description=finding.get("Description", ""),
            package_name=finding.get("PkgName"),
            installed_version=finding.get("InstalledVersion"),
            fixed_version=finding.get("FixedVersion"),
            file_path=finding.get("PkgPath"),
        )


# ═══════════════════════════════════════════════════════════════════════
# Security Scan Request / Result
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class SecurityScanRequest:
    """Immutable scan request. All fields are explicit."""
    target_path: str = ""
    scan_type: str = "vulnerability"  # "vulnerability", "config", "secret"
    severity_min: str = "HIGH"        # "CRITICAL", "HIGH", "MEDIUM", "LOW"

    def to_dict(self) -> dict:
        return {
            "target_path": self.target_path,
            "scan_type": self.scan_type,
            "severity_min": self.severity_min,
        }


@dataclass(frozen=True)
class SecurityScanResult:
    """Complete result of a security scan.

    trivy_raw_json preserves the original output for audit.
    truth_source is ALWAYS False — scan results are evidence.
    """

    request: SecurityScanRequest = field(default_factory=SecurityScanRequest)
    vulnerabilities: Tuple[Vulnerability, ...] = ()
    total_critical: int = 0
    total_high: int = 0
    total_medium: int = 0
    total_low: int = 0
    scan_duration_ms: float = 0.0
    trivy_raw_json: str = ""
    evidence_hash: str = ""
    degraded: bool = False
    error: str = ""
    truth_source: bool = False      # ALWAYS False — enforced

    @property
    def total_findings(self) -> int:
        return self.total_critical + self.total_high + self.total_medium + self.total_low

    @property
    def has_critical_or_high(self) -> bool:
        return self.total_critical > 0 or self.total_high > 0

    def to_dict(self) -> dict:
        return {
            "request": self.request.to_dict(),
            "vulnerabilities": [v.to_dict() for v in self.vulnerabilities],
            "total_critical": self.total_critical,
            "total_high": self.total_high,
            "total_medium": self.total_medium,
            "total_low": self.total_low,
            "total_findings": self.total_findings,
            "has_critical_or_high": self.has_critical_or_high,
            "scan_duration_ms": self.scan_duration_ms,
            "evidence_hash": self.evidence_hash,
            "degraded": self.degraded,
        }

    @staticmethod
    def degraded_result(request: SecurityScanRequest, reason: str) -> "SecurityScanResult":
        return SecurityScanResult(
            request=request,
            degraded=True,
            error=reason,
            evidence_hash=hashlib.sha256(
                f"degraded:{request.target_path}:{reason}".encode()
            ).hexdigest()[:16],
        )


# ═══════════════════════════════════════════════════════════════════════
# Security Scan Runner
# ═══════════════════════════════════════════════════════════════════════

def run_security_scan(request: SecurityScanRequest) -> SecurityScanResult:
    """Run a trivy security scan against a target path.

    Pipeline:
      1. Check trivy CLI availability
      2. Run trivy fs scan with severity filter
      3. Parse trivy JSON output → Vulnerability objects
      4. Return SecurityScanResult (truth_source=False)

    When trivy is not installed, returns a degraded result with empty
    vulnerabilities — never raises.

    Reuses the trivy adapter from Phase 16b-1.
    """
    if not request.target_path:
        return SecurityScanResult.degraded_result(request, "No target_path specified")

    # Check trivy availability
    import importlib
    try:
        trivy_mod = importlib.import_module("v3.integrations.trivy.adapter")
    except ImportError:
        return SecurityScanResult.degraded_result(request, "trivy adapter not importable")

    health = trivy_mod.check_health()
    if health["degraded"]:
        return SecurityScanResult.degraded_result(
            request,
            f"trivy CLI not available — install with: {health['install_hint']}",
        )

    # Run scan
    start = time.time()
    adapter_result = trivy_mod.scan_filesystem(request.target_path)

    if not adapter_result.success:
        return SecurityScanResult(
            request=request,
            degraded=True,
            error=adapter_result.stderr[:500],
            scan_duration_ms=(time.time() - start) * 1000,
            evidence_hash=adapter_result.evidence_hash,
        )

    # Parse vulnerabilities
    raw_vulns = trivy_mod.parse_vulnerabilities(adapter_result)
    vulns = tuple(Vulnerability.from_trivy_finding(v) for v in raw_vulns)

    # Count by severity
    counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for v in vulns:
        sev = v.severity.upper()
        if sev in counts:
            counts[sev] += 1

    # Filter by severity_min
    severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    min_level = severity_order.get(request.severity_min.upper(), 1)
    filtered = tuple(
        v for v in vulns
        if severity_order.get(v.severity.upper(), 99) <= min_level
    )

    scan_duration_ms = (time.time() - start) * 1000
    evidence_hash = hashlib.sha256(
        f"trivy:{request.target_path}:{len(vulns)}:{counts['CRITICAL']}".encode()
    ).hexdigest()[:16]

    return SecurityScanResult(
        request=request,
        vulnerabilities=filtered,
        total_critical=counts["CRITICAL"],
        total_high=counts["HIGH"],
        total_medium=counts["MEDIUM"],
        total_low=counts["LOW"],
        scan_duration_ms=round(scan_duration_ms, 1),
        trivy_raw_json=adapter_result.stdout[:10000],
        evidence_hash=evidence_hash,
    )


# ═══════════════════════════════════════════════════════════════════════
# Severity filter helpers
# ═══════════════════════════════════════════════════════════════════════

def filter_critical(result: SecurityScanResult) -> Tuple[Vulnerability, ...]:
    """Return only CRITICAL severity vulnerabilities."""
    return tuple(v for v in result.vulnerabilities if v.severity.upper() == "CRITICAL")


def filter_critical_or_high(result: SecurityScanResult) -> Tuple[Vulnerability, ...]:
    """Return CRITICAL and HIGH severity vulnerabilities."""
    return tuple(
        v for v in result.vulnerabilities
        if v.severity.upper() in ("CRITICAL", "HIGH")
    )


def is_clean(result: SecurityScanResult) -> bool:
    """True if no CRITICAL or HIGH findings."""
    return not result.has_critical_or_high and not result.degraded


# ═══════════════════════════════════════════════════════════════════════
# Evidence wrapping
# ═══════════════════════════════════════════════════════════════════════

def wrap_as_evidence(result: SecurityScanResult) -> dict:
    """Wrap a SecurityScanResult as an evidence record."""
    return {
        "evidence_type": "security_scan_result",
        "source": "trivy",
        "target_path": result.request.target_path,
        "total_findings": result.total_findings,
        "total_critical": result.total_critical,
        "total_high": result.total_high,
        "has_critical_or_high": result.has_critical_or_high,
        "truth_source": False,
        "evidence_hash": result.evidence_hash,
        "degraded": result.degraded,
    }
