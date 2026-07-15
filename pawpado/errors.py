"""Typed error classes for the Pawpado SDK."""

from __future__ import annotations

from typing import Any, Dict, Optional


class PawpadoAuthError(Exception):
    """Raised on Pawpado auth / OIDC failures."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message

    def __repr__(self) -> str:
        return f"PawpadoAuthError({self.code!r}, {self.message!r})"


class RefreshError(Exception):
    """Raised when refreshing an OIDC access token fails."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message

    def __repr__(self) -> str:
        return f"RefreshError({self.code!r}, {self.message!r})"


class NetworkError(Exception):
    """Raised on transport failures (DNS, connect refused, TLS, etc.)."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class PawpadoError(Exception):
    """Raised on enveloped errors (data=null, error.code/message)
    or non-2xx HTTP responses from Pawpado APIs.

    Aliased as ``ApiError`` for parity with the Node SDK's
    ``ApiError as PawpadoError`` re-export.
    """

    def __init__(
        self,
        code: str,
        message: str,
        status: int,
        *,
        request_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
        self.request_id = request_id
        self.details = details

    def __repr__(self) -> str:
        return f"PawpadoError({self.code!r}, {self.message!r}, status={self.status})"


# Alias to match Node SDK naming.
ApiError = PawpadoError
