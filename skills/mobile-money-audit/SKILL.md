---
name: mobile-money-audit
description: Read-only pre-production audit of the mobile money payment integration in a Laravel app (Bictorys, Wave, PayTech, PayDunya, or any other provider). Checks webhook/IPN authentication, idempotency, server-side amount checks, XOF integer amounts, pending-payment resolution, test vs live configuration, secrets, CSRF, HTTPS, logs and API error handling, then returns a GO / NO-GO verdict with file:line fixes. Use when the user asks to audit, review or check a mobile money / Wave / Orange Money / PayTech / PayDunya / Bictorys payment integration, or asks whether their payment code is ready for production.
---

# Mobile money integration audit (Laravel)

You audit the code that takes mobile money payments in a Laravel application and decide whether it can go to production. The audit is **read-only**.

## Hard rules

1. **Never modify the audited project.** No edits, no new files, no `composer`/`npm` install, no migrations, no `artisan` commands that write (cache, migrate, queue, key:generate...). Reading files and running read-only commands (`grep`, `cat`, `git log`, `php artisan route:list` if it already works) is fine. Proposed fixes go in the report, not in the code.
2. **Never print a secret in clear.** When you find a key, token, password or webhook secret, report its location and a masked value: first 4 characters, then `****`, then the length. Example: `.env:12 PAYTECH_API_SECRET = 9f3a**** (64 chars)`. This also applies to values found in `.env`, logs, tests, seeders and git history.
3. **Never call a payment provider API**, even sandbox, and never send a test webhook. The audit is static.
4. **Answer in the user's language** (the language of their request). The report labels below are given in English; translate them (for French: `Bloquant`, `Important`, `Mineur`, `A confirmer manuellement`).
5. **Do not invent provider details.** Provider-specific facts come only from the provider reference file. If a fact you need is missing there, say so and put it under "To confirm manually".

## Step 1 - Detect the provider(s)

Search the project (exclude `vendor/`, `node_modules/`, `storage/`):

| Provider | Composer packages | API hosts / strings | Typical env/config names |
|---|---|---|---|
| Bictorys | (none official known) | `api.bictorys.com`, `api.test.bictorys.com`, `X-Secret-Key`, `X-Api-Key` | `BICTORYS_*` |
| Wave | (none official known) | `api.wave.com`, `Wave-Signature`, `checkout/sessions`, `wave_sn_` | `WAVE_*` |
| PayTech | `babaly/laravel-paytech`, any `*paytech*` | `paytech.sn`, `request-payment`, `get-status`, `hmac_compute`, `api_key_sha256` | `PAYTECH_*` |
| PayDunya | `paydunya/*` | `app.paydunya.com`, `PAYDUNYA-MASTER-KEY`, `checkout-invoice` | `PAYDUNYA_*` |

Useful searches: `composer.json`, `config/services.php`, `config/*.php`, `.env.example`, `.env` (mask values), `routes/*.php`, `app/**` for the hosts above and for words like `webhook`, `ipn`, `callback`, `notify`, `payment`, `paiement`, `checkout`.

Then load **only** the matching reference file(s) from `references/` next to this file:
- `references/bictorys.md`
- `references/wave.md`
- `references/paytech.md`
- `references/paydunya.md`

Each reference has a line `Verified on: YYYY-MM-DD`. If that date is more than 6 months before today, add a `Minor` finding: "Reference for <provider> last verified on <date>: provider details may have changed, re-check the official documentation."

**Provider without a reference file** (Orange Money, Free Money, MTN MoMo, CinetPay, Kkiapay, FedaPay, etc.): say so at the top of the report, run all common checks below, and list in "To confirm manually" exactly which facts to look up in that provider's official docs: how notifications are authenticated (header name, algorithm, what is signed), notification retry policy and duplicates, exact success/pending/failed status names, status-check endpoint, sandbox vs production base URLs and key formats, amount format for XOF.

If no payment code is found at all, say so and stop.

## Step 2 - Map the payment flow

Before judging, locate and note (file:line) each of these. Missing pieces are findings.
1. Where a payment is **initiated** (controller/service calling the provider) and where the amount comes from.
2. The **notification endpoint** (webhook / IPN / callback route + controller).
3. The **return pages** (success_url / return_url / cancel_url handlers).
4. The **order/payment model + migration** (status column, amount column type, provider reference column, unique indexes).
5. Any **scheduled job / command** that re-checks pending payments (`app/Console/Kernel.php`, `routes/console.php`, `bootstrap/app.php` `withSchedule`, jobs).

