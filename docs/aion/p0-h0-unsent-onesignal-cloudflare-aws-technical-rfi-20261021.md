# AION P0/H0 — Vendor technical RFIs ready for review (NOT SENT)

**Prepared:** 2026-10-21 · **Scope:** offline engineering questionnaire, no customer data, API requests, credentials, account setup, purchasing, or message sends.
**Governance:** HARD NO-GO, 0/6 P0 homologated, Worker OFF, ZERO_AUTO_RESEND.
**Previous work reused:** `docs/aion/AION_P0_SMS_ONESIGNAL_VS_TWILIO_EVIDENCE_RFI_20261020.md`, `docs/aion/p0-h0-provider-vs-independent-custodian-evaluation-20261021.md`, PRs #1406/#1407. Prior contact history is not asserted: **these drafts have not been sent in this round**.

## Email draft 1 — OneSignal engineering/support (producer of SMS)

**Subject:** Technical RFI — OneSignal SMS notification create idempotency, lost response, and terminal outcome guarantees

Hello OneSignal Engineering / Technical Support,

We are evaluating a possible *future* integration of **OneSignal SMS** using the REST `notifications#create` operation, not requesting production activation or a sales commitment. We are designing a fail-closed system that cannot automatically retry a first attempt if its result is uncertain. We reviewed your public idempotency documentation, which describes UUID `idempotency_key` retention for 30 days and at-most-once notification *creation/processing*; we understand that this is **not a guarantee of SMS delivery**.

Could you provide **written, endpoint-specific** answers, links to versioned documentation or contract language, and a clear **“not supported”** where applicable?

**P-01. API and transport boundary.** Does the documented `idempotency_key` apply without qualification to *both* OneSignal-managed SMS and BYO Twilio integrations through `notifications#create` with SMS target? Identify exact API endpoint, app/account scope, channel, and any unsupported configurations.

**P-02. Key scope and expiry.** Is deduplication keyed by app, account, organization, payload, destination, or some combination? Confirm 30-day expiration start point, deletion semantics, possible early eviction, and whether an old key can create a new notification after expiry.

**P-03. Concurrency and different payloads.** When two identical-key create requests reach different regions concurrently, is the outcome atomic? If the key is reused with a different body, recipient, channel or tenant, is there a conflict response, or does the first request silently win?

**P-04. Lost acknowledgment without message ID.** If the initial HTTP response is lost after the request is received, is there a **strictly read-only endpoint to query by the original `idempotency_key`** and obtain an authenticated, current resource ID or an inconclusive result? Please provide URI, consistency model, retention and negative-result semantics. We will **not** issue a duplicate `POST` just to look up an ID without a separately approved protocol.

**P-05. After key retention expires.** Is there a way to **irreversibly fence** the logical operation so that a late or repeated create cannot create a second SMS after 30 days? If not, please confirm explicitly.

**P-06. Queued/in-flight cancellation.** Can cancellation ensure no future submission or delivery if the message has been accepted, queued, sent downstream or is in-flight? Which stages can still produce late carrier events after a “canceled” response?

**P-07. Causal outcome and receipts.** What events prove message accepted by OneSignal, submission to the underlying SMS provider, acceptance by a carrier, and terminal recipient delivery? Which event is durable and traceable to the *specific first* create? Is a provider-issued, third-party-verifiable signed receipt available?

**P-08. Authentication and replay.** For each webhook or readback API, how is origin authenticated, how is a one-time nonce/request digest bound to the specific account/app/message, how are keys rotated/revoked and repeated/out-of-order events detected?

**P-09. No-effect proof.** Is there any operator-verifiable terminal `NO_EFFECT_FENCED` outcome guaranteeing that **no SMS was created/submitted/delivered and none can occur later** for that logical request? If unsupported, can support state that no such guarantee exists? We do **not** treat timeout, 404, an empty list, “failed” status, or cancellation alone as such proof.

**P-10. Downstream Twilio/carrier boundary.** If OneSignal SMS uses a downstream provider or a customer’s own Twilio account, which idempotency/uniqueness and late-effect guarantees survive this boundary, if any? Are duplicate carrier submissions/receipts possible even when notification creation is deduplicated?

