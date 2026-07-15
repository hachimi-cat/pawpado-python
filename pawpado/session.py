"""Multi-profile credentials store mirroring @forjio/sdk's Session.

INI-format ``~/.pawpado/credentials``, one section per profile. Single-flight
refresh guard prevents concurrent calls from burning the Huudis refresh-token
family (Huudis revokes the entire family on reuse — see the
``feedback_huudis_refresh_singleflight`` rule).

This is the Python parity of the Node ``Session`` from ``@forjio/sdk``. If a
central ``forjio-sdk-py`` is later extracted, this module moves there
unchanged.
"""

from __future__ import annotations

import configparser
import os
import stat
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Optional
from urllib.parse import urlencode

import httpx

from .errors import PawpadoAuthError, RefreshError


@dataclass
class ProfileData:
    access_token: str
    expires_at: int
    issuer: str
    client_id: str
    refresh_token: Optional[str] = None
    scope: Optional[str] = None
    account_id: Optional[str] = None


# Default refresh implementation — hits the OIDC token endpoint at
# ``{issuer}/api/v1/oidc/token``. Tests inject their own via the
# ``refresh_impl`` constructor arg.
def _default_refresh(
    *,
    issuer: str,
    client_id: str,
    refresh_token: str,
    scope: Optional[str] = None,
    http: Optional[httpx.Client] = None,
) -> Dict[str, Any]:
    body = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": client_id,
    }
    if scope:
        body["scope"] = scope
    client = http or httpx.Client(timeout=10.0)
    owns = http is None
    try:
        res = client.post(
            f"{issuer.rstrip('/')}/api/v1/oidc/token",
            headers={"content-type": "application/x-www-form-urlencoded"},
            content=urlencode(body),
        )
    except httpx.HTTPError as e:
        raise RefreshError("NETWORK_ERROR", str(e)) from e
    finally:
        if owns:
            client.close()
    try:
        payload = res.json()
    except Exception:
        payload = {}
    if res.status_code >= 400:
        code = (payload.get("error") if isinstance(payload, dict) else None) or "refresh_failed"
        desc = (payload.get("error_description") if isinstance(payload, dict) else None) or "refresh failed"
        raise RefreshError(str(code).upper(), str(desc))
    return payload


