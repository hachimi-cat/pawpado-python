"""High-level Pawpado client mirroring the Node SDK's PawpadoClient surface."""

from __future__ import annotations

from typing import Any, Dict, Optional

import httpx

from .api_generated import GeneratedApi
from .resources import (
    AccountResources,
    ApiClient,
    BillingResources,
    CreditsResources,
    SessionsResources,
    SettingsResources,
    build_resources,
)
from .session import Session


class _ApiKeyApiClient(ApiClient):
    """ApiClient variant that injects a static API key as the default Bearer.

    Mirrors the Node SDK's ``a(token)`` helper: when no per-call ``auth_token``
    is given, fall back to the configured static api_key.
    """

    def __init__(self, *, api_key: str, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._api_key = api_key

    def _request(self, method, path, body, *, query, headers, auth_token):  # type: ignore[override]
        if auth_token is None:
            auth_token = self._api_key
        return super()._request(
            method, path, body, query=query, headers=headers, auth_token=auth_token,
        )


class PawpadoApi(GeneratedApi):
    """``client.api``: every feature route, one method each (``api_generated.py``,
    generated from the API spec) — and, as before, the underlying ``ApiClient``'s own
    ``get`` / ``post`` / ``patch`` / ``put`` / ``delete`` / ``paginate``
    (``client.api.get("/api/v1/...")``), the escape hatch."""

    def __init__(self, client: "PawpadoClient", http_api: ApiClient) -> None:
        super().__init__(client)
        self._http_api = http_api

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        return getattr(self._http_api, name)


class PawpadoClient:
    """Talk to Pawpado.

    Auth options (pick one):
      - ``session=Session(...)`` — Bearer via Huudis device flow w/ refresh.
      - ``api_key="..."`` — a Pawpado API key (``paw_live_…``, Settings → API keys) or a
        Huudis access token, sent as Bearer (mirrors Node ``apiKey``).
      - neither — only ``health()`` is usable; per-call ``auth_token=`` works.
    """

    # IDE hints — populated in __init__.
    sessions: SessionsResources
    credits: CreditsResources
    billing: BillingResources
    settings: SettingsResources
    account: AccountResources

    def __init__(
        self,
        *,
        base_url: str = "https://pawpado.com",
        session: Optional[Session] = None,
        api_key: Optional[str] = None,
        http: Optional[httpx.Client] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._http = http or httpx.Client(timeout=10.0)
        self._owns_http = http is None
        if api_key is not None and session is None:
            self._api_client: ApiClient = _ApiKeyApiClient(
                api_key=api_key, base_url=self.base_url, http=self._http,
            )
        else:
            self._api_client = ApiClient(base_url=self.base_url, session=session, http=self._http)
        # Every feature route, one method each (generated from the API spec), plus the
        # raw HTTP verbs client.api always had.
        self.api = PawpadoApi(self, self._api_client)
        resources = build_resources(self._api_client)
        self.sessions = resources["sessions"]  # type: ignore[assignment]
        self.credits = resources["credits"]  # type: ignore[assignment]
        self.billing = resources["billing"]  # type: ignore[assignment]
        self.settings = resources["settings"]  # type: ignore[assignment]
        self.account = resources["account"]  # type: ignore[assignment]

    def close(self) -> None:
        if self._owns_http:
            self._http.close()

    def __enter__(self) -> "PawpadoClient":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    # ─── Health (no auth) ───────────────────────────────────────────────
    def health(self) -> Any:
        return self._api_client.get("/api/v1/health")

    # ─── Generated routes ───────────────────────────────────────────────
    def _apigen_request(
        self,
        method: str,
        path: str,
        *,
        query: Optional[Dict[str, Any]] = None,
        body: Any = None,
    ) -> Any:
        """The call behind ``client.api.<area>_<action>(...)`` (api_generated.py): the
        same ApiClient and credentials (the session, or the constructor's ``api_key`` — a
        ``paw_live_…`` key, sent as Bearer) as every resource method."""
        verb = method.upper()
        if verb in ("POST", "PATCH", "PUT"):
            return getattr(self._api_client, verb.lower())(path, body, query=query)
        if verb in ("GET", "DELETE"):
            return getattr(self._api_client, verb.lower())(path, query=query)
        raise ValueError(f"unsupported method {method}")