**P-11. Recovery and audit history.** For a response lost before a message ID is known, what is the *read-only* recovery path? Which logs, sequence/high-water, immutable audit traces and retention periods are available to an independently authorized auditor? What does “no record found” actually mean?

**P-12. SDK and HTTP retry.** Do any client SDKs, proxies, `429/5xx` handlers or carrier integrations automatically retry creates without explicit customer consent? How can retries be completely disabled or externally fenced?

**P-13. Brazil, compliance and price.** For low-volume business SMS to Brazil, what sender registration, consent/LGPD, sender-ID/number requirements, retention, region, carrier/route, monthly fixed fees, and per-SMS/per-segment prices apply? Are test/sandbox calls charged or capable of reaching real recipients?

**P-14. Verification logistics.** Can you share official versioned API documentation, engineering review/security contacts and a **no-send/no-charge** procedure to review these guarantees? We will seek separate authorization before any account, number, sandbox transaction, live SMS or paid service is created.

We do not need access credentials or recipient information in your reply. A response of “not provided by this API” is useful and preferable to an inferred guarantee.

Thank you.

AtlasQuant / AION engineering (research only)

---

## Email draft 2 — Cloudflare Durable Objects engineering/security (separate custodian)

**Subject:** Technical RFI — Durable Objects SQLite as independently administered monotonic first-attempt ledger

Hello Cloudflare Engineering / Security / Developer Support,

We are assessing **SQLite-backed Durable Objects** as a possible *independently administered custody service* for a future fail-closed automation system. We have **not deployed, provisioned, or connected** a custody service. We reviewed your transactional/strongly consistent SQLite storage, 30-day point-in-time recovery (PITR) API, and Free/Paid limits. We need to distinguish **transactional storage** from an actual **tamper-resistant independent witness**.

Please answer the following, marking unsupported controls explicitly and supplying versioned references or architectural requirements.

**C-01. Independent administration.** Can we isolate the custodian in a *separate Cloudflare account*, with no deploy, DNS, API-token, billing, restore or delete privilege given to the AION host/app owner? Which roles and least-privilege API tokens allow only `reserve` and authenticated readback?

**C-02. Atomic reservation.** Can a single Durable Object implement atomic check-and-set for `(tenant, intent digest, nonce, epoch)` and reject concurrent, conflicting first attempts with a durable monotonic sequence? Identify transaction and storage durability semantics, including faults during execution.

**C-03. Acknowledgment loss/readback.** If the caller loses the acknowledgment of a successful reservation, can an independent reader retrieve an authoritative latest state without creating a second reservation? What do timeout, 404, failover and inconsistent clocks mean? Are read-your-writes and latest confirmed head guaranteed for this single object and under what conditions?

**C-04. PITR and malicious rollback.** Because SQLite Durable Objects expose **point-in-time restore**, what happens to stored sequence/head when an authorized administrator restores a 30-day-old snapshot or deletes a namespace/object? Is there a documented way to prevent, restrict, or independently detect such rollback with a separate immutable witness? Please distinguish platform default from application controls we must design.

**C-05. Independent signature.** Does the platform natively issue third-party-verifiable signatures or externally witnessed attestations over `intent/nonce/seq/head`? If not, confirm the need for a separate KMS/HSM/issuer with independently enrolled public keys and key rotation/revocation.

**C-06. Append-only audit.** Are immutable, exportable and separately owned audit logs available for reserve, readback, administrative restore/delete, key change, namespace migration, and deployment? What retention and tamper-resistance actually apply?

**C-07. Restore and split-brain experiments.** What is the documented behavior across Durable Object eviction/restart, failover, concurrent callers, object migration and multiple regions? What practical read-only tests could reveal stale heads, replay and lost acknowledgments without live external effects?

**C-08. Data boundaries.** Can the custodian store **only hashes, nonces, scopes and sequence**, excluding SMS bodies, recipient phone numbers and other personally identifiable information? What geographic/data-processing, deletion/retention and DPA/GDPR/LGPD arrangements exist for this metadata?

**C-09. Failure handling.** Is there any case in which the service reports success before the durable commit or a stale successful response is returned after restore? Please explain how a third-party verifier can establish freshness under your public API guarantees.

