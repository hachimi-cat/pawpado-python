"""Verifying Pawpado webhook deliveries.

Every delivery carries ``Pawpado-Signature: t=<unix>,v1=<hex HMAC-SHA256(secret,
"<t>.<raw body>")>``. Verify the RAW bytes as received — a body that was parsed and
re-serialised will not match — and reject an old timestamp (default 5 minutes).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import time
from typing import Any, Callable, Dict, Optional, Union

__all__ = ["PawpadoWebhookError", "verify_webhook", "verify_webhook_signature"]


class PawpadoWebhookError(ValueError):
    """A delivery whose ``Pawpado-Signature`` does not check out (or is too old)."""


def _parse(header: str) -> Optional[tuple]:
    t: Optional[int] = None
    sigs = []
    for part in header.split(","):
        key, sep, value = part.partition("=")
        if not sep:
            continue
        key, value = key.strip(), value.strip()
        if key == "t" and value.isdigit():
            t = int(value)
        elif key == "v1" and re.fullmatch(r"[0-9a-fA-F]{64}", value):
            sigs.append(value.lower())
    return (t, sigs) if t is not None and sigs else None


def verify_webhook_signature(
    raw_body: Union[bytes, str],
    signature_header: Optional[str],
    secret: str,
    *,
    tolerance_seconds: int = 300,
    now: Optional[Callable[[], float]] = None,
) -> bool:
    """True when ``signature_header`` matches ``raw_body`` within the tolerance."""
    if not signature_header or not secret:
        return False
    parsed = _parse(signature_header)
    if not parsed:
        return False
    t, sigs = parsed
    current = int((now or time.time)())
    if abs(current - t) > tolerance_seconds:
        return False
    body = raw_body.decode("utf-8") if isinstance(raw_body, (bytes, bytearray)) else raw_body
    expected = hmac.new(secret.encode(), f"{t}.{body}".encode(), hashlib.sha256).hexdigest()
    return any(hmac.compare_digest(expected, s) for s in sigs)


def verify_webhook(
    raw_body: Union[bytes, str],
    signature_header: Optional[str],
    secret: str,
    *,
    tolerance_seconds: int = 300,
    now: Optional[Callable[[], float]] = None,
) -> Dict[str, Any]:
    """Verify a delivery and return its event (``id``, ``type``, ``occurredAt``,
    ``workspaceId``, ``data``). Raises :class:`PawpadoWebhookError` when the signature is
    missing, wrong or too old."""
    if not verify_webhook_signature(raw_body, signature_header, secret, tolerance_seconds=tolerance_seconds, now=now):
        raise PawpadoWebhookError("invalid or expired Pawpado-Signature")
    body = raw_body.decode("utf-8") if isinstance(raw_body, (bytes, bytearray)) else raw_body
    try:
        return json.loads(body)
    except ValueError as exc:
        raise PawpadoWebhookError("the webhook body is not JSON") from exc
