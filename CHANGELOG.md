# Changelog

## 0.3.0
- `verify_webhook(raw_body, signature_header, secret)` returns a webhook delivery's event (`id`, `type`, `occurredAt`, `workspaceId`, `data`) or raises `PawpadoWebhookError`; `verify_webhook_signature(...)` answers True/False. Both check `Pawpado-Signature` (`t=…,v1=…`) over the raw body and refuse a timestamp more than 5 minutes off (`tolerance_seconds`).
- `client.api`: the webhook delivery log and the event catalogue — `webhooks_deliveries(subscription_id=…, status=…, type_=…, limit=…, cursor=…)`, `webhooks_get_deliveries(delivery_id)`, `webhooks_deliveries_retry(delivery_id)`, `webhooks_event_types()`; `webhooks_update(id_, url=…, events=…, active=…)` takes `url` and `events` as well as `active` (regenerated).

## 0.2.0
- `client.api.<area>_<action>(...)`: every Pawpado feature route, one method each, generated from
  the API spec (`pawpado/api_generated.py`, made by `scripts/apigen.sh`). `client.api` keeps the
  raw `get` / `post` / `patch` / `put` / `delete` / `paginate` it always had.
- `api_key` takes a Pawpado API key (`paw_live_…`) or a Huudis access token; every customer route
  now accepts both.
- Breaking — the hand-written methods now match what the server takes: `credits.topup(amount_idr=…
  | amount_usd_cents=…)`, `settings.update(idle_auto_stop_minutes=…, play_mode=…,
  launch_options=…)`, `sessions.pair(pin, …)`, new `billing.resize_storage(storage_gb)`,
  `account.delete()` POSTs `{"confirm": "DELETE"}` (person-only — browser session).
- Removed: `account.session()` (the browser's own session probe) and `admin` (operator-only).

## 0.1.0
- Initial tracked release.
