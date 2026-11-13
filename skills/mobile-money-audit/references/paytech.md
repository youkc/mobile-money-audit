# PayTech (paytech.sn, by Intech)

Verified on: 2026-11-13

Sources (official documentation, read on the date above):
- https://docs.intech.sn/doc_paytech.php (formerly doc.paytech.sn)
- https://github.com/touskar/laravel-paytech (repository linked from the docs as "Laravel PayTech"; source read on the date above)
- https://packagist.org/packages/babaly/laravel-paytech (package name declared by that repository)

## Environments and keys

| Item | Value (from docs) |
|---|---|
| Base URL | `https://paytech.sn/api` (same URL for test and prod) |
| Request payment | `POST /payment/request-payment` -> returns `token` and `redirect_url` (`https://paytech.sn/payment/checkout/<token>`) |
| Payment status | `GET /payment/get-status?token_payment=<token>` |
| Refund | `POST /payment/refund-payment` |
| Auth headers | `API_KEY` and `API_SECRET` on every request |
| Mode | Request parameter **`env`** = `test` or `prod`. **Default is `prod`** if omitted. |
| Production activation | Manual account validation by PayTech (e-mail with NINEA and ID). Without activation, `env=prod` returns an error. |

Test vs live keys: the docs do not describe separate key pairs per environment; the mode is chosen by `env` - to confirm.

**Sandbox is not free**: in `env=test`, the customer is really debited a random amount between **100 and 150 CFA**, whatever the order amount. PayTech says sandbox must never be used for public transactions.

Request parameters (selection): `item_name`, `item_price` (number, required), `ref_command` (unique order reference, required), `command_name`, `currency` (XOF, EUR, USD, CAD, GBP, MAD; default XOF), `env`, `ipn_url` (**HTTPS only**), `success_url`, `cancel_url`, `custom_field` (JSON string), `target_payment`, `refund_notif_url` (HTTPS).

## IPN authentication

PayTech POSTs the notification to `ipn_url`. Two documented verification methods:

1. **HMAC-SHA256 (recommended by PayTech)**: field **`hmac_compute`** in the notification.
   - Payments: message = `amount|ref_command|api_key`, key = `api_secret`, hex digest. PayTech's samples use `final_item_price` (falling back to `item_price`) as the amount.
   - Transfers: message = `amount|id_transfer|api_key`.
2. **SHA256 of keys ("classic")**: fields `api_key_sha256` and `api_secret_sha256` must equal `hash('sha256', API_KEY)` and `hash('sha256', API_SECRET)`.
   - These hashes are **static**: they are the same in every notification and do not depend on the payload. Anyone who sees one notification (logs, proxy) can forge others. Treat this method alone as weak: require a `get-status` counter-check before crediting (Important if missing).

Audit notes on PayTech's own samples:
- The official PHP sample uses HMAC **if `hmac_compute` is present, else falls back** to the SHA256 method. An attacker can drop `hmac_compute` to force the weaker check. Flag this fallback (Important) unless a `get-status` call confirms the payment.
- The SHA256 comparison in the samples uses `===` (not constant-time); require `hash_equals`.
- `refund_complete` and `transfer_failed` sample payloads show no `hmac_compute`: refund/transfer notifications may only be verifiable by the SHA256 method - to confirm.

Notification format: the PHP sample reads `$_POST` (form-encoded); Laravel `$request->input()` works for both form and JSON. Exact content type: not explicitly documented - to confirm.

Retry / redelivery policy, expected response body/code: not documented (samples return `IPN OK` / 200 on success, 403 on failure) - to confirm. Duplicate notifications: not documented - assume they can happen.

## Events and statuses

IPN `type_event`: `sale_complete` (paid), `sale_canceled` (canceled), `refund_complete` (to `refund_notif_url`), `transfer_success` / `transfer_failed` (to the transfer `callback_url`).

Payment IPN fields: `type_event`, `ref_command`, `item_name`, `item_price`, `item_price_xof`, `initial_item_price`, `final_item_price` (after promo), `promo_enabled`, `promo_value_percent`, `currency`, `command_name`, `token`, `env`, `payment_method`, `client_phone`, `custom_field` (Base64-encoded in the payment sample), `api_key_sha256`, `api_secret_sha256`, `hmac_compute`.

- **Promotions**: `final_item_price` can be lower than the order amount (example: 60000 -> 55000 with an 8.33% promo). The amount check must decide explicitly whether a PayTech promo is accepted; comparing only `item_price` may hide a different amount actually paid.
- The IPN contains `env`: a production handler should reject `env=test` notifications.
- Payment `get-status` response format and status values: not documented on the page (transfer status uses `state` = `pending` | `failed` | `success`) - to confirm.

## Laravel package caveat

The docs show a Laravel package `composer require touskar/laravel-paytech` with `Touskar\LaravelPaytech\Paytech`, `verifyIPN()` and a route middleware **`paytech.ipn`** ("automatic verification"). On the verification date:
- `touskar/laravel-paytech` is **not on Packagist**; the linked GitHub repository declares the package `babaly/laravel-paytech` (namespace `Babaly\LaravelPaytech`, last push 2022-12, requires `illuminate/contracts ^9.0`).
- That repository contains **no `verifyIPN()` and no `paytech.ipn` middleware**. Its published stubs:
  - disable TLS verification (`CURLOPT_SSL_VERIFYPEER` 0 and `CURLOPT_SSL_VERIFYHOST` 0) in `PaytechService::post()`;
  - register `GET ipn` pointing to a non-existent `ipn` method;
  - save the payment in the **success_url** handler from query-string data (`$_GET['data']`);
  - default to `setTestMode(true)` and hard-code `$IPN_URL`.

So: if the audited project uses `->middleware('paytech.ipn')`, check that the middleware actually exists in the project (`app/Http/Kernel.php`, `bootstrap/app.php`, a service provider). A middleware alias that is not registered makes Laravel throw at runtime; a custom one must be read and checked like any IPN verification. If the project published the `babaly/laravel-paytech` stubs, each item above is a finding.

## Provider-specific checks

1. IPN handler verifies `hmac_compute` with `hash_equals(hash_hmac('sha256', "$amount|$ref_command|$apiKey", $apiSecret), $hmac)`; no silent fallback to the SHA256-of-keys method when `hmac_compute` is missing (or, if the fallback exists, a `get-status` call confirms the payment). Blocker if no verification at all.
2. `env` is set explicitly from config (`env=prod` in production, `test` elsewhere); not hard-coded, not left to the default. IPN with `env=test` rejected in production.
3. `ipn_url` is HTTPS and public (no localhost/ngrok); IPN route excluded from CSRF only.
4. `ref_command` generated server-side, unique (DB unique index), used to find the order.
5. Amount check against the order using `final_item_price` / `item_price_xof`, with an explicit rule for promotions; currency checked.
6. `custom_field` treated as untrusted data (Base64 + JSON decode in try/catch), never used to pick the amount or the user to credit without cross-check.
7. Pending orders reconciled by a scheduled job calling `GET /payment/get-status?token_payment=` (store the `token` returned at request time).
8. No `CURLOPT_SSL_VERIFYPEER`/`VERIFYHOST` disabled (common in copied PayTech code).
9. `success_url` handler does not mark the order paid (the published package stub does).
10. Testing note for the report: sandbox debits 100 to 150 CFA for real; production requires manual activation (to confirm manually).
