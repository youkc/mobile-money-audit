# Wave (Checkout API)

Verified on: 2026-11-13

Sources (official documentation, read on the date above):
- https://docs.wave.com/webhook
- https://docs.wave.com/checkout

## Environments and keys

| Item | Value (from docs) |
|---|---|
| Base URL | `https://api.wave.com` |
| Create checkout session | `POST /v1/checkout/sessions` |
| Get a session (status check) | `GET /v1/checkout/sessions/:id` |
| Find by transaction | `GET /v1/checkout/sessions?transaction_id=...` |
| Find by your reference | `GET /v1/checkout/sessions/search?client_reference=...` |
| Expire / refund | `POST /v1/checkout/sessions/:id/expire`, `POST /v1/checkout/sessions/:id/refund` |
| API auth | `Authorization: Bearer <api key>` over HTTPS. Keys are bound to one business wallet; must stay on your servers, never client-side. |
| Key example format | `wave_sn_prod_...` (docs example) |
| Optional request signing | An API key can be created with request signing; then every API request must carry `Wave-Signature` (cannot be disabled on that key). Requests rejected if timestamp > 5 min in the past or > 30 s in the future. |
| IP allowlisting on API keys | Available (recommended by Wave). |

Sandbox / test environment and test key format: not documented on these pages - to confirm. (Only a single base URL is documented.)

## Webhook authentication

Two strategies, chosen when the webhook is registered in the Business Portal:

1. **Shared secret** (simpler, less secure): `Authorization: Bearer <webhook secret>` header. Compare with `hash_equals`.
2. **Signing secret (recommended by Wave)**: header **`Wave-Signature: t=<unix timestamp>,v1=<hex signature>[,v1=...]`**.
   - Algorithm: **HMAC-SHA256**, key = webhook secret, message = `timestamp . raw_body` (timestamp string concatenated with the raw request body, no separator), hex digest.
   - Several `v1=` values may be present during secret rotation: accept if any matches.
   - Reject requests whose timestamp is older than **5 minutes** (replay protection).
   - Must use the **raw body** (`$request->getContent()`); re-encoding parsed JSON breaks the signature (Wave lists this as the most common failure).
   - The official PHP sample uses `in_array` (not constant-time) and does not check the timestamp: in the audit, require `hash_equals` in a loop over the `v1` values plus the 5-minute timestamp check.
- The webhook secret is different from the API key; it is shown once at registration.
- Wave's IP ranges for webhooks are listed in the docs (an October 2026 notice adds `87.192.0.0/19`). Wave says to whitelist all of them if you filter by IP, otherwise some webhooks are randomly rejected. IP filtering is complementary, not a replacement for signature checking.

Endpoint requirements (docs): accept POST, HTTPS with valid certificate, respond within **5 seconds**, return 2xx, handle duplicates.

## Delivery and retries

- Non-2xx: Wave retries for up to **3 days**.
- Events may be **missed**, **delivered multiple times**, and arrive **out of order**. Use the event `id` for idempotency.
- During secret rotation (duplicated webhook), every event is delivered twice, once per secret.

## Events and statuses

Event envelope: `id` (unique event id), `type`, `data`.

Checkout events: `checkout.session.completed`, `checkout.session.payment_failed` (several failures can precede a success). Others: `b2b.payment_received`, `b2b.payment_failed`, `merchant.payment_received`, `test.test_event`.

Checkout session fields: `checkout_status` = `open` | `complete` | `expired`; `payment_status` = `processing` | `cancelled` | `succeeded`; `client_reference` (yours, up to 255 chars); `amount`, `currency`, `transaction_id`, `when_expires`, `last_payment_error`.

Sessions expire **30 minutes** after creation by default.

Paid = `payment_status == 'succeeded'` (and `checkout_status == 'complete'`). Out-of-order delivery means a `payment_failed` arriving after `completed` must not downgrade a paid order.

## Amounts

- Amounts are **strings** (e.g. `"1000"`).
- XOF: **decimal places are not allowed**. Send `"5000"`, never `"5000.00"`, never `5000 * 100`.
- `amount` is gross of fees (amount to collect from the customer).
- `success_url` and `error_url` must be fully-qualified `https` URLs. They are browser redirects, distinct from the webhook.

## Provider-specific checks

1. Webhook: `Wave-Signature` parsed, HMAC-SHA256 of `t . rawBody` with the webhook secret, `hash_equals` against each `v1`, timestamp within 5 minutes. Or, if the shared-secret strategy is used, `hash_equals` on the Bearer token. Blocker if neither.
2. Signature computed on `$request->getContent()`, not on `json_encode($request->all())`.
3. Idempotency keyed on the event `id` and/or the checkout session `id` / `transaction_id` (unique index).
4. Order resolved by `client_reference` set server-side; amount (string, compare as integer) and `currency == 'XOF'` checked against the order.
5. Amount sent as an integer string without decimals.
6. Webhook answers 2xx within 5 s (heavy work queued). A handler that does slow work synchronously = Important.
7. Status reconciliation job uses `GET /v1/checkout/sessions/:id` (or `search?client_reference=`) for sessions still open; sessions expire after 30 min by default.
8. Late `payment_failed` events do not overwrite a `succeeded` order.
9. API key only server-side (never in the Flutter app or JS).
10. If IP filtering is used, the full current Wave IP list is allowed (to confirm manually, including the 2026 range).
