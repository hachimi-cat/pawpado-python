"""Official Python SDK for Pawpado.

Mirrors the Node SDK (`@forjio/pawpado-node`):

- :class:`PawpadoClient` — sessions / credits / billing / settings / account /
  admin / health, with Bearer auth via either a :class:`Session` (Huudis OIDC
  device flow + refresh) or a static ``api_key``.
- :class:`Session` — multi-profile credentials store with single-flight refresh,
  the Python parity of ``@forjio/sdk``'s Session.
- :class:`ApiClient` — typed HTTP client with envelope unwrap, proactive +
  reactive token refresh, and auto-pagination.
"""

from .client import PawpadoClient
from .errors import (
    ApiError,
    NetworkError,
    PawpadoAuthError,
    PawpadoError,
    RefreshError,
)
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
from .session import ProfileData, Session

__all__ = [
    # client
    "PawpadoClient",
    # errors
    "ApiError",
    "NetworkError",
    "PawpadoAuthError",
    "PawpadoError",
    "RefreshError",
    # resources
    "ApiClient",
    "AccountResources",
    "AdminResources",
    "BillingResources",
    "CreditsResources",
    "SessionsResources",
    "SettingsResources",
    "build_resources",
    # session
    "ProfileData",
    "Session",
]

__version__ = "0.1.0"
