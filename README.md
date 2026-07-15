# pawpado (Python)

Official Python SDK for [Pawpado](https://pawpado.com) — the single-user AWS
GPU gaming portal. Mirrors the Node SDK (`@forjio/pawpado-node`) 1:1.

## Install

```bash
pip install pawpado
```

## Quickstart

### Static API key (simplest)

```python
from pawpado import PawpadoClient

with PawpadoClient(api_key="...") as client:
    print(client.health())               # public, no auth
    print(client.sessions.poll())        # GET /api/v1/sessions/poll
    print(client.sessions.start())       # POST /api/v1/sessions/start
    print(client.credits.me())
    client.sessions.stop({"force": True})
```

### Huudis OIDC device flow (CLI-style)

```python
from pawpado import PawpadoClient, Session

session = Session(brand="pawpado", profile="default")
session.load()  # reads ~/.pawpado/credentials

with PawpadoClient(session=session) as client:
    print(client.account.session())
```

The ``Session`` refresh path is single-flight — concurrent callers share the
same refresh and avoid burning the Huudis refresh-token family (Huudis revokes
the entire family on reuse).

## Surface

| Namespace | Methods |
|---|---|
| ``sessions`` | ``start`` / ``stop`` / ``poll`` / ``pair`` / ``connect`` / ``tailscale_key`` |
| ``credits`` | ``me`` / ``topup`` |
| ``billing`` | ``storage`` |
| ``settings`` | ``get`` / ``update`` |
| ``account`` | ``session`` / ``delete`` |
| ``admin`` | ``reconcile`` / ``orphans`` |
| ``health()`` | top-level, no auth |

Every method takes an optional ``auth_token=`` to override the client-level
bearer for one call.

## Errors

- ``PawpadoError`` (alias: ``ApiError``) — enveloped API errors, carries
  ``.code``, ``.message``, ``.status``, ``.request_id``, ``.details``.
- ``PawpadoAuthError`` — credentials / session lookup failures.
- ``RefreshError`` — OIDC refresh failure.
- ``NetworkError`` — transport failure (DNS, TLS, etc.).

## License

MIT