class Session:
    def __init__(
        self,
        *,
        brand: str = "pawpado",
        profile: Optional[str] = None,
        credentials_path: Optional[str] = None,
        http: Optional[httpx.Client] = None,
        refresh_impl: Optional[Callable[..., Dict[str, Any]]] = None,
    ) -> None:
        self.brand = brand
        env_key = f"{brand.upper()}_PROFILE"
        self.profile = profile or os.environ.get(env_key, "default")
        self.credentials_path = Path(
            credentials_path or os.path.expanduser(f"~/.{brand}/credentials")
        )
        self.http = http
        self._refresh_impl = refresh_impl or _default_refresh
        self._data: Optional[ProfileData] = None
        self._refresh_lock = threading.Lock()
        self._refresh_in_flight: Optional[threading.Event] = None
        self._refresh_error: Optional[BaseException] = None

    @property
    def data(self) -> Optional[ProfileData]:
        return self._data

    def set_data(self, data: ProfileData) -> None:
        """In-memory only — useful for tests and ad-hoc use."""
        self._data = data

    def load(self) -> ProfileData:
        if not self.credentials_path.exists():
            raise PawpadoAuthError(
                "SESSION_NOT_FOUND",
                f"credentials file not found at {self.credentials_path}",
            )
        parser = configparser.ConfigParser()
        parser.read(self.credentials_path)
        if not parser.has_section(self.profile):
            raise PawpadoAuthError(
                "PROFILE_NOT_FOUND",
                f"profile [{self.profile}] not in {self.credentials_path}",
            )
        section = parser[self.profile]
        for required in ("access_token", "issuer", "client_id"):
            if required not in section:
                raise PawpadoAuthError(
                    "SESSION_INCOMPLETE",
                    f"profile [{self.profile}] missing {required}",
                )
        self._data = ProfileData(
            access_token=section["access_token"],
            expires_at=int(section.get("expires_at", "0") or "0"),
            issuer=section["issuer"],
            client_id=section["client_id"],
            refresh_token=section.get("refresh_token") or None,
            scope=section.get("scope") or None,
            account_id=section.get("account_id") or None,
        )
        return self._data

    def save(self, data: Optional[ProfileData] = None) -> None:
        if data is not None:
            self._data = data
        if self._data is None:
            raise RuntimeError("Session.save called with no data")
        parser = configparser.ConfigParser()
        if self.credentials_path.exists():
            parser.read(self.credentials_path)
        parser[self.profile] = {
            "access_token": self._data.access_token,
            "expires_at": str(self._data.expires_at),
            "issuer": self._data.issuer,
            "client_id": self._data.client_id,
        }
        if self._data.refresh_token:
            parser[self.profile]["refresh_token"] = self._data.refresh_token
        if self._data.scope:
            parser[self.profile]["scope"] = self._data.scope
        if self._data.account_id:
            parser[self.profile]["account_id"] = self._data.account_id
        self.credentials_path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=".credentials.", dir=str(self.credentials_path.parent))
        try:
            with os.fdopen(fd, "w") as f:
                parser.write(f)
            os.chmod(tmp, stat.S_IRUSR | stat.S_IWUSR)
            os.replace(tmp, self.credentials_path)
        except Exception:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise

    def clear(self) -> None:
        if not self.credentials_path.exists():
            self._data = None
            return
        parser = configparser.ConfigParser()
        parser.read(self.credentials_path)
        if parser.has_section(self.profile):
            parser.remove_section(self.profile)
        self._data = None
        if not parser.sections():
            self.credentials_path.unlink(missing_ok=True)
            return
        fd, tmp = tempfile.mkstemp(prefix=".credentials.", dir=str(self.credentials_path.parent))
        try:
            with os.fdopen(fd, "w") as f:
                parser.write(f)
            os.chmod(tmp, stat.S_IRUSR | stat.S_IWUSR)
            os.replace(tmp, self.credentials_path)
        except Exception:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise

    def is_expired(self) -> bool:
        if self._data is None:
            return True
        return time.time() >= self._data.expires_at

    def will_expire_soon(self, buffer_sec: int = 300) -> bool:
        if self._data is None:
            return True
        return time.time() + buffer_sec >= self._data.expires_at

    def refresh(self) -> None:
        """Single-flight refresh. Concurrent callers share the same refresh."""
        with self._refresh_lock:
            if self._refresh_in_flight is not None:
                event = self._refresh_in_flight
            else:
                self._refresh_in_flight = threading.Event()
                self._refresh_error = None
                event = self._refresh_in_flight
                self._spawn_refresh()
        event.wait()
        if self._refresh_error is not None:
            raise self._refresh_error

    def _spawn_refresh(self) -> None:
        try:
            self._do_refresh()
        except BaseException as e:  # noqa: BLE001
            self._refresh_error = e
        finally:
            event = self._refresh_in_flight
            with self._refresh_lock:
                self._refresh_in_flight = None
            if event is not None:
                event.set()

    def _do_refresh(self) -> None:
        if self._data is None:
            raise RefreshError("NO_SESSION", "load() or set_data() before refresh()")
        if not self._data.refresh_token:
            raise RefreshError("NO_REFRESH_TOKEN", "session has no refresh_token")
        payload = self._refresh_impl(
            issuer=self._data.issuer,
            client_id=self._data.client_id,
            refresh_token=self._data.refresh_token,
            scope=self._data.scope,
            http=self.http,
        )
        expires_in = int(payload.get("expires_in", 3600))
        self._data = ProfileData(
            access_token=payload["access_token"],
            expires_at=int(time.time()) + expires_in,
            issuer=self._data.issuer,
            client_id=self._data.client_id,
            refresh_token=payload.get("refresh_token") or self._data.refresh_token,
            scope=payload.get("scope") or self._data.scope,
            account_id=self._data.account_id,
        )
        # Only persist if we have a credentials file already on disk; in-memory
        # sessions stay in memory.
        if self.credentials_path.exists():
            self.save()
