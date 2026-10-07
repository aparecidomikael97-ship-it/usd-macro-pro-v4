# AION Multi-Tool Saga + Cumulative Authority Budget V1

Status: staging hardening only. No provider, connector, network action,
production persistence, Core Freeze, worker arming or deploy is enabled here.

## Objective

Close two related execution risks:

1. partial failure across a multi-tool transaction;
2. authority accumulation, where many individually permitted actions silently
   add up to a larger effective capability.

This block extends the existing transactional outbox instead of creating a
parallel executor.

## Outbox binding

Saga intents carry all of:

- transaction_id;
- authority_budget_ref;
- risk_points;
- capability_class.

When authority_budget_ref is present, the outbox itself requires a cumulative
authority guard immediately before adapter.send.

If the guard is absent, fails, mismatches the transaction/budget ref, or exceeds
limits, the outbox transitions to BLOCKED_REAPPROVAL before the external
boundary. The adapter is not called.

## Cumulative authority ledger

Confirmed effects are recorded durably and idempotently by:

- owner / tenant / workspace;
- transaction_id;
- authority_budget_ref;
- policy_version;
- capability_class;
- action;
- risk_points;
- effect_ref;
- confirmation time;
- decision digest.

The guard checks both:

- per-transaction limits;
- rolling scope-window limits.

Limits include:

- effect count;
- risk points;
- capability diversity.

This prevents separate transactions from evading limits through repeated small
approvals.

CRITICAL capability class never passes this budget guard and remains a separate
human-owned flow.

The budget component does not itself authorize execution.

## Saga state machine

Forward transaction states include:

PLANNED -> RUNNING -> COMPLETED

and fail-closed branches:

- RECONCILIATION_REQUIRED
- FAILED
- COMPENSATION_REQUIRED
- COMPENSATING
- COMPENSATED
- MANUAL_INTERVENTION_REQUIRED

Each step is sequential and durably bound to its outbox idempotency key.

## Partial failure

If a later step fails:

- no previously confirmed effect -> saga can fail with no compensation;
- only reversible confirmed effects -> COMPENSATION_REQUIRED;
- any confirmed irreversible effect -> MANUAL_INTERVENTION_REQUIRED.

The coordinator never labels an irreversible effect as rolled back.

## Ambiguous / lost response

UNCERTAIN or SENT means the effect is not safe to assume absent.

The saga enters RECONCILIATION_REQUIRED.

While in this state:

- no next forward step is enqueued;
- no compensation is prepared;
- no blind resend occurs;
- no blind rollback occurs.

After the existing outbox reconciler confirms the real outcome, the saga may
continue from the reconciled durable state.

## Compensation

Compensation is not automatic.

Before compensation starts, all are required:

- saga state COMPENSATION_REQUIRED;
- explicit_human_approval is exactly true;
- approval_ref;
- reauth_ref.

Compensation runs in reverse order of confirmed forward effects.

Each compensation is itself a new transactional outbox intent and requires:

- authority/policy revalidation;
- transaction reauthentication;
- cumulative authority guard;
- idempotency/reconciliation semantics.

If compensation fails, the saga becomes MANUAL_INTERVENTION_REQUIRED.

If compensation outcome is uncertain, the saga returns to
RECONCILIATION_REQUIRED and no later compensation may proceed until the
ambiguous effect is reconciled.

## Rollback reserve

At saga creation, the worst-case transaction shape reserves budget for:

- all forward effects;
- compensation effects for all reversible steps;
- forward risk;
- compensation risk.

A saga that is known in advance to exceed the declared transaction budget,
including rollback capacity, is rejected before execution.

This avoids starting a transaction that is structurally impossible to
compensate inside its own declared authority envelope.

## Audit integrity

Saga transitions are appended to a hash-chained durable event journal:

- sequence;
- previous_hash;
- event_hash;
- event type;
- state;
- step key;
- detail digest;
- timestamp.

Rewriting an event breaks integrity_report.

## Red-team coverage

Tests cover:

- full multi-step success;
- second-step failure;
- third-step failure;
- reverse compensation order;
- explicit human compensation approval;
- compensation reauthentication;
- irreversible prior effect -> manual escalation;
- lost forward response -> reconciliation required;
- lost compensation response -> reconciliation required;
- compensation failure -> manual escalation;
- per-transaction cumulative authority exhaustion;
- rolling-window authority exhaustion across separate transactions;
- guard omitted at dispatch -> adapter never called;
- critical capability blocked;
- budget ledger idempotency and collision detection;
- policy/budget/scope mismatch;
- time-window expiry;
- saga event tamper detection;
- durable store reopen/recovery.

## Explicit non-goals

This contract does not claim generic distributed transactions across arbitrary
third-party systems.

A compensation is only valid where the specific external system provides a
real, tested compensating operation.

Irreversible effects, uncertain external truth and failed compensation remain
human escalation paths.

No real adapter is enabled by this block.
