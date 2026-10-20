# AION P0 — 30-day SMS provider key expiry and limits of local history

**Date:** 2026-10-20 · **Status:** OPEN EVIDENCE GAP, HARD NO-GO  
**Scope:** OneSignal `notifications#create` idempotency_key **30-day deduplication** is documented; no external message is sent and no provider secret/Account SID is used. The AION Outbox's deterministic local key and durable SQLite ledger are different protections.

## Threat model

A remote provider's finite key retention is not a permanent *terminal no-effect fence*. Specifically, after its 30-day record retention expires, submitting the same key may produce another notification, even if the original effect may have occurred. The AION must not permit automatic retries in an ambiguous state, whether before, during or after that window.

The source Outbox currently persists a deterministic per-intent+scope+payload+action+aggregate key and an `intent_ref` uniqueness check in SQLite. This protects an **intact** local state after a process restart: re-enqueue of identical intent returns `IDEMPOTENT`; changed payload/action/aggregate with reused intent is a **collision**; `UNCERTAIN` remains quarantined and holds downstream FIFO. Our time-shift tests probe 30, 31, 365 and 730 days.

**However, durable SQLite is not an independent provider witness.** If the original database is lost, replaced, restored to an older checkpoint, or a malicious actor deletes both the outbox and decision history, a new local store can recreate a `PENDING` intent bearing the same deterministic key. This is an **OPEN H0 external proof gap** even if the current code still blocks at `INDEPENDENT_PRODUCER_NOT_ENROLLED` before any network call. Never interpret a freshly rebuilt `PENDING` as proof of no earlier effect. **ZERO_AUTO_RESEND**.

## Required eventual security control

1. Independent producer enrollment bound to actual provider account, tenant, owner, current authorization, canonical action digest and protected key root; no adapter self-attestation.
2. Durable antirollback idempotency/intent tombstone and/or independently witnessed monotonic anchor that survives local database rollback/loss, with quarantine whenever historical state cannot be authenticated. Local backup restore alone is not a signed global fence.
3. Enforce immutable client intent digest with provider key and original request; reject same key with changed destination/body even though OneSignal's *first request wins* contract handles that case at its own API level.
4. Protect ambiguity **past any provider TTL**. After key expiry, only independently verified original committed effect or a provider-enforced terminal no-effect guarantee can resolve the state; otherwise manual reconciliation with no automatic resend.
5. Current Outbox/Saga producer gates remain **HARD NO-GO**, 32 historical Quality ERROR nonwaived, no implementation changes authorized here.

## Evidence in this isolated LAB

`tests/test_aion_p0_sms_provider_key_expiry_local_history_lab.py` contains **12 offline tests**. The loss-of-history test is deliberately a demonstration of the open gap — it checks that a completely new blank database can produce a new PENDING row; PASS of that test is not a security approval.

It uses UTC time shifts and fake recipient identifiers; **no provider clock/TTL is actually tested, no Twilio or OneSignal API is contacted and no real message is sent**. A passing LAB matrix is only proof of local observed behavior. No Quality complete or Security 365 reexecution is claimed. There is no independent signed evidence for actual provider at-most-once, terminal no-effect fencing or producer receipt.

**References:** [OneSignal Idempotent API Requests](https://documentation.onesignal.com/reference/idempotent-notification-requests), [OneSignal View Message](https://documentation.onesignal.com/reference/view-message), [Outbox historical issue #1329](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/issues/1329).

**Operational state:** Worker OFF, ZERO_AUTO_RESEND, HARD NO-GO, 0/6 P0 homologated, no merge/deploy/spend.
