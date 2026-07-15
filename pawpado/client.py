"""High-level Pawpado client mirroring the Node SDK's PawpadoClient surface."""

from __future__ import annotations

from typing import Any, Optional

import httpx

from .resources import (
    AccountResources,
    AdminResources,
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


class PawpadoClient:
    """Talk to Pawpado.

    Auth options (pick one):
      - ``session=Session(...)`` — Bearer via Huudis device flow w/ refresh.
      - ``api_key="..."`` — static access token (mirrors Node ``apiKey``).
      - neither — only ``health()`` is usable; per-call ``auth_token=`` works.
    """

    # IDE hints — populated in __init__.
    sessions: SessionsResources
    credits: CreditsResources
    billing: BillingResources
    settings: SettingsResources
    account: AccountResources
    admin: AdminResources

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
            self.api: ApiClient = _ApiKeyApiClient(
                api_key=api_key, base_url=self.base_url, http=self._http,
            )
        else:
            self.api = ApiClient(base_url=self.base_url, session=session, http=self._http)
        resources = build_resources(self.api)
        self.sessions = resources["sessions"]  # type: ignore[assignment]
        self.credits = resources["credits"]  # type: ignore[assignment]
        self.billing = resources["billing"]  # type: ignore[assignment]
        self.settings = resources["settings"]  # type: ignore[assignment]
        self.account = resources["account"]  # type: ignore[assignment]
        self.admin = resources["admin"]  # type: ignore[assignment]

    def close(self) -> None:
        if self._owns_http:
            self._http.close()

    def __enter__(self) -> "PawpadoClient":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    # ─── Health (no auth) ───────────────────────────────────────────────
    def health(self) -> Any:
        return self.api.get("/api/v1/health")
