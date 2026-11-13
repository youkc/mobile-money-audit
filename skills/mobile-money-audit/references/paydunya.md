# PayDunya (HTTP/JSON API, "Paiement Avec Redirection")

Verified on: 2026-11-13

Sources (official documentation, read on the date above):
- https://developers.paydunya.com/doc/FR/http_json

## Environments and keys

| Item | Value (from docs) |
|---|---|
| Create invoice, test | `POST https://app.paydunya.com/sandbox-api/v1/checkout-invoice/create` |
| Create invoice, production | `POST https://app.paydunya.com/api/v1/checkout-invoice/create` |
| Confirm / status, test | `GET https://app.paydunya.com/sandbox-api/v1/checkout-invoice/confirm/[invoice_token]` |
| Confirm / status, production | `GET https://app.paydunya.com/api/v1/checkout-invoice/confirm/[invoice_token]` |
| Auth headers | `PAYDUNYA-MASTER-KEY`, `PAYDUNYA-PRIVATE-KEY`, `PAYDUNYA-TOKEN` |
| Test key format | Docs examples: private key `test_private_...`, invoice token `test_...`, checkout URL `.../sandbox-checkout/invoice/...` |
| Success response | `response_code == "00"` (every JSON response has `response_code` and `response_text`) |
| Mode | Application created in the dashboard in test mode, then "ACTIVER LE MODE DE PRODUCTION" |

Live key prefixes: not documented - to confirm (test keys start with `test_` in examples).

## IPN (callback_url) authentication

- Set with `actions.callback_url` when creating the invoice (also `return_url`, `cancel_url`).
- PayDunya sends a **POST `application/x-www-form-urlencoded`** to the callback URL; the payment data is under the **`data`** key (`$request->input('data')`).
- Authentication field: **`data.hash`** = **SHA-512 of your MasterKey**. Verify with `hash_equals(hash('sha512', $masterKey), $data['hash'])`.
  - This hash is **static** (same for every notification, not tied to the payload). It proves knowledge of a value that appears in every notification; a leaked notification allows forging others. Recommended: confirm via `GET .../checkout-invoice/confirm/{token}` before crediting (Important if missing).
- Payload: `response_code`, `response_text`, `hash`, `invoice` (`token`, `items`, `taxes`, `total_amount`, `description`), `custom_data`, `actions`, `mode`, `status`, `fail_reason` (cards only), `customer`, `receipt_url`.

Retry / redelivery policy, expected response, duplicates: not documented - to confirm. Assume duplicates can happen.

## Statuses

- Confirm API and IPN: `pending`, `cancelled`, `completed`; the IPN section also mentions **`failed`**. Docs use lower case in payloads and upper case in prose (`PENDING`, `CANCELLED`, `COMPLETED`): compare case-insensitively.
- Paid = `completed` only.
- `pending` can automatically become `cancelled` **24 h** after invoice creation if unpaid. Use the Confirm API to resolve pending invoices.
- IPN is sent for confirmed, cancelled or failed payments; PayDunya notes confirmation is not always instantaneous (customer typing the PIN, network latency).

## Amounts

- `invoice.total_amount` is required (with `store.name`). Examples use integer amounts (`5000`, `42300`); the IPN returns it as a string (`'42300'`). Compare as integers.
- Decimal handling for XOF: not documented - to confirm. Use integer XOF.

## Provider-specific checks

1. Callback handler reads `$request->input('data')` (form-encoded, not JSON body) and checks `hash_equals(hash('sha512', config('services.paydunya.master_key')), $data['hash'] ?? '')`. Blocker if absent.
2. Payment confirmed through `GET /checkout-invoice/confirm/{token}` (server-side, with the three key headers) before crediting, or at least the hash check plus amount check. Recommended because the hash is static.
3. Sandbox vs production: `sandbox-api` URLs and `test_` keys only outside production; production uses `/api/v1/` URLs with live keys, from env.
4. `invoice.token` stored at creation with a unique index; order found by it (or by `custom_data` set server-side and cross-checked).
5. `status == 'completed'` (case-insensitive) is the only paid state; `failed` and `cancelled` handled.
6. `invoice.total_amount` compared to the order total (integer).
7. Scheduled job confirms invoices still pending (they auto-cancel after 24 h).
8. `callback_url` / `return_url` are HTTPS in production (the docs examples use `http://`: do not copy them).
9. `return_url` handler does not validate the payment. PayDunya appends `?token=<invoice_token>` to the return URL: the handler may use that token to call the Confirm API server-side, but must never mark the order paid just because the token is present.
