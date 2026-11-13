# Bictorys

Verified on: 2026-11-13

Sources (official documentation, read on the date above):
- https://docs.bictorys.com/llms.txt (index)
- https://docs.bictorys.com/docs/how-to-validate-webhooks.md
- https://docs.bictorys.com/docs/setup-webhook.md
- https://docs.bictorys.com/docs/test-vs-live-environment.md
- https://docs.bictorys.com/docs/get-your-api-key.md
- https://docs.bictorys.com/docs/getting-your-private-ip-address.md
- https://docs.bictorys.com/docs/status-responses-and-their-meanings.md
- https://docs.bictorys.com/docs/test-mobile-money.md
- https://docs.bictorys.com/docs/how-checkout-works.md
- https://docs.bictorys.com/reference/createcharge.md
- https://docs.bictorys.com/reference/gettransactiondetails.md
- https://docs.bictorys.com/reference/gettransactions.md

## Environments and keys

| Item | Value (from docs) |
|---|---|
| Test base URL | `https://api.test.bictorys.com` |
| Live base URL | `https://api.bictorys.com` |
| Create a charge | `POST /pay/v1/charges` (optional query `payment_type`, e.g. `wave_money`, `orange_money`, `free_money`, `card`; without it the customer is redirected to the Bictorys checkout page) |
| Transaction details (status check) | `GET /pay/v1/transactions/{transactionId}` |
| Search transactions | `GET /pay/v1/transactions?payment_reference=<your reference>` (also `start_date`, `end_date`, `type`, `customer_id`, `customer_phone`, `page_offset`, `page_size` default 20); returns a JSON array |
| API auth header | `X-Api-Key` (OpenAPI security scheme name: `X-API-Key`) |
| Keys | Three sets per account: secret (private) key for API calls, public key (identifies the account, usable from front-end / mobile for the charges API), webhook secret key. All exist in Live and Test. |
| Mode switch | Same login for both; dashboard toggle. In Live you must use the Live API key **and** configure the webhook in Live mode. |
| IP allowlist | Private key calls require the server's public IP bound to the key in Live; otherwise 403 `ACCESS_DENIED`. `0.0.0.0` (any IP) is possible but strongly discouraged by Bictorys. |

Key prefixes for test vs live: not documented - to confirm. (The docs example shows a key starting with `public-`.)

## Webhook authentication

- Header: **`X-Secret-Key`**. It contains the webhook secret key you set in the dashboard (Developers page). You must compare it with your stored webhook secret before processing.
- There is **no HMAC / signature of the body**: the header is a static shared secret. Consequences for the audit:
  - Compare with `hash_equals(config('services.bictorys.webhook_secret'), (string) $request->header('X-Secret-Key'))`. The official PHP sample uses `!==` (not constant-time): flag `===`/`!==` as Important.
  - The secret travels in every request: it must never be logged (no `Log::info($request->headers->all())`).
  - Because the body is not signed, it is strongly recommended to also confirm the payment through `GET /pay/v1/transactions/{id}` before crediting (Important if absent on high-value flows).
- Payload fields shown in the docs: `id` (transaction id), `merchantId`, `type` (`payment`, `refund`, ...), `paymentReference` (your reference passed at charge creation), `merchantReference`, `amount`, `currency`, `settledAmount`, `settledCurrency`, `merchantFees`, `customerFees`, `status`, `pspName`, `timestamp`, etc. Bictorys warns that fields may be added without notice: do not reject unknown fields.
- **`amount` does not mean the same thing in the webhook and in the API.** Webhook payload: amount paid by the customer, including customer fees if fees are passed to the customer (webhook guide). Transaction API (`GET /pay/v1/transactions...`): amount received by the merchant, **net of fees**; `merchantFees` is the fee paid by the merchant (OpenAPI schema). So: if the code compares the amount read from the API, `amount + merchantFees` against the order total is correct; if it compares the webhook payload amount, it must account for `customerFees`. Check which source the code reads before reporting a mismatch.
- Bictorys says to validate the order only on a webhook confirming the status, and to check amount, currency, status and payment reference.

Retry / redelivery policy: not documented - to confirm. Delivery ordering: not documented - to confirm. Required response code: not documented (sample returns 200) - to confirm.

## Statuses

API enum `PaymentStatus` (OpenAPI): `succeeded`, `failed`, `cancelled`, `pending`, `processing`, `reversed`, `authorized`.

The webhook sample handles `succeeded` and `authorized` as paid (lower-cased comparison). The "status responses" guide uses other labels (`initié`, `en attente`, `succès`, `échoué`, `expiré`) and an older payload shape (`event: charge.successful`, `data.status`). The docs are inconsistent: the code should compare against the API enum, lower-cased, and treat unknown values as not paid.

Pending transactions are considered expired after **2 hours** (status guide). A pending payment must be re-checked via the transaction details endpoint.

`authorized` relates to card pre-authorization (capture endpoint exists): for mobile money, treating `authorized` as paid is to confirm with Bictorys.

## Sandbox specifics

- Mobile money in sandbox uses a simulator: a QR code is scanned with the phone camera, never with a real Wave/Orange Money app.
- In sandbox, the success/error redirect URL is **not called** for mobile money payments (only for card). So a flow that relies on the redirect to finish the order will look broken in sandbox and "work" in production: that is exactly the success_url anti-pattern.

## Amounts

`amount` is typed `number` (double) in the OpenAPI spec; examples use integers for XOF (`100`, `10000`). Use integer XOF. Decimal handling for XOF: not documented - to confirm.

## Provider-specific checks

1. Webhook handler reads `X-Secret-Key` and compares with `hash_equals` against a config value; missing header = reject (401/403). Blocker if absent.
2. Live: `.env` production uses `https://api.bictorys.com`, not `api.test.bictorys.com`; the webhook is registered in **Live** mode in the dashboard (to confirm manually).
3. Private (secret) key never in the Flutter/web front-end; only the public key may be there.
4. Order lookup uses `paymentReference` that the server generated at charge creation; amount and currency compared to the order with the right formula for the source read (API: `amount + merchantFees`; webhook payload: account for `customerFees`), as integers.
5. Status compared case-insensitively against `succeeded` (and `authorized` only if the business accepts it); every other value is not paid.
6. A scheduled job re-checks pending orders via `GET /pay/v1/transactions/{id}` before the 2-hour expiry and after.
7. Server IP bound to the private key in Live (to confirm manually); `0.0.0.0` allowlist = Important.
8. No logic that relies on the success redirect being called (it is not called in sandbox for mobile money).
9. Reconciliation without the webhook: the code must not depend only on the webhook to learn the transaction id. A scheduled job should call `GET /pay/v1/transactions?payment_reference=<ref>` for orders still pending and confirm them. Missing = Important (a lost webhook means a customer who paid and never gets the order).
10. A payment marked failed after a failed attempt must still be creditable if a later attempt on the same reference succeeds (state update `WHERE status IN ('pending','failed')`, not only `pending`).
