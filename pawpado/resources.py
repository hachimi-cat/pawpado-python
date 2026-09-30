"""Typed ApiClient + resource namespaces for PawpadoClient.

Bundled into one module because pawpado's surface is small enough that splitting
``http_client.py`` + ``resources.py`` (the huudis layout) is overkill — but the
class shapes match huudis 1:1 so they can be teased apart later.
"""

from __future__ import annotations

from typing import Any, Dict, Iterator, Optional
from urllib.parse import urlparse

import httpx

from .errors import ApiError, NetworkError
from .session import Session


class ApiClient:
    """Bearer-auth HTTP client with envelope unwrap + proactive/reactive
    refresh. Mirrors @forjio/sdk's ApiClient."""

    def __init__(
        self,
        *,
        base_url: str,
        session: Optional[Session] = None,
        http: Optional[httpx.Client] = None,
        refresh_buffer_sec: int = 300,
        retry_on_5xx: int = 1,
        default_headers: Optional[Dict[str, str]] = None,
        default_query: Optional[Dict[str, str]] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.session = session
        self._http = http or httpx.Client(timeout=10.0)
        self._owns_http = http is None
        self.refresh_buffer_sec = refresh_buffer_sec
        self.retry_on_5xx = retry_on_5xx
        self.default_headers = default_headers or {}
        self.default_query = default_query or {}

    def close(self) -> None:
        if self._owns_http:
            self._http.close()

    def __enter__(self) -> "ApiClient":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    # ---- public methods -------------------------------------------------

    def get(self, path: str, *, query: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None, auth_token: Optional[str] = None) -> Any:
        return self._request("GET", path, None, query=query, headers=headers, auth_token=auth_token)

    def post(self, path: str, body: Any = None, *, query: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None, auth_token: Optional[str] = None) -> Any:
        return self._request("POST", path, body, query=query, headers=headers, auth_token=auth_token)

    def patch(self, path: str, body: Any = None, *, query: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None, auth_token: Optional[str] = None) -> Any:
        return self._request("PATCH", path, body, query=query, headers=headers, auth_token=auth_token)

    def put(self, path: str, body: Any = None, *, query: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None, auth_token: Optional[str] = None) -> Any:
        return self._request("PUT", path, body, query=query, headers=headers, auth_token=auth_token)

    def delete(self, path: str, *, query: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None, auth_token: Optional[str] = None) -> Any:
        return self._request("DELETE", path, None, query=query, headers=headers, auth_token=auth_token)

    def paginate(
        self,
        path: str,
        *,
        query: Optional[Dict[str, Any]] = None,
        cursor_param: str = "cursor",
        auth_token: Optional[str] = None,
    ) -> Iterator[Any]:
        cursor: Optional[str] = None
        while True:
            q = dict(query or {})
            if cursor:
                q[cursor_param] = cursor
            page = self.get(path, query=q, auth_token=auth_token)
            for item in _extract_items(page):
                yield item
            cursor = _extract_cursor(page)
            if not cursor:
                return

    # ---- internals ------------------------------------------------------

    def _request(
        self,
        method: str,
        path: str,
        body: Any,
        *,
        query: Optional[Dict[str, Any]],
        headers: Optional[Dict[str, str]],
        auth_token: Optional[str],
    ) -> Any:
        # Proactive refresh (only when we own the bearer via session)
        if (
            self.session is not None
            and auth_token is None
            and self.session.will_expire_soon(self.refresh_buffer_sec)
        ):
            try:
                self.session.refresh()
            except Exception:
                pass
        res = self._send(method, path, body, query=query, headers=headers, auth_token=auth_token)
        # Reactive single 401 retry
        if res.status_code == 401 and self.session is not None and auth_token is None:
            try:
                self.session.refresh()
                res = self._send(method, path, body, query=query, headers=headers, auth_token=auth_token)
            except Exception:
                pass
        # 5xx retry
        retries_left = self.retry_on_5xx
        while res.status_code >= 500 and retries_left > 0:
            retries_left -= 1
            res = self._send(method, path, body, query=query, headers=headers, auth_token=auth_token)
        return self._unwrap(res)

    def _send(
        self,
        method: str,
        path: str,
        body: Any,
        *,
        query: Optional[Dict[str, Any]],
        headers: Optional[Dict[str, str]],
        auth_token: Optional[str],
    ) -> httpx.Response:
        if urlparse(path).scheme:
            url = path
        else:
            url = f"{self.base_url}{path if path.startswith('/') else '/' + path}"
        merged_q: Dict[str, Any] = dict(self.default_query)
        if query:
            merged_q.update({k: v for k, v in query.items() if v is not None})
        h: Dict[str, str] = dict(self.default_headers)
        h["accept"] = h.get("accept", "application/json")
        if headers:
            h.update(headers)
        token = auth_token or (
            self.session.data.access_token if (self.session and self.session.data) else None
        )
        if token:
            h["authorization"] = f"Bearer {token}"
        kwargs: Dict[str, Any] = {"params": merged_q or None, "headers": h}
        if body is not None:
            h.setdefault("content-type", "application/json")
            kwargs["json"] = body
        try:
            return self._http.request(method, url, **kwargs)
        except httpx.HTTPError as e:
            raise NetworkError(str(e)) from e

    def _unwrap(self, res: httpx.Response) -> Any:
        text = res.text or ""
        parsed: Any = None
        if text:
            try:
                parsed = res.json()
            except Exception:
                if res.status_code >= 400:
                    raise ApiError("NON_JSON_ERROR", text or res.reason_phrase, res.status_code)
                raise ApiError("INVALID_RESPONSE", "non-JSON response", res.status_code)
        if isinstance(parsed, dict) and "data" in parsed and "error" in parsed and "meta" in parsed:
            if parsed.get("error"):
                error = parsed["error"]
                raise ApiError(
                    error.get("code", "UNKNOWN"),
                    error.get("message", ""),
                    res.status_code,
                    request_id=(parsed.get("meta") or {}).get("requestId"),
                    details=error.get("details"),
                )
            return parsed.get("data")
        if res.status_code >= 400:
            err_obj = parsed.get("error") if isinstance(parsed, dict) else parsed
            code = (err_obj or {}).get("code", "HTTP_ERROR") if isinstance(err_obj, dict) else "HTTP_ERROR"
            message = (
                (err_obj or {}).get("message", res.reason_phrase)
                if isinstance(err_obj, dict)
                else res.reason_phrase
            )
            raise ApiError(
                code,
                message,
                res.status_code,
                details=parsed if isinstance(parsed, dict) else None,
            )
        return parsed


def _extract_items(page: Any) -> Iterator[Any]:
    if isinstance(page, list):
        yield from page
        return
    if isinstance(page, dict):
        for key in ("items", "data", "results"):
            v = page.get(key)
            if isinstance(v, list):
                yield from v
                return


def _extract_cursor(page: Any) -> Optional[str]:
    if not isinstance(page, dict):
        return None
    nc = page.get("nextCursor")
    if isinstance(nc, str) and nc:
        return nc
    meta = page.get("meta")
    if isinstance(meta, dict):
        mc = meta.get("nextCursor")
        if isinstance(mc, str) and mc:
            return mc
    return None


# ─── Resource namespaces ────────────────────────────────────────────────


class _Namespace:
    def __init__(self, api: ApiClient) -> None:
        self.api = api


def _opts(auth_token: Optional[str]) -> Dict[str, Any]:
    return {"auth_token": auth_token} if auth_token else {}


# Each method takes an optional ``auth_token`` (an API key or a Huudis access token) that
# overrides the client's own credentials. Every other route: ``client.api``.


class SessionsResources(_Namespace):
    def start(self, *, auth_token: Optional[str] = None):
        return self.api.post("/api/v1/sessions/start", None, **_opts(auth_token))

    def stop(self, body: Optional[Dict[str, Any]] = None, *, auth_token: Optional[str] = None):
        """``body``: ``{"force": True}`` re-issues the stop forcefully."""
        return self.api.post("/api/v1/sessions/stop", body or {}, **_opts(auth_token))

    def poll(self, *, auth_token: Optional[str] = None):
        return self.api.get("/api/v1/sessions/poll", **_opts(auth_token))

    def pair(
        self,
        pin: str,
        *,
        device_name: Optional[str] = None,
        via: Optional[str] = None,
        auth_token: Optional[str] = None,
    ):
        """Pair a Moonlight client: send the 4-digit PIN it shows. ``via``: desktop or mobile."""
        body: Dict[str, Any] = {"pin": pin}
        if device_name is not None:
            body["deviceName"] = device_name
        if via is not None:
            body["via"] = via
        return self.api.post("/api/v1/sessions/pair", body, **_opts(auth_token))

    def connect(self, *, auth_token: Optional[str] = None):
        return self.api.get("/api/v1/sessions/connect", **_opts(auth_token))

    def tailscale_key(self, *, auth_token: Optional[str] = None):
        return self.api.post("/api/v1/sessions/tailscale-key", None, **_opts(auth_token))


class CreditsResources(_Namespace):
    def me(self, *, auth_token: Optional[str] = None):
        return self.api.get("/api/v1/credits/me", **_opts(auth_token))

    def topup(
        self,
        *,
        amount_idr: Optional[int] = None,
        amount_usd_cents: Optional[int] = None,
        auth_token: Optional[str] = None,
    ):
        """Start a checkout: an IDR amount, or USD cents (PayPal). Owner/admin only (an API
        key: the role of the person who made it)."""
        if (amount_idr is None) == (amount_usd_cents is None):
            raise ValueError("topup needs exactly one of amount_idr or amount_usd_cents")
        body = {"amountIdr": amount_idr} if amount_idr is not None else {"amountUsdCents": amount_usd_cents}
        return self.api.post("/api/v1/credits/topup", body, **_opts(auth_token))


class BillingResources(_Namespace):
    def storage(self, *, auth_token: Optional[str] = None):
        """The storage sizes on offer: ``{"presets": [...], "min": ..., "max": ...}`` (GB)."""
        return self.api.get("/api/v1/billing/storage", **_opts(auth_token))

    def resize_storage(self, storage_gb: int, *, auth_token: Optional[str] = None):
        """Grow the workspace's disk (owner/admin; disks only grow)."""
        return self.api.post("/api/v1/billing/storage", {"storageGb": storage_gb}, **_opts(auth_token))


_UNSET: Any = object()


class SettingsResources(_Namespace):
    def get(self, *, auth_token: Optional[str] = None):
        return self.api.get("/api/v1/settings", **_opts(auth_token))

    def update(
        self,
        *,
        idle_auto_stop_minutes: Any = _UNSET,
        play_mode: Optional[str] = None,
        launch_options: Optional[Dict[str, Any]] = None,
        auth_token: Optional[str] = None,
    ):
        """Send only what changes. ``idle_auto_stop_minutes=None`` turns idle auto-stop off;
        ``play_mode``: browser or moonlight; ``launch_options``: fps, hdr, transport, …"""
        patch: Dict[str, Any] = {}
        if idle_auto_stop_minutes is not _UNSET:
            patch["idleAutoStopMinutes"] = idle_auto_stop_minutes
        if play_mode is not None:
            patch["playMode"] = play_mode
        if launch_options is not None:
            patch["launchOptions"] = launch_options
        if not patch:
            raise ValueError("update needs at least one of idle_auto_stop_minutes, play_mode, launch_options")
        return self.api.patch("/api/v1/settings", patch, **_opts(auth_token))


class AccountResources(_Namespace):
    def delete(self, *, auth_token: Optional[str] = None):
        """Delete the account. Person-only: Pawpado accepts it from the signed-in browser
        session alone — an API key or a Huudis token gets 401, so a leaked key cannot lock
        the owner out."""
        return self.api.post("/api/v1/account/delete", {"confirm": "DELETE"}, **_opts(auth_token))


def build_resources(api: ApiClient) -> Dict[str, _Namespace]:
    return {
        "sessions": SessionsResources(api),
        "credits": CreditsResources(api),
        "billing": BillingResources(api),
        "settings": SettingsResources(api),
        "account": AccountResources(api),
    }
