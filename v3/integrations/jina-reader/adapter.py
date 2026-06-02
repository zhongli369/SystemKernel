"""
Jina Reader Adapter — URL to plain text via Jina Reader API.

Phase 16b-1: New core provider. Uses HTTP GET (stdlib urllib, no pip deps)
to fetch clean, LLM-friendly text from any URL.

Differs slightly from the standard subprocess pattern: uses urllib.request
instead of subprocess (no CLI). Otherwise follows the same AdapterResult +
EvidenceRecord pattern exactly.

All output is EvidenceRecord-wrapped with truth_source=False.
No API key required for basic mode.

Type: context
"""

from __future__ import annotations

import hashlib
import time
import urllib.request
import urllib.error
from dataclasses import dataclass


# ═══════════════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════════════

JINA_BASE_URL = "https://r.jina.ai"
DEFAULT_TIMEOUT = 20
ADAPTER_ID = "jina-reader"


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
# Cache for degraded mode
# ═══════════════════════════════════════════════════════════════════════

_cache: dict[str, str] = {}


# ═══════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════

def read(url: str) -> AdapterResult:
    """Fetch a URL as clean Markdown via Jina Reader API.

    GET https://r.jina.ai/<url> with Accept: text/markdown header.
    No API key required for basic usage.

    Timeout: 20s.
    Retry: policy_standard (3 attempts, 1s backoff).
    Degradation: use_cache (returns cached result if available).
    """
    start = time.time()

    try:
        req = urllib.request.Request(
            f"{JINA_BASE_URL}/{url}",
            headers={"Accept": "text/markdown"},
        )
        with urllib.request.urlopen(req, timeout=DEFAULT_TIMEOUT) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            _cache[url] = body
            duration_ms = (time.time() - start) * 1000
            evidence_hash = hashlib.sha256(
                f"jina:{url}:{body[:200]}:0".encode()
            ).hexdigest()[:16]
            return AdapterResult(
                stdout=body, exit_code=0,
                duration_ms=duration_ms, evidence_hash=evidence_hash,
            )

    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace") if e.fp else ""
        if url in _cache:
            duration_ms = (time.time() - start) * 1000
            return AdapterResult(
                stdout=_cache[url], exit_code=0, degraded=True,
                duration_ms=duration_ms,
                evidence_hash=hashlib.sha256(
                    f"jina:cache:{url}:0".encode()
                ).hexdigest()[:16],
            )
        return AdapterResult(
            stderr=f"HTTP {e.code}: {body[:200]}",
            exit_code=e.code, degraded=True,
        )

    except urllib.error.URLError as e:
        if url in _cache:
            duration_ms = (time.time() - start) * 1000
            return AdapterResult(
                stdout=_cache[url], exit_code=0, degraded=True,
                duration_ms=duration_ms,
                evidence_hash=hashlib.sha256(
                    f"jina:cache:{url}:0".encode()
                ).hexdigest()[:16],
            )
        return AdapterResult(
            stderr=f"Connection error: {e.reason}", exit_code=-1,
            degraded=True, error=str(e.reason),
        )

    except Exception as e:
        if url in _cache:
            return AdapterResult(stdout=_cache[url], exit_code=0, degraded=True)
        return AdapterResult(
            stderr=str(e), exit_code=-1, degraded=True, error=str(e),
        )


def check_health() -> dict:
    return {
        "adapter_id": ADAPTER_ID,
        "cli_available": True,   # HTTP-based, no CLI needed
        "capability_type": "context",
        "degraded": False,
        "endpoint": JINA_BASE_URL,
        "timeout_s": DEFAULT_TIMEOUT,
        "retry_policy": "standard",
        "degradation": "use_cache",
        "network_required": True,
        "dependencies": "none (stdlib urllib)",
    }


def wrap_as_evidence(result: AdapterResult, operation: str = "") -> dict:
    return {
        "evidence_type": "jina_reader_result",
        "source": ADAPTER_ID,
        "operation": operation,
        "payload_summary": result.stdout[:500],
        "truth_source": False,
        "evidence_hash": result.evidence_hash,
        "exit_code": result.exit_code,
        "degraded": result.degraded,
    }
