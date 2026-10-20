# AION P0 LAB — SMS providers: OneSignal 30-day Create idempotency vs Twilio Classic/Bulk

**Date:** 2026-10-20. **Status:** PROVIDER EVIDENCE RESEARCH ONLY, HARD NO-GO.  
**Scope:** OneSignal `notifications#create` with SMS, Twilio Classic Messages and Twilio Bulk Messaging Beta. **NO production integration, no live provider traffic, no enrollment, no auto resend.**

## 1. What changed in this review

The previous [Twilio comparison](AION_P0_TWILIO_CLASSIC_BULK_CONTRACT_COMPARISON_20261020.md) established that the publicly reviewed Twilio Classic/Bulk *send* endpoints did not present an independently verified client-generated atomic create-idempotency contract. This is **not** a universal claim that Twilio has no idempotency in any product.

The official OneSignal [Idempotent API requests](https://documentation.onesignal.com/reference/idempotent-notification-requests) guide **does** document `idempotency_key` (UUID, per logical notification) for `notifications#create`, with **30 days** of retention and first-request-wins semantics. The source says retrying the same key returns the original API creation result without processing a second notification, even when submitted content differs. It **does not guarantee end-user delivery**. Vendor support correspondence was reviewed separately; **no private support message, account details or contact metadata is copied into the public repository**.

The AION must keep a separate local immutable mapping `{idempotency_key, canonical intent digest, destination and app/tenant scope}`: one key reused for a different destination/body must be rejected **locally**, even if OneSignal itself processes only the first request. Because the provider key may expire after 30 days, a forever-safe identical-key resend is **not** established.

The OneSignal Create contract **does not independently establish** (1) end-to-end carrier at-most-once SMS delivery, (2) a signed causal committed-effect receipt bound to AION issuer/nonce/epoch/scope, or (3) a provider-enforced terminal `NO_EFFECT_FENCED` that prevents future effects after a timeout/cancel. The [Cancel Message](https://documentation.onesignal.com/reference/cancel-message) operation documents stopping scheduled/outgoing messages but is not proof of a universal terminal fence for already transmitting downstream effects.

**Important**: OneSignal supports connecting a customer's Twilio SMS account as an upstream/downstream service configuration; OneSignal `notifications#create` protection is **not** proof that Twilio independently enforces the same key/TTL or has a cryptographic witness. Never inherit contracts across APIs.

## 2. Side-by-side constraints

| Control | OneSignal Create notification SMS | Twilio Classic Messages | Twilio Bulk Beta |
| --- | --- | --- | --- |
| Client-generated create idempotency key | **Documented** `idempotency_key` | Not established for this POST | Not established for this POST |
| Deduplication window | **30 days** | Not established | Not established |
| Behavior after lost create response | Provider documents same-key retry within valid window | SID may be unknown; list read only | `operationId` may be unknown after 202 lost |
| Changed payload under same key | Only first request processed; AION must **deny local mismatch** | No comparable contract established | No comparable contract established |
| After dedupe expiry | Reusing key may create new notification | No comparison possible | No comparison possible |
| End-to-end carrier exactly-once | **Not proved** | **Not proved** | **Not proved** |
| AION independent `COMMITTED_EFFECT` receipt | **Not proved** | **Not proved** | **Not proved** |
| Terminal `NO_EFFECT_FENCED` | **Not proved** | **Not proved** | **Not proved** |
| Ability to perform AION automatic retry today | **DENIED** | **DENIED** | **DENIED** |

## 3. Policy for current AION

- An `allowed=True` budget preflight, OneSignal `idempotency_key` and Twilio `Message SID`/`operationId` **never** grant producer execution authority on their own.
- The present Outbox refuses preadapter sends without independent producer enrollment; Saga refuses local SQL positive receipt and local negative `FAILED` as terminal proof.
- **Even for OneSignal**, do not implement retry on timeout at this point. The vendor may describe a safe *API-layer* same-key retry, but AION still lacks independent producer root and required outcome/no-effect fences. Any future controlled exception needs explicit Owner authorization, provider-specific proof, bounded TTL, exact intent digest, and full H0 approval.
- Do not use a provider's `429 Retry-After` or generic SDK retry default to override `ZERO_AUTO_RESEND`.
- Operationally useful next action: request engineering confirmation of concurrent same-key creates, error/timeout boundary, BYO Twilio carrier effects, key scope and TTL, receipt authenticity, no-effect terminal capability, costs and Brazil regulatory prerequisites. A **Gmail reply draft exists for review** but no message was sent by this LAB.
- Avoid uncontrolled cost exposure: no SMS send, number rental, paid plan, provider account or subscription was requested or activated.

## 4. Verification and limits

- `AION_P0_SMS_PROVIDER_EVIDENCE_COMPARISON_20261020.json`: **18 scenarios**, 11 OneSignal, 3 Twilio Classic and 4 Twilio Bulk, all with `auto_resend_authorized=false`, `terminal_no_effect_fence_proven=false` and `canonical_quality_case_waived=false`.
- `tests/test_aion_p0_sms_provider_comparison_lab.py`: **11 cases** to preserve OneSignal's 30-day positive deduplication distinction without mistaking it for AION authority, plus real Outbox/Saga denial tests.
- These are **specification and negative boundary tests**, not a cryptographic test of OneSignal, Twilio, downstream carrier or any real account. No network, webhook or vendor signature was verified.
- The canonical Quality baseline is still **51 FAIL / 34 ERROR**, of which **32 Outbox/Saga errors are OPEN_NOT_WAIVED (23 producer enrollment, 8 committed-effect receipt, 1 terminal no-effect fence)**. No P0 was homologated.
- **HARD NO-GO, 0/6 P0 homologated, Worker OFF, ZERO_AUTO_RESEND, no merge/deploy/spend.**

## Public documentation

- OneSignal idempotency: https://documentation.onesignal.com/reference/idempotent-notification-requests
- OneSignal cancellation: https://documentation.onesignal.com/reference/cancel-message
- OneSignal message details: https://documentation.onesignal.com/reference/view-message
- OneSignal SMS setup: https://documentation.onesignal.com/docs/en/sms-setup
- Twilio Classic Messages: https://www.twilio.com/docs/messaging/api/message-resource
- Twilio Bulk Messages: https://www.twilio.com/docs/bulk-messaging/api/message-resource