## Step 3 - Common checks

Apply every check. Severity guide: **Blocker** = money can be lost, an order can be marked paid without payment, or a secret is exposed. **Important** = real risk or likely incident in production. **Minor** = hygiene.

### 3.1 Notification authenticity - Blocker if missing
- The webhook/IPN handler must authenticate the request **before** changing anything: provider signature or shared secret as documented in the reference file, **or** a server-to-server call to the provider's status API whose result (not the notification body) decides the outcome.
- Secrets and signatures are compared in constant time: `hash_equals($expected, $received)`. `==`, `===`, `in_array`, `strcmp` on a secret or signature = Important (timing leak). Note: some providers' own sample code uses non constant-time comparison; still flag it.
- HMAC must be computed on the **raw body** when the provider signs the body (`$request->getContent()`), not on re-encoded JSON.
- A missing header/field must lead to rejection, not to skipping the check (`if ($sig && ...)` patterns are a Blocker).
- An IP allowlist alone is not authentication (Important if it is the only control).

### 3.2 Idempotency - Blocker if missing
The same notification received twice (or a notification plus a status poll, or two concurrent deliveries) must credit the order **once**.
- A DB unique constraint on the provider transaction/event reference (migration `->unique()`), and/or
- A state transition guarded atomically: `DB::transaction` + `lockForUpdate()`, or a conditional update (`where('status', 'pending')->update([...])` and check the affected row count), or `Cache::lock`.
- "Check status then update" without a lock or transaction = race condition, Important at least; Blocker if it triggers a credit, wallet top-up, delivery or e-mail with value.
- Side effects (credit balance, send goods, dispatch jobs) happen only on the actual transition to paid.

### 3.3 Amount and currency - Blocker if wrong
- Amount and currency sent to the provider are computed **server-side** from the order (DB prices), never taken from the request (`$request->amount`, hidden form field, mobile app payload).
- On notification, the paid amount and currency (from the verified notification or from the status API) are **compared to the stored order** before marking it paid. A missing comparison = Blocker.
- The order is found by a reference the server generated, not by a client-supplied id alone.

### 3.4 XOF amounts are integers - Important (Blocker if amounts are corrupted)
- XOF has no decimals. Amount columns should be integer types (`integer`, `bigInteger`, `unsignedBigInteger`) or `decimal(…,0)`; `float`/`double` columns or `(float)` casts on money = Important.
- No `* 100` / `/ 100` conversion inherited from Stripe or card gateways: 5000 XOF must be sent as 5000 unless the reference file says otherwise. A `* 100` on XOF = Blocker (customer charged 100 times or order mismatch).
- No `round()`/`number_format()` producing `"5 000"` or `"5000.00"` in API payloads unless the reference file says the provider accepts it.

### 3.5 Pending payments are resolved later - Important
Mobile money is asynchronous: the customer confirms on their phone, the network can be slow, notifications can be lost.
- There must be a scheduled task (command or job in the scheduler) that queries the provider's status API for orders still pending after N minutes and resolves them (paid / failed / expired).
- Without it, a lost notification = a customer who paid and never got the order. Flag the absence as Important; Blocker if the provider reference says notifications can be missed and nothing else recovers them.

### 3.6 The return page never validates a payment - Blocker
- `success_url` / `return_url` handlers must only **display** a status read from the DB (or trigger a server-side status check). Marking an order paid, crediting, or delivering in that handler = Blocker: anyone can open that URL.
- Same for any route where the client (web or Flutter/mobile app) reports "payment succeeded".

### 3.7 Test vs live configuration - Blocker if production uses test settings
- Keys, base URLs and mode flags come from config/env, and are consistent: live keys with production URLs, test keys with sandbox URLs. Use the reference file for each provider's actual URLs, key prefixes and mode parameters.
- Hard-coded sandbox URLs or test mode in code (`env => 'test'`, `setTestMode(true)`, `sandbox-api`) without an env switch = Important; Blocker if `.env` / `.env.production` clearly targets production.
- No `ngrok`, `localhost`, `127.0.0.1`, `*.test`, `expose.dev`, `trycloudflare` URLs in callback/IPN/success URLs used in production config.
- `APP_ENV=production` and `APP_DEBUG=false` in the production env file if present (debug pages can leak keys).

