"""Smoke tests for PawpadoClient — uses respx to intercept httpx.

Same testing strategy as the Node SDK's ``test/resources.test.ts``: spin up
a fake transport, fire each method once, assert path + method + body +
Bearer header.
"""

from __future__ import annotations

import json
import time
from typing import Any

import httpx
import pytest
import respx

from pawpado import (
    ApiError,
    PawpadoClient,
    PawpadoError,
    ProfileData,
    Session,
)

BASE = "https://pawpado.test"


def _envelope(data: Any) -> dict:
    return {
        "data": data,
        "error": None,
        "meta": {"requestId": "req_test", "timestamp": "now"},
    }


@pytest.fixture
def mock():
    with respx.mock(base_url=BASE, assert_all_called=False) as m:
        yield m


def _ok_route(mock, method: str, path: str):
    return getattr(mock, method.lower())(path).mock(
        return_value=httpx.Response(200, json=_envelope({"ok": True}))
    )


# ─── Construction ────────────────────────────────────────────────────────


def test_client_construction_defaults():
    c = PawpadoClient()
    assert c.base_url == "https://pawpado.com"
    # All resource namespaces exist
    assert c.sessions and c.credits and c.billing
    assert c.settings and c.account
    assert not hasattr(c, "admin")  # operator-only; not in the public SDK


# ─── Bearer auth via api_key ─────────────────────────────────────────────


def test_api_key_attaches_bearer(mock):
    route = _ok_route(mock, "GET", "/api/v1/sessions/poll")
    client = PawpadoClient(base_url=BASE, api_key="tok")
    client.sessions.poll()
    assert route.calls.last.request.headers["authorization"] == "Bearer tok"


def test_per_call_token_overrides_api_key(mock):
    route = _ok_route(mock, "GET", "/api/v1/sessions/poll")
    client = PawpadoClient(base_url=BASE, api_key="tok")
    client.sessions.poll(auth_token="override")
    assert route.calls.last.request.headers["authorization"] == "Bearer override"


def test_no_auth_header_when_no_token(mock):
    route = _ok_route(mock, "GET", "/api/v1/sessions/poll")
    client = PawpadoClient(base_url=BASE)
    client.sessions.poll()
    assert "authorization" not in route.calls.last.request.headers


# ─── Every route ─────────────────────────────────────────────────────────


def test_sessions_start_post(mock):
    route = _ok_route(mock, "POST", "/api/v1/sessions/start")
    PawpadoClient(base_url=BASE, api_key="t").sessions.start()
    assert route.called
    assert route.calls.last.request.method == "POST"


def test_sessions_stop_post_with_body(mock):
    route = _ok_route(mock, "POST", "/api/v1/sessions/stop")
    PawpadoClient(base_url=BASE, api_key="t").sessions.stop({"force": True})
    assert json.loads(route.calls.last.request.content) == {"force": True}


def test_sessions_pair_post(mock):
    route = _ok_route(mock, "POST", "/api/v1/sessions/pair")
    PawpadoClient(base_url=BASE, api_key="t").sessions.pair("1234", via="mobile")
    assert json.loads(route.calls.last.request.content) == {"pin": "1234", "via": "mobile"}


def test_sessions_connect_get(mock):
    route = _ok_route(mock, "GET", "/api/v1/sessions/connect")
    PawpadoClient(base_url=BASE, api_key="t").sessions.connect()
    assert route.called


def test_sessions_tailscale_key_post(mock):
    route = _ok_route(mock, "POST", "/api/v1/sessions/tailscale-key")
    PawpadoClient(base_url=BASE, api_key="t").sessions.tailscale_key()
    assert route.called


def test_credits_me_get(mock):
    route = _ok_route(mock, "GET", "/api/v1/credits/me")
    PawpadoClient(base_url=BASE, api_key="t").credits.me()
    assert route.called


