# AION V2 — one-shot paid-dispatch attempt and UNKNOWN_OUTCOME reference

**Date:** 2026-10-09. **Base:** Draft #1132 on #1131 → #1130 → #1129 → #1128 → #1127 → #1126 → #1125 and predecessors.
**Security verdict: NO-GO. This is an inert local SQLite reference, NOT an API gateway.**

## Risk

A signed V2 intent and locally held maximum signed micro-USD amount are NOT proof a paid HTTP call has or has not already run. If the provider processes a request and the socket times out or the process dies before receiving a response, the client MUST assume **UNKNOWN_OUTCOME** and MUST NOT automatically resend the request or re-authorize its signature, even when no answer was stored.

At-most-once client attempt under honest, unrestored storage is the objective. Exactly-once external provider processing is impossible to guarantee from a single SQLite transaction, particularly without provider-supported idempotency, a cross-provider receipt or secure reconciliation. There is no claim that an exception or timeout means the provider did not bill.

## Code

`atlasquant_aion_v2_one_shot_unknown_outcome_journal_reference.py` is a local-only synthetic SQLite WAL + `synchronous=FULL` reference. It persists exact full immutable metadata of a **hypothetical** signed request: owner/tenant/workspace/conversation/message, nonce, V2 signed-intent hash, fully resolved provider request hash, BOTH signed witness head receipt digests, latest four-key roster digest, policy generation, period and signed maximum cost. **It never verifies actual cryptographic trust** in these caller-provided digests; #1125–#1132 are not connected as a production authority chain.

Operations:

1. `prepare_reference_only(intent)`: within `BEGIN IMMEDIATE`, allocate a unique `PREPARED` record; exact nonce, signed intent, entire intent digest and scoped conversation/message must not be rebound or reused.
2. `claim_reference_only(intent=...)`: commit an immutable transition `PREPARED → DISPATCH_CLAIMED` **before** any potential HTTP send in a future architecture. The return `LOCAL_REFERENCE_CLAIM_RECORDED_UNTRUSTED` is NOT actual dispatch authorization. Repeated claims return `REPLAY_BLOCKED_NO_SECOND_DISPATCH`.
3. `read_reference_only`: a claimed, still unresolved record is displayed as **UNKNOWN after crash/restart**. Never infer `NEVER_SENT` merely because the client sees no response.
4. `mark_unknown_reference_only`: append `DISPATCH_CLAIMED → UNKNOWN_OUTCOME`; idempotent repeats remain blocked. `cancel_never_claimed_reference_only` is permitted only from `PREPARED` and burns the nonce permanently; **never** cancel after claim.
5. `append_evidence_digest_reference_only`: store an opaque incident/evidence hash without treating it as an authenticated provider receipt, cost settlement or retry approval. Evidence may be noted while CLAIMED/UNKNOWN but cannot authorize payment.
6. `local_snapshot_reference_only`: read-only SHA-256 of full local journal for future external witness design; it provides **no** rollback resistance without separately authenticated, monotonic external anchoring.

The SQLite config and all intent records are verified on each operation for strict version, scope, digest, monotonic local contiguous sequence, state transition shape, unique nonce/message/signed-intent hash and durable history; unexpected partial database schemas, missing config or changed config are rejected, never automatically reinitialized.

## Crash and adversarial table

| Simulated observation | Reference verdict |
|---|---|
| Lost reply or crash after persisted claim | `DISPATCH_CLAIMED` remains; on restart interpreted conservatively as UNKNOWN; retry blocked |
| First 12 parallel claim attempts against same SQLite record | exactly one local claim; remaining returns block |
| Two different scoped messages use the same signed V2 digest/nonce | blocks second registration |
| Prepared-only attempt is explicitly cancelled | nonce burned forever; no later claim |
| After claim, someone asserts "never sent" | cancellation blocked |
| Same nonce used with a changed model request / witness / roster digest / amount | blocked |
| SQL trigger fails during claim transaction | no partial claim; rollback; state remains PREPARED |
| Local SQLite intent/sequence is altered | BLOCK on read/claim |
| **Privileged operator restores older journal file** | prior PREPARED state may appear again and claim may succeed in reference — explicit **negative control** proving local-only antirollback is NOT sufficient |
| Third-party evidence hash received | stored as **untrusted observation only**, not confirmed settlement |

## Production admission gates, NOT completed

- A real trusted HUMAN_OWNER key enrollment and signed full-request authorization; four roles with protected generation and cumulative revocation (#1131–#1132).
- Two independently authenticated monotonic witness heads protecting **the dispatch journal's own sequence and digest**, not just the signed V2 hold ledger. A legitimate rollback/corruption/recovery mismatch must BLOCK.
- A production dispatch-claim receipt in a protected external trust domain that is durably committed before any possible network attempt, with globally unique provider idempotency key when supported, fencing token, explicit lease semantics and protection against parallel workers, crash after claim and unknown provider response.
- Vendor-specific reconciliation of UNKNOWN_OUTCOME with provable provider-side request ID/billing receipt, separate authorization to retry (if ever) and no silent double charges. A staged negative response / HTTP timeout is NOT proof provider did not execute.
- Cross-DB/Cloud transactions not atomic by default. Real budget policy pricing/FX, actual spend limits, full HTTP request digest, logs/retention/LGPD and alert escalation require deliberate approval.
- Physical owner ceremony, credential and independent signing keys, risk budget (R$200/month **across all infrastructure**), account provisioning, Windows device installation and any merge/deploy remain out of scope and require explicit authorization.

**All actual authorization booleans always FALSE:** owner presence/trust, witness and roster freshness, provider authorization, real spend, actual cost, network invocation, installer and safe-to-resume. This reference performs **zero API calls**, does not generate or use signing keys, bills nothing, and cannot be wired to an execution gateway as-is.

Core V1/`main` unchanged. No merge, deploy or computer access.