### 3.8 Secrets - Blocker if committed
- API keys, secrets and webhook secrets live in `.env` and are read through `config()` (not `env()` outside config files, which breaks with `config:cache` = Minor).
- No secret hard-coded in PHP, JS, Blade, Flutter/Dart code shipped to clients, tests, seeders or `.env.example`.
- `.env` is listed in `.gitignore`. If the project is a git repo, check whether `.env` or secrets were ever committed: `git log --all --oneline -- .env` and a grep of history for the key names (read-only). A secret in history = Blocker (must be rotated, not just deleted).
- Private keys never in the frontend/mobile app (only a provider's public key, if the provider has one).

### 3.9 CSRF - Important
- The webhook/IPN route must be excluded from CSRF (otherwise the provider gets 419 and notifications are lost): `VerifyCsrfToken::$except` (Laravel <= 10), `bootstrap/app.php` `->withMiddleware(fn ($m) => $m->validateCsrfTokens(except: [...]))` (Laravel 11+), or the route lives in `routes/api.php`.
- The exclusion must cover **only** the notification route(s). Wildcards like `'*'`, `'api/*'` on web routes, or excluding the payment initiation route = Important.

### 3.10 HTTPS - Important
- Notification and return URLs given to the provider use `https://`.
- Outgoing HTTP calls do not disable TLS checks: `CURLOPT_SSL_VERIFYPEER => false/0`, `CURLOPT_SSL_VERIFYHOST => 0`, `Http::withoutVerifying()`, Guzzle `'verify' => false` = Blocker (keys can be intercepted).
- In production, `URL::forceScheme('https')` or `APP_URL=https://...` so generated `route()` URLs are https.

### 3.11 Logs - Important
- No logging of full requests/headers to the provider or from webhooks if they contain keys (`Log::info($request->all())`, `Log::debug($request->headers)`, `dd()`/`dump()` left in payment code).
- No API keys, webhook secrets, full phone numbers + names dumps, or card data in logs. Check `storage/logs/*.log` only if present, and mask anything found.

### 3.12 API errors and timeouts - Important
- Calls to the provider set a timeout (`Http::timeout()`, `CURLOPT_TIMEOUT`, Guzzle `timeout`). No timeout = Important.
- Non-2xx responses and network exceptions are handled: no unguarded `$response['token']`, no assumption that `json_decode` succeeded.
- A timeout on payment initiation must not leave the order in an undefined state, and must not create a second payment for the same order when the user retries (reuse or expire the previous one).
- The webhook handler answers quickly with 2xx after authenticating and recording; heavy work goes to a queue. Returning 5xx on a duplicate makes the provider retry forever.

### 3.13 Provider-specific checks
Run every check listed in the loaded reference file(s) ("Provider-specific checks" section).

## Step 4 - Report

Use exactly this structure (translated into the user's language):

```
<VERDICT LINE>

Provider(s): <name> (reference verified on YYYY-MM-DD) | <name>: no reference file
Scope: <files/dirs read>

Findings
1. [Blocker] <problem> -> <precise fix> (path/to/File.php:42)
2. [Important] ...
3. [Minor] ...

To confirm manually
- <what cannot be seen in code: provider account activated for production (for providers with a manual activation step, have the confirmation before setting a launch date), dashboard settings, webhook URL registered at the provider in live mode, keys rotated, IP allowlist, server clock, queue worker and scheduler running in production, etc.>
```

Verdict line rules:
- `NO-GO - N blocker(s)` if there is at least one Blocker (French: `NO-GO — 2 bloquants`).
- `GO with reservations - N important` if no Blocker but at least one Important (French: `GO avec réserves — N importants`).
- `GO` otherwise.

Finding rules:
- Sort by severity, then by file.
- Every finding has a file:line (or "missing: expected in <file>"). Each fix is concrete: name the function, the column, the middleware or the config key, and show a short code snippet when it helps. Do not apply it.
- Masked values only (see Hard rules).
- Do not pad: if a check passes, do not list it as a finding. You may end with one line listing the checks that passed.
