# Changelog

## 0.5.0 — 2026-10-27

### Breaking
- `WebhookHandler` now requires your signing secret: `WebhookHandler(signing_secret)`. Copy it from the dashboard (Webhooks → Signing secret). The optional `ipn_secret` argument is gone, and a handler can no longer skip signature verification.
- Signatures are read from `X-Sagapay-Merchant-Signature`, keyed with your own signing secret. The old `X-Sagapay-Signature` header, keyed with a secret shared by every merchant, is retired: SagaPay no longer sends it and this SDK no longer accepts it.
- `process_webhook()` takes the raw body (str or bytes) and a signature; it no longer accepts a parsed dict. Use `parse_payload()` to parse a body you have already verified.

### Security
- `verify_signature()` compares the decoded digest, accepts upper-case hex, and returns `False` for a malformed digest.
- Requests no longer follow redirects. requests resends custom headers on a redirect, so following one could send your `x-api-key` and `x-api-secret` to another host.

### Added
- `is_ipn_fresh(webhook, max_age_seconds=86400)` and `WebhookHandler(..., max_age_seconds=...)` reject notifications whose `timestamp` is too old or more than 5 minutes in the future. Use them alongside processing each `id` only once.
- `SIGNATURE_HEADER`, `DEFAULT_MAX_AGE_SECONDS` and `parse_payload()`.
- `create_withdrawal(params, idempotency_key=...)` sends an `Idempotency-Key` header, so a retried request cannot create a second withdrawal.
- `WebhookPayload` has the `asset` and `contract_address` fields that notifications carry.
