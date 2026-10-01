import hashlib
import hmac
import json

import pytest

from pawpado import PawpadoWebhookError, verify_webhook, verify_webhook_signature

SECRET = "paw_whsec_test"
BODY = json.dumps({"id": "evt_1", "type": "pawpado.session.stopped.v1", "occurredAt": "2026-10-01T00:00:00.000Z",
                   "workspaceId": "ws_1", "data": {"sessionId": "ses_1", "reason": "idle"}})
NOW = 1_790_000_000


def sign(t, body=BODY, secret=SECRET):
    return f"t={t},v1=" + hmac.new(secret.encode(), f"{t}.{body}".encode(), hashlib.sha256).hexdigest()


def test_valid_signature_returns_the_event():
    event = verify_webhook(BODY.encode(), sign(NOW), SECRET, now=lambda: NOW)
    assert event["type"] == "pawpado.session.stopped.v1"
    assert event["data"]["reason"] == "idle"


def test_refuses_wrong_secret_changed_body_old_or_missing():
    assert not verify_webhook_signature(BODY, sign(NOW, secret="other"), SECRET, now=lambda: NOW)
    assert not verify_webhook_signature(BODY + " ", sign(NOW), SECRET, now=lambda: NOW)
    assert not verify_webhook_signature(BODY, sign(NOW - 301), SECRET, now=lambda: NOW)
    assert verify_webhook_signature(BODY, sign(NOW - 301), SECRET, tolerance_seconds=600, now=lambda: NOW)
    assert not verify_webhook_signature(BODY, None, SECRET)
    with pytest.raises(PawpadoWebhookError):
        verify_webhook(BODY, "t=1,v1=00", SECRET, now=lambda: NOW)
