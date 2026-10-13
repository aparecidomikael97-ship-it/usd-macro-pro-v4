# AION Execution Outbox V1 — staged contract

Status: **staging only**. No connector/provider/external adapter is enabled by this
contract.

## Why this exists

The previous execution model had idempotency at several local boundaries, but it
did not yet define the distributed-action semantics required before e-mail,
WhatsApp, payments, publishing or any financial side effect can be authorized.

This contract establishes the mechanics without enabling any external action.

## Core semantics

Every future external action must first become an immutable intent in the same
SQLite durability boundary used by the staged AION host.

The enqueue transaction writes:

1. a decision row;
2. the action intent/outbox row;
3. the deterministic idempotency key.

If either insert fails, both roll back.

The idempotency key is derived from:

- trusted owner/tenant/workspace scope;
- stable `intent_ref`;
- action;
- aggregate/resource key;
- canonical redacted payload digest.

Reusing the same `intent_ref` with a changed payload fails closed.

## State machine

The execution ledger uses:

- `PENDING`
- `RETRY`
- `CLAIMED`
- `UNCERTAIN`
- `SENT`
- `CONFIRMED`
- `REVOKED`
- `BLOCKED_REAPPROVAL`
- `FAILED`

Important invariant: once the external boundary might have been crossed, a lost
response becomes `UNCERTAIN`. It is **not** eligible for normal claim/retry.
The only next path is reconciliation.

## Claim and concurrency

A worker obtains a short lease under `BEGIN IMMEDIATE`.

- only one worker can claim a given intent;
- expired `CLAIMED` work may return to `RETRY`, because dispatch has not
  started yet;
- `UNCERTAIN` and `SENT` never blind-retry;
- actions for the same aggregate/resource are sequenced and later actions remain
  blocked until the earlier action is terminal.

## Authority at use time

Approval at enqueue time is not enough.

Immediately before adapter dispatch, the executor must revalidate:

- current actor identity;
- current tenant/workspace;
- current policy version;
- current authorization reference;
- `valid_until`;
- transaction-bound reauthentication reference when the intent requires it.

A revoked authority becomes `REVOKED`.
Policy/authorization drift, authority expiry or reauthentication mismatch becomes
`BLOCKED_REAPPROVAL`.

Memory or conversation context cannot satisfy this gate.

## Lost-response rule

Dispatch persists `UNCERTAIN` **before** crossing the adapter boundary.

Therefore a crash or timeout after that point cannot cause a blind resend after
restart. A future adapter must expose an idempotency-aware reconciliation path.

- found + confirmed -> `CONFIRMED` in local fixture semantics, effect ledger written once;
  **a real producer receipt and independently authenticated source remain
  mandatory before operational trust**;
- adapter-declared `authoritative_absence=true` **is not evidence of no effect**,
  even when the fake adapter knows the fixture did not send anything: keep
  `UNCERTAIN`/`SENT`, return `INDEPENDENT_ABSENCE_PROOF_REQUIRED`;
- an adapter response `accepted=false`, regardless of `retryable`, is not
  proof of no effect or no delayed effect after the pre-send UNCERTAIN commit:
  keep `UNCERTAIN` and the aggregate blocked;
- any ambiguity -> no automatic `RETRY`, terminal `FAILED`, escalation to
  compensation, or release of the next aggregate action solely from a callback;
- only an independently authenticated, causal no-effect receipt **and** a
  producer-enforced late-effect fence could justify a future recovery path.
  No such productive admission mechanism exists in this staging version.

The original synthetic tests modeled an adapter's self-declared absence as
authoritative. The A.20 lab candidate intentionally revokes that assumption;
separate compensation-engine tests still exercise their state machine via an
**explicit SQL fixture simulating external review**, never proof or an
available production API.

## Effect ledger

Confirmed external effects are keyed by the same idempotency key. A different
effect trying to claim the same key is an idempotency collision and fails closed.

## Tests

The staged red-team suite proves:

- exact enqueue replay is idempotent;
- changed payload under the same intent_ref is rejected;
- forced outbox insert failure also rolls back the decision row;
- eight workers racing produce one claim;
- revocation after approval but before dispatch causes zero adapter calls;
- policy-version drift forces reapproval;
- transaction reauthentication mismatch forces reapproval;
- expired authority causes zero adapter calls;
- lost response after a successful effect is reconciled without a second send;
- unverified adapter absence/rejection cannot authorize retry or release FIFO;
- external proof of no effect is still required, with no live verifier installed;
- per-resource ordering is enforced;
- expired pre-dispatch claims are recoverable;
- cross-tenant access fails closed;
- confirmed effects are recorded once.

## Still deliberately absent

This block does not activate:

- real e-mail/WhatsApp/payment/trading adapters;
- production action workers;
- network calls;
- production storage;
- saga/compensation for multi-tool plans;
- tenant encryption/key management;
- biometric/FIDO transaction confirmation implementation.

Those remain separate gates.


## V16-A.24 — temporary positive-admission hard stop (LAB candidate only)

The executable A.21 adversarial contracts in Draft #1236 proved that injected,
untrusted `adapter.send` and `adapter.reconcile` responses could set
`CONFIRMED` and populate `action_effects` even when no producer existed.

This staged A.24 child deliberately **does not provide any path for a callback
boolean, `effect_ref`, or a direct private `_confirm` call to certify an effect**.

- A post-send `accepted=true, confirmed=true` is kept `UNCERTAIN` and the
  scoped aggregate remains blocked, reporting `UNCERTAIN_PROOF_REQUIRED` and
  `ADAPTER_POSITIVE_EFFECT_UNVERIFIED`.
- An `adapter.reconcile(found=true, confirmed=true)` leaves a current
  `SENT` or `UNCERTAIN` untouched, reporting
  `INDEPENDENT_POSITIVE_PROOF_REQUIRED`. A stale observation is ignored.
- A direct call to `_confirm` raises
  `INDEPENDENT_PRODUCER_RECEIPT_NOT_ENROLLED`; no ledger row is added.
- The A.20 negative quarantine remains active. An unverified negative result
  never permits retry, FAILED, compensation or release of the next aggregate.

**Important compatibility cost:** tests and Saga fixture workflows that used a
fake adapter's `confirmed=true` as an effect may now correctly fail. They
must remain visible in CI as **legacy contract incompatibilities** until a
reviewed proof-admission mechanism and updated safety tests exist. Do not add
an allow-fixture-in-production flag, xfail/skip, trust a self-enrolled key or
weaken the new A.21 adversarial tests merely to force green.

A future real path needs producer-issued causal positive receipts,
independently enrolled issuer/pins/tenant+resource scope, challenge/nonce,
replay/revocation/freshness checks, causal readback and a separately retained
antirollback current-head. The producer must also furnish a terminal
fenced-no-effect proof before safe retry of ambiguous attempts. Neither path
exists in the A.24 staging candidate.

No external sender is enabled, and a red CI from legacy positive fixtures is
not evidence of a released system. Main, Core V1, Worker, AM12 and deployment
remain untouched; first install remains HARD NO-GO (20/20 blocked).
