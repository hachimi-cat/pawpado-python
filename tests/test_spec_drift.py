"""Every hand-written method must call a route Pawpado actually serves: its (method, path)
is checked against the API spec, frontend/openapi.json, which scripts/apigen.sh makes from
the route handlers. A method whose route moves or disappears fails here. (The public mirror
of this package carries no spec, so there the check is skipped.)"""

from __future__ import annotations

import inspect
import json
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Tuple

import httpx
import pytest

from pawpado import PawpadoClient

SPEC = Path(__file__).resolve().parents[3] / "frontend" / "openapi.json"
pytestmark = pytest.mark.skipif(not SPEC.exists(), reason="no API spec next to this SDK (public mirror)")

NAMESPACES = ["sessions", "credits", "billing", "settings", "account"]

# One call per hand-written method; a method missing here fails the completeness check.
CALLS: Dict[str, Callable[[PawpadoClient], Any]] = {
    "sessions.start": lambda c: c.sessions.start(),
    "sessions.stop": lambda c: c.sessions.stop({"force": True}),
    "sessions.poll": lambda c: c.sessions.poll(),
    "sessions.pair": lambda c: c.sessions.pair("1234"),
    "sessions.connect": lambda c: c.sessions.connect(),
    "sessions.tailscale_key": lambda c: c.sessions.tailscale_key(),
    "credits.me": lambda c: c.credits.me(),
    "credits.topup": lambda c: c.credits.topup(amount_idr=100_000),
    "billing.storage": lambda c: c.billing.storage(),
    "billing.resize_storage": lambda c: c.billing.resize_storage(200),
    "settings.get": lambda c: c.settings.get(),
    "settings.update": lambda c: c.settings.update(play_mode="browser"),
    "account.delete": lambda c: c.account.delete(),
    "health": lambda c: c.health(),
}


def _served(method: str, path: str) -> bool:
    paths = json.loads(SPEC.read_text())["paths"]
    for route, ops in paths.items():
        if re.fullmatch(re.sub(r"\{[^}]+\}", "[^/]+", route), path) and method.lower() in ops:
            return True
    return False


def _client(seen: List[Tuple[str, str]]) -> PawpadoClient:
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.method, request.url.path))
        return httpx.Response(200, content=b"{}")

    return PawpadoClient(api_key="paw_live_test", base_url="https://pawpado.test", http=httpx.Client(transport=httpx.MockTransport(handler)))


def test_covers_every_hand_written_method() -> None:
    client = _client([])
    methods = [
        f"{ns}.{name}"
        for ns in NAMESPACES
        for name, _ in inspect.getmembers(getattr(client, ns), inspect.ismethod)
        if not name.startswith("_")
    ]
    assert sorted(CALLS) == sorted(methods + ["health"])


@pytest.mark.parametrize("name", sorted(CALLS))
def test_calls_a_route_the_spec_has(name: str) -> None:
    seen: List[Tuple[str, str]] = []
    CALLS[name](_client(seen))
    assert len(seen) == 1
    assert _served(*seen[0]), seen[0]
