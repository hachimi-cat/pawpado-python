"""Official Python SDK for Pawpado.

Mirrors the Node SDK (`@forjio/pawpado-node`):

- :class:`PawpadoClient` — sessions / credits / billing / settings / account /
  health, and ``client.api`` (every route, generated from the API spec), with Bearer
  auth via either a :class:`Session` (Huudis OIDC device flow + refresh) or an
  ``api_key`` (a ``paw_live_…`` key, or a Huudis access token).
- :class:`Session` — multi-profile credentials store with single-flight refresh,
  the Python parity of ``@forjio/sdk``'s Session.
- :class:`ApiClient` — typed HTTP client with envelope unwrap, proactive +
  reactive token refresh, and auto-pagination.
"""

from .api_generated import GeneratedApi
from .client import PawpadoApi, PawpadoClient
from .errors import (
    ApiError,
    NetworkError,
    PawpadoAuthError,
    PawpadoError,
    RefreshError,
)
from .resources import (
    AccountResources,
    ApiClient,
    BillingResources,
    CreditsResources,
    SessionsResources,
    SettingsResources,
    build_resources,
)
from .session import ProfileData, Session
from .webhooks import PawpadoWebhookError, verify_webhook, verify_webhook_signature

__all__ = [
    # client
    "PawpadoClient",
    "PawpadoApi",
    "GeneratedApi",
    # errors
    "ApiError",
    "NetworkError",
    "PawpadoAuthError",
    "PawpadoError",
    "RefreshError",
    # resources
    "ApiClient",
    "AccountResources",
    "BillingResources",
    "CreditsResources",
    "SessionsResources",
    "SettingsResources",
    "build_resources",
    # session
    "ProfileData",
    "Session",
    # webhooks
    "PawpadoWebhookError",
    "verify_webhook",
    "verify_webhook_signature",
]

__version__ = "0.3.0"
