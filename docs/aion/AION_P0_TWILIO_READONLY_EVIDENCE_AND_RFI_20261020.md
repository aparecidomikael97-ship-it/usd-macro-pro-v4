# AION P0 LAB — Twilio Programmable Messaging: read-only evidence vs authority

**Date:** 2026-10-20.  
**Scope:** SMS and WhatsApp *through Twilio Programmable Messaging Messages resource*; this is not the Meta WhatsApp Cloud API contract or the newer Twilio Bulk Messaging API.  
**Baseline:** parent [PR Draft #1336](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/pull/1336) with **32 historical Quality errors still OPEN_NOT_WAIVED**: 23 producer enrollment + 8 causal effect receipt + 1 terminal no-effect fence.  
**Verdict:** **GO-LAB for offline specification only; NO-GO for producer enrollment, actual sends, retry after unknown response or integration.**

## Verified public provider behavior (20 October 2026)

| Provider mechanism | What is documented | What it does **not** prove for AION |
|---|---|---|
| `POST /Messages.json` | Creates outbound Message resource, with `Message SID` returned on successful response | No client-generated atomic CREATE idempotency key and persistent producer terminal fence were established from this endpoint's documented parameters; a lost response cannot justify a second POST |
| `GET /Messages/{Sid}.json` | Read by **known** Message SID, with Account SID and delivery lifecycle fields | SID/status alone is not a provider-signed, independently witnessed receipt tying the original AION intent, payload digest and epoch |
| `GET /Messages.json` | Read list, filter by To, From and DateSent; paginate | Zero entries is **not** `NO_EFFECT_FENCED`; a candidate entry may belong to a parallel or repeated request, and multiple entries are ambiguous |
| Status lifecycle | `queued`, `accepted`, `scheduled`, `sending`, `sent`, `delivered`, `undelivered`, `failed`, `read` and `canceled` have provider-specific meanings | `sent` is upstream carrier acceptance, not necessarily recipient delivery; even `delivered`/ `read` is not a complete AION independent causal attestation; `failed`/`undelivered` don't fence every unknown POST |
| Status callbacks | Reports status transitions; initial creation status has **no** callback | Missing webhook is not no-effect evidence, and callback data must be validated rather than trusting caller-supplied booleans |
| `X-Twilio-Signature` | Official SDK signature validation authenticates HTTP webhook requests using the real account secret and request URL/parameters | Authentication of one status update alone cannot prove the original AION authorized intent, exact request idempotency, independent producer witness, or late-effect immunity |
| Cancel future scheduled Message | Update identified scheduled Message `Status=canceled` **before** `SendAt` | **Not** an unrestricted cancel-after-queue/send API or universal terminal no-effect fence for unknown parallel attempts |
| Duplicate deliveries | Twilio recommends diagnosing duplicates via distinct Message SIDs in message logs | A second application POST after a timeout is not automatically safe |

**Official sources read:**  
- Message resource / Create / Fetch / List / Status definitions: https://www.twilio.com/docs/messaging/api/message-resource  
- Lifecycle + no initial callback: https://www.twilio.com/docs/messaging/guides/outbound-message-status-in-status-callbacks  
- Polling vs callbacks: https://www.twilio.com/docs/messaging/guides/outbound-message-logging  
- Scheduled cancellation limits: https://www.twilio.com/docs/messaging/features/message-scheduling  
- HMAC signature verification: https://www.twilio.com/docs/usage/webhooks/webhooks-security  
- Duplicate message troubleshooting: https://help.twilio.com/articles/223181768-Why-did-the-person-I-sent-a-message-to-get-duplicate-messages-

**Evidence nuance:** "Not established in reviewed documentation" does **not** mean Twilio has explicitly denied every capability across all products/enterprise contracts. The user previously received a support answer indicating the Messages API does not support idempotency tokens; this round did **not** reconfirm any private account-specific entitlement or contractual guarantee. **Nothing from the docs is enrolled or trusted as proof**.

## AION interpretation: safe-to-observe ≠ safe-to-act

1. When CREATE acknowledgement is lost, preserve `UNCERTAIN`, **do not POST again**. Use a **separately approved read-only** check by known SID if available, or list filtering where no SID exists, with an operator checking for same sender, recipient, timeframe and content correlation. No lookup was performed in this LAB.
2. A list returning no rows, multiple rows, a failed delivery or a canceled scheduled Message **does not certify** that a different queued or delayed request cannot execute later.
3. A `sent`, `delivered`, `read`, or webhook `confirmed=true` result, even from authenticated Twilio infrastructure, is **provider observation only** unless the AION independent enrollment, exact causal binding, replay/epoch and independent witness gates are separately satisfied.
4. Outbox remains `BLOCKED_PRODUCER`, `SENT` or `UNCERTAIN` according to the internal stage. Saga remains `RECONCILIATION_REQUIRED` when appropriate. No manual `CONFIRMED` or `FAILED` injection is valid authentication. Do not unlock the FIFO or schedule retries.
5. Privacy/LGPD: provider logs contain recipient and sender identifiers, and Message content; handle in approved scope with retention and data minimization. Do not use real phone numbers or message bodies in LAB fixtures.
6. **ZERO_AUTO_RESEND** until a real, separately authenticated idempotency/terminal no-effect protocol has been demonstrated and approved; absent that, manual supervised resolution remains the default.

## Technical vendor RFI to resolve the actual dependency

Request a **written, operation-specific** response from Twilio before proposing any LIVE/H0 enrollment:

1. For `POST /2010-04-01/Accounts/{AccountSid}/Messages.json`, is there an atomic *caller-chosen idempotency key* supported for creating one Message under a single account? Which request header/body field, lifetime, payload-consistency rules and concurrency semantics?
2. If a client times out after submitting POST but before learning the Message SID, how does Twilio distinguish **not created** from **created but not yet discoverable** without issuing a second POST?
3. Does a read-only API search provide an **authoritative terminal no-create/no-send fence**, preventing all queued, delayed or parallel attempts under the same request/account? If not, confirm it explicitly.
4. Can Twilio guarantee cancellation of an already queued/sending (not merely future scheduled) Message by original caller key? When is cancellation durable and what about late carrier delivery?
5. Can Twilio issue signed provider-origin **causal committed-effect** evidence binding a client-chosen intent ID, exact canonical content digest, Account SID, Message SID, timing and replay epoch — beyond status callbacks?
6. For SMS vs WhatsApp through Twilio, identify differences among `sent`, `delivered`, `read`, `failed` and `undelivered` and the earliest reliable event for your definition of "effect".
7. Are there independent monotonic current-head / antirollback witnesses and issuer root rotation/revocation guarantees? What independent evidence can a third party verify without trusting the application's own database?
8. What are message log retention, pagination/consistency delays, webhook retries, duplicate delivery semantics and cancellation windows? Provide versioned terms/API docs and applicable account/region details.

**No outbound support message has been sent.** This is an RFI specification only; prior support guidance is not treated as a cryptographically verifiable operational commitment.

## Deliverables and verification

- [22-case provider observation matrix](AION_P0_TWILIO_READONLY_OBSERVATION_MATRIX_20261020.json) — 22 lifecycle, lookup, missing-result, callback, cancellation, duplicate and foreign-account cases; **all** carry `effect_execution_authorized=false`, `safe_automatic_resend=false`, `independently_authenticated_committed_effect_receipt=false`, `terminal_no_effect_fence_verified=false`, `original_quality_case_closed=false`.
- `tests/test_aion_p0_twilio_readonly_observation_lab.py` — matrix consistency and real AION `Outbox.dispatch_claimed`, `reconcile`, `Saga.sync_forward_outcome` fail-closed regressions; test-only Twilio-looking SIDs and self-asserted signatures are explicitly untrusted.
- Branch-scoped, read-only GitHub Actions Ubuntu + Windows, no Twilio SDK/accounts/secrets/messaging APIs called. These tests are deliberately **negative boundary tests**, not verification of a real Twilio deployment.

**HARD NO-GO | 0/6 P0 homologados | 32 historical Outbox/Saga ERROR OPEN_NOT_WAIVED | Worker OFF | ZERO_AUTO_RESEND | no merge, deploy or additional spend.**
