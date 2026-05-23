"""
github_webhook.py — GitHub Webhook Event Source (v1.0)

Receives GitHub webhook HTTP requests and emits normalized events.

PURELY an event emitter — no processing, no routing, no task creation.
Does NOT:
  - Parse issue/PR content for meaning
  - Classify or prioritize
  - Decide whether to create a task (EventRouter does that)
  - Call any LLM

Expected usage (Flask/FastAPI example):
    @app.route("/webhook/github", methods=["POST"])
    def github_webhook():
        headers = dict(request.headers)
        body = request.get_json()
        raw_event = github_webhook.listen(headers, body)
        result = EventBus.ingest(raw_event)
        return {"status": "ok", "task_id": result.task_id}
"""

from typing import Optional


def listen(headers: dict, body: dict) -> dict:
    """Receive a GitHub webhook and emit a normalized event dict.

    Args:
        headers: HTTP request headers (must contain X-GitHub-Event).
        body: Parsed JSON request body.

    Returns:
        Raw event dict ready for EventBus.ingest().
    """
    from EventBus.event_schema import normalize_github_webhook
    return normalize_github_webhook(headers, body)


# ═══════════════════════════════════════════════════════════════════════════════
# Webhook signature verification (optional, for production use)
# ═══════════════════════════════════════════════════════════════════════════════

def verify_signature(payload: bytes, signature: str, secret: str) -> bool:
    """Verify GitHub webhook signature (HMAC-SHA256).

    Pure function. No side effects. Does not affect event processing.

    Args:
        payload: Raw request body bytes.
        signature: X-Hub-Signature-256 header value.
        secret: Webhook secret configured in GitHub.

    Returns:
        True if signature is valid.
    """
    import hmac
    import hashlib

    if not signature or not secret:
        return False

    expected = "sha256=" + hmac.new(
        secret.encode(), payload, hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(expected, signature)
