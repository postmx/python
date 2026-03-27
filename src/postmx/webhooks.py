from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time

from ._errors import PostMXWebhookVerificationError
from ._types import WebhookEvent

SIGNATURE_PREFIX = "v1="
DEFAULT_TOLERANCE_SECONDS = 300


def verify_webhook_signature(
    *,
    payload: str | bytes,
    signature: str,
    timestamp: str,
    signing_secret: str,
    tolerance: int = DEFAULT_TOLERANCE_SECONDS,
) -> WebhookEvent:
    """Verify a PostMX webhook signature and return the parsed event.

    Raises PostMXWebhookVerificationError on any verification failure.
    """
    if not signature.startswith(SIGNATURE_PREFIX):
        raise PostMXWebhookVerificationError(
            "Invalid signature format: missing v1= prefix"
        )

    try:
        ts = int(timestamp)
    except (ValueError, TypeError):
        raise PostMXWebhookVerificationError("Invalid timestamp: not a number")

    now = int(time.time())
    if abs(now - ts) > tolerance:
        raise PostMXWebhookVerificationError(
            f"Timestamp outside tolerance: {abs(now - ts)}s > {tolerance}s"
        )

    raw_body = payload if isinstance(payload, str) else payload.decode("utf-8")

    expected = base64.urlsafe_b64encode(
        hmac.new(
            signing_secret.encode("utf-8"),
            f"{timestamp}.{raw_body}".encode("utf-8"),
            hashlib.sha256,
        ).digest()
    ).rstrip(b"=").decode("ascii")

    received = signature[len(SIGNATURE_PREFIX):]

    if not hmac.compare_digest(expected, received):
        raise PostMXWebhookVerificationError("Signature mismatch")

    try:
        return json.loads(raw_body)
    except (json.JSONDecodeError, ValueError):
        raise PostMXWebhookVerificationError("Invalid JSON payload")