**C-10. Cost and quota.** Please confirm current SQLite-backed Durable Objects Free tier for **requests, CPU duration, rows read/written and data stored**, including what happens on quota exhaustion and whether any operation can incur charges without an explicit paid-plan upgrade. Describe Paid pricing and hard budget alerts/limits.

**C-11. Threat-model declaration.** If an account administrator with privileged restore/delete access colludes with an application operator, can Cloudflare alone prove a monotonically increasing head has **never** been rolled back? If not, please state which trust boundary a third witness must satisfy.

**C-12. Independent onboarding.** What minimal **nonproduction, zero-send, no-charge** validation is possible to review these contracts before provisioning? We will seek separate owner authorization before opening accounts, deploying Workers/Durable Objects or spending.

We do not ask Cloudflare to attest an SMS producer's delivery or non-delivery; that is a **separate producer obligation**. Written answers that a given feature is unsupported are welcome.

Thank you.

AtlasQuant / AION engineering (research only)

---

## Follow-up / alternative RFI — AWS DynamoDB (DO NOT SEND unless alternative selected)

**Subject:** Architectural question — conditional-write independent high-water custodian (DynamoDB)

1. **A-01:** For a single-region DynamoDB table, which `ConditionExpression` patterns guarantee a single durable reservation on concurrent requests keyed by intent/nonce and monotonic sequence? Provide documented boundaries and transactional examples.
2. **A-02:** Does `GetItem(ConsistentRead=true)` always reflect successful writes to a base table in that region, and what changes for GSIs, streams, global tables, replicas and PITR restore?
3. **A-03:** What least-privilege IAM and separate AWS-account roles allow the AION application to reserve/read but **not** update historical heads, delete, restore, alter keys or logs?
4. **A-04:** How can restores and malicious account-administrator rollback be independently detected, given that DynamoDB itself is not an external signed monotonic witness?
5. **A-05:** What signed or externally anchored append-only audit/proof scheme could bind `intent, nonce, epoch, seq, head` with independently verified issuer and key rotation? If not a native service guarantee, please say so.
6. **A-06:** What are the minimum and worst-case charges for conditional writes including failures, strong readback, auditing, logs/exports, KMS and restore? Does the requested design fit any Free tier without assuming **R$0**?
7. **A-07:** Which regions, metadata-only retention/data protection and IAM logs would be recommended for a Brazil-based application requiring minimal PII?
8. **A-08:** Is there a no-resource/no-charge document-only review before a separate-account technical pilot? Any real account/action requires explicit approval.

---

## Handling replies, evidence and next action

1. Store **only public/approved excerpts or links** in GitHub; keep private vendor correspondence, credentials, customer identifiers and phone numbers in appropriate private records, not a public PR.
2. Each question has an independent answer status (`UNANSWERED`, `ANSWERED_UNVERIFIED`, `NOT_SUPPORTED`, `NEEDS_CLARIFICATION`), with a dated reference to supplier identity and exact operation/version. A source-less “yes”, unsigned JSON or user-created signature is **never an authenticated external proof**.
3. Vendor reply can narrow options, never set `producer_enrolled`, `owner_authenticated`, `causal_receipt_verified` or `no_effect_fenced` by itself. A support answer of “unsupported” keeps that technical path blocked; unknown answers remain UNKNOWN/BLOCKED.
4. **Before any live test**: separate administrative domains, independently enroll issuer keys and head/nonce, approve costs, consent and risk, define first reservation plus rollback/late-event tests, and close every P0 through independent review.
5. The two emails here are **drafts not sent**. They do not represent commitments from OneSignal, Cloudflare or AWS.

### Public sources checked 2026-10-21
- OneSignal idempotency: https://documentation.onesignal.com/reference/idempotent-notification-requests
- OneSignal cancel: https://documentation.onesignal.com/reference/cancel-message
- OneSignal read by notification ID: https://documentation.onesignal.com/reference/view-message
- OneSignal SMS: https://documentation.onesignal.com/docs/en/sms-setup
- Cloudflare SQLite/PITR: https://developers.cloudflare.com/durable-objects/api/sqlite-storage-api/
- Cloudflare Free/Paid pricing: https://developers.cloudflare.com/durable-objects/platform/pricing/
- AWS DynamoDB read consistency: https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/HowItWorks.ReadConsistency.html

**No external inquiry or action was submitted in this PR.**