def test_credits_topup_post(mock):
    route = _ok_route(mock, "POST", "/api/v1/credits/topup")
    client = PawpadoClient(base_url=BASE, api_key="t")
    client.credits.topup(amount_idr=100_000)
    assert json.loads(route.calls.last.request.content) == {"amountIdr": 100_000}
    client.credits.topup(amount_usd_cents=1_000)
    assert json.loads(route.calls.last.request.content) == {"amountUsdCents": 1_000}
    with pytest.raises(ValueError):
        client.credits.topup()


def test_billing_resize_storage_post(mock):
    route = _ok_route(mock, "POST", "/api/v1/billing/storage")
    PawpadoClient(base_url=BASE, api_key="t").billing.resize_storage(200)
    assert json.loads(route.calls.last.request.content) == {"storageGb": 200}


def test_billing_storage_get(mock):
    route = _ok_route(mock, "GET", "/api/v1/billing/storage")
    PawpadoClient(base_url=BASE, api_key="t").billing.storage()
    assert route.called


def test_settings_get(mock):
    route = _ok_route(mock, "GET", "/api/v1/settings")
    PawpadoClient(base_url=BASE, api_key="t").settings.get()
    assert route.called


def test_settings_update_patches(mock):
    route = _ok_route(mock, "PATCH", "/api/v1/settings")
    PawpadoClient(base_url=BASE, api_key="t").settings.update(
        idle_auto_stop_minutes=None, play_mode="moonlight", launch_options={"fps": 60},
    )
    assert route.calls.last.request.method == "PATCH"
    assert json.loads(route.calls.last.request.content) == {
        "idleAutoStopMinutes": None, "playMode": "moonlight", "launchOptions": {"fps": 60},
    }


def test_account_delete(mock):
    route = _ok_route(mock, "POST", "/api/v1/account/delete")
    PawpadoClient(base_url=BASE, api_key="t").account.delete()
    assert route.calls.last.request.method == "POST"
    assert json.loads(route.calls.last.request.content) == {"confirm": "DELETE"}


def test_health_no_auth(mock):
    route = _ok_route(mock, "GET", "/api/v1/health")
    PawpadoClient(base_url=BASE).health()
    assert "authorization" not in route.calls.last.request.headers


# ─── Errors ──────────────────────────────────────────────────────────────


def test_enveloped_error_raises_pawpado_error(mock):
    mock.get("/api/v1/sessions/poll").mock(
        return_value=httpx.Response(
            400,
            json={
                "data": None,
                "error": {"code": "BAD_STATE", "message": "session not running"},
                "meta": {"requestId": "req_x", "timestamp": "now"},
            },
        ),
    )
    with pytest.raises(PawpadoError) as exc:
        PawpadoClient(base_url=BASE, api_key="t").sessions.poll()
    assert exc.value.code == "BAD_STATE"
    assert exc.value.status == 400
    assert exc.value.request_id == "req_x"
    # Alias still works.
    assert isinstance(exc.value, ApiError)


def test_non_enveloped_4xx_raises(mock):
    mock.get("/api/v1/sessions/poll").mock(
        return_value=httpx.Response(404, text="not found"),
    )
    with pytest.raises(PawpadoError) as exc:
        PawpadoClient(base_url=BASE, api_key="t").sessions.poll()
    assert exc.value.status == 404


# ─── Session-based auth (Bearer via Session) ─────────────────────────────


def test_session_bearer_used(mock):
    route = _ok_route(mock, "GET", "/api/v1/credits/me")
    session = Session(brand="pawpado", credentials_path="/tmp/__never_exists__")
    session.set_data(
        ProfileData(
            access_token="sess_tok",
            expires_at=int(time.time()) + 3600,
            issuer="https://huudis.test",
            client_id="oc_pawpado",
        )
    )
    client = PawpadoClient(base_url=BASE, session=session)
    client.credits.me()
    assert route.calls.last.request.headers["authorization"] == "Bearer sess_tok"
