import base64
import hashlib
import hmac
import json
import time

import pytest

from postmx import PostMXWebhookVerificationError, verify_webhook_signature

SIGNING_SECRET = "whsec_test_secret"
PAYLOAD = json.dumps(
    {
        "id": "evt_1",
        "type": "email.received",
        "created_at": "2026-01-01T00:00:00Z",
        "data": {
            "inbox": {"id": "inb_1", "email_address": "a@b.com", "label": "test"},
            "message": {
                "id": "msg_1",
                "inbox_id": "inb_1",
                "inbox_email_address": "a@b.com",
                "inbox_label": "test",
                "from_email": "sender@x.com",
                "to_email": "a@b.com",
                "subject": "OTP",
                "preview_text": None,
                "received_at": "2026-01-01T00:00:00Z",
                "has_text_body": True,
                "has_html_body": False,
                "text_body": "123456",
                "html_body": None,
                "otp": "123456",
                "links": [],
                "intent": "login_code",
            },
        },
    }
)


def make_signature(secret: str, timestamp: str, body: str) -> str:
    mac = hmac.new(
        secret.encode("utf-8"),
        f"{timestamp}.{body}".encode("utf-8"),
        hashlib.sha256,
    ).digest()
    encoded = base64.urlsafe_b64encode(mac).rstrip(b"=").decode("ascii")
    return f"v1={encoded}"


def test_verifies_valid_signature():
    timestamp = str(int(time.time()))
    signature = make_signature(SIGNING_SECRET, timestamp, PAYLOAD)
    event = verify_webhook_signature(
        payload=PAYLOAD,
        signature=signature,
        timestamp=timestamp,
        signing_secret=SIGNING_SECRET,
    )
    assert event["id"] == "evt_1"
    assert event["type"] == "email.received"
    assert event["data"]["message"]["otp"] == "123456"


def test_verifies_with_bytes_payload():
    timestamp = str(int(time.time()))
    signature = make_signature(SIGNING_SECRET, timestamp, PAYLOAD)
    event = verify_webhook_signature(
        payload=PAYLOAD.encode("utf-8"),
        signature=signature,
        timestamp=timestamp,
        signing_secret=SIGNING_SECRET,
    )
    assert event["id"] == "evt_1"


def test_rejects_missing_prefix():
    timestamp = str(int(time.time()))
    with pytest.raises(PostMXWebhookVerificationError, match="missing v1= prefix"):
        verify_webhook_signature(
            payload=PAYLOAD,
            signature="bad_sig",
            timestamp=timestamp,
            signing_secret=SIGNING_SECRET,
        )


def test_rejects_invalid_timestamp():
    with pytest.raises(PostMXWebhookVerificationError, match="not a number"):
        verify_webhook_signature(
            payload=PAYLOAD,
            signature="v1=abc",
            timestamp="not-a-number",
            signing_secret=SIGNING_SECRET,
        )


def test_rejects_expired_timestamp():
    old_timestamp = str(int(time.time()) - 600)
    signature = make_signature(SIGNING_SECRET, old_timestamp, PAYLOAD)
    with pytest.raises(PostMXWebhookVerificationError, match="Timestamp outside tolerance"):
        verify_webhook_signature(
            payload=PAYLOAD,
            signature=signature,
            timestamp=old_timestamp,
            signing_secret=SIGNING_SECRET,
        )


def test_rejects_tampered_body():
    timestamp = str(int(time.time()))
    signature = make_signature(SIGNING_SECRET, timestamp, PAYLOAD)
    with pytest.raises(PostMXWebhookVerificationError, match="Signature mismatch"):
        verify_webhook_signature(
            payload=PAYLOAD.replace("123456", "999999"),
            signature=signature,
            timestamp=timestamp,
            signing_secret=SIGNING_SECRET,
        )


def test_rejects_wrong_secret():
    timestamp = str(int(time.time()))
    signature = make_signature("wrong_secret", timestamp, PAYLOAD)
    with pytest.raises(PostMXWebhookVerificationError, match="Signature mismatch"):
        verify_webhook_signature(
            payload=PAYLOAD,
            signature=signature,
            timestamp=timestamp,
            signing_secret=SIGNING_SECRET,
        )


def test_custom_tolerance():
    timestamp = str(int(time.time()) - 10)
    signature = make_signature(SIGNING_SECRET, timestamp, PAYLOAD)

    # Should fail with 5s tolerance
    with pytest.raises(PostMXWebhookVerificationError, match="Timestamp outside tolerance"):
        verify_webhook_signature(
            payload=PAYLOAD,
            signature=signature,
            timestamp=timestamp,
            signing_secret=SIGNING_SECRET,
            tolerance=5,
        )

    # Should pass with 60s tolerance
    event = verify_webhook_signature(
        payload=PAYLOAD,
        signature=signature,
        timestamp=timestamp,
        signing_secret=SIGNING_SECRET,
        tolerance=60,
    )
    assert event["id"] == "evt_1"
