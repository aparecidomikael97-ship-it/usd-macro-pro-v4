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

- found + confirmed -> `CONFIRMED`, effect ledger written once;
- authoritative absence -> policy is revalidated again, then the intent may
  return to `RETRY`;
- ambiguous result -> remains uncertain.

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
- authoritative proof of no effect is required before retry;
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
