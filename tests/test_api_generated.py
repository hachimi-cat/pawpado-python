"""client.api: every feature route, one method each, generated from the API spec
(scripts/apigen.sh). Calls carry the same credentials as every other method."""

from __future__ import annotations

import json
from typing import List
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest

from pawpado import GeneratedApi, PawpadoClient


def _client(seen: List[httpx.Request]) -> PawpadoClient:
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, content=json.dumps({"ok": True}).encode())

    http = httpx.Client(transport=httpx.MockTransport(handler))
    return PawpadoClient(api_key="paw_live_test", base_url="https://pawpado.test", http=http)


def test_sends_the_fields_pawpado_reads_with_the_api_key() -> None:
    seen: List[httpx.Request] = []
    client = _client(seen)
    assert client.api.feedback_create(session_id="ses_1", rating=5, experience="smooth") == {"ok": True}
    request = seen[0]
    assert (request.method, request.url.path) == ("POST", "/api/v1/feedback")
    assert json.loads(request.content) == {"sessionId": "ses_1", "rating": 5, "experience": "smooth"}
    assert request.headers["authorization"] == "Bearer paw_live_test"


def test_path_and_query() -> None:
    seen: List[httpx.Request] = []
    client = _client(seen)
    client.api.snapshots_status("snap 1")
    client.api.audit_log_list(limit=5, action="pawpado.snapshot.deleted.v1")
    client.api.webhooks_update("wh_1", active=False)
    assert seen[0].url.raw_path.decode() == "/api/v1/snapshots/snap%201/status"
    assert seen[1].url.path == "/api/v1/audit-log"
    assert parse_qs(urlsplit(str(seen[1].url)).query) == {"limit": ["5"], "action": ["pawpado.snapshot.deleted.v1"]}
    assert (seen[2].method, json.loads(seen[2].content)) == ("PATCH", {"active": False})


def test_a_required_field_is_asked_for() -> None:
    client = _client([])
    with pytest.raises(ValueError, match="needs name"):
        client.api.snapshots_create()


def test_raw_http_verbs_stay_on_client_api() -> None:
    seen: List[httpx.Request] = []
    client = _client(seen)
    client.api.get("/api/v1/sessions/poll")
    assert seen[0].url.path == "/api/v1/sessions/poll"
    assert seen[0].headers["authorization"] == "Bearer paw_live_test"
    assert client.api.base_url == "https://pawpado.test"


def test_every_feature_route_has_a_method() -> None:
    client = _client([])
    assert isinstance(client.api, GeneratedApi)
    methods = [n for n in dir(GeneratedApi) if not n.startswith("_")]
    assert len(methods) >= 38
    assert "machines_resize" in methods
