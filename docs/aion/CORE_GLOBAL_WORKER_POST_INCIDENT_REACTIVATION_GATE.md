# AION Global Worker Post-Incident Reactivation Safety Gate V1

## Purpose

This block adds a fail-closed safety gate between **incident closure** and any
future Global Worker activation.

A durable incident closure does not mean the Worker may be reactivated.

If durable Global Worker incident history exists, an activation plan is now
blocked unless the post-incident safety gate is green.

## Core truth rule

`REACTIVATION_GATE_READY` means only:

> current read-only evidence has no post-incident blocker for continuing the
> activation ceremony.

It does **not** mean:

- feature flag enabled;
- Worker reactivated;
- activation authorized by the gate;
- heartbeat/tick proven;
- trading enabled.

The gate always keeps:

- `reactivation_authorized=false`;
- `automatic_reactivation=false`;
- `feature_flag_modified=false`;
- `runtime_modified=false`;
- `global_worker_modified=false`;
- `real_trading_enabled=false`;
- `executes_action=false`.

## When the gate is required

The gate is mandatory when the confirmed shared runtime Checkpoint contains one
or more valid durable Global Worker closure records.

If there is no durable incident history:

`REACTIVATION_GATE_NOT_REQUIRED`

The legacy first-activation flow still uses all existing ARMED, readiness,
feature-flag, ADMIN, Guardian and confirmation protections.

## Evidence required after an incident

When durable history exists, the gate requires:

1. runtime status = `CONFIRMED`;
2. valid durable closure ledger;
3. Incident Center Global Worker reconciliation present;
4. reconciliation not fail-open;
5. durable history state = `CONFIRMED`;
6. reconciled durable record count equals the runtime ledger count;
7. no active Global Worker incident;
8. latest durable closure record appears in
   `closed_incidents` as `CLOSED_HUMAN_VERIFIED`;
9. activation readiness = `PASS / READY_FOR_FLAG_ENABLE`;
10. readiness has no blockers;
11. authoritative feature flag = `UNSET` or `DISABLED`;
12. flag is explicitly safe for arming persistence.

## Blocking incident states

Any active Global Worker incident blocks the gate.

In particular:

- `OPEN`;
- `REOPENED`;
- `OPEN_NEW_AFTER_CLOSURE`;
- fail-open reconciliation;
- unresolved/unverified closure evidence.

Historical closure cannot override a newer active incident.

## Short-lived evidence

A green gate has a short TTL.

Default:

`300 seconds`

Allowed range:

`120–600 seconds`

The gate binds:

- runtime SHA;
- checkpoint digest;
- closure ledger digest;
- latest closure record id;
- reconciliation state/time;
- activation readiness time;
- feature-flag state.

A digest protects the complete gate payload.

## Activation-plan enforcement

`prepare_global_worker_activation_plan()` now asks the gate layer whether
post-incident evidence is required.

If durable history exists and the gate is absent, expired, tampered or bound to
different runtime/readiness/flag evidence, activation plan creation returns
`BLOCKED`.

The activation plan records:

- whether the post-incident gate was required;
- gate digest at plan time;
- closure ledger digest;
- latest closure record id.

The activation approval ticket carries the same closure-history bindings.

## Final pre-write recheck

The Central AION does not reuse the old gate blindly.

Immediately before any future feature-flag enable attempt, when post-incident
history exists, it re-reads:

- shared runtime;
- authoritative feature flag;
- live verification evidence;
- operational supervision;
- Incident Center reconciliation.

It then creates a **fresh** post-incident gate.

If this fresh gate is not green:

- Guardian/write path is not entered;
- activation function is not called;
- feature flag remains unchanged.

## Activation-function enforcement

`activate_global_worker_feature_flag()` also validates the fresh gate before
its flag writer can run.

It checks that:

- durable-history requirement has not changed;
- gate integrity is valid;
- gate is still unexpired;
- runtime SHA/digest are unchanged;
- closure ledger digest is unchanged;
- latest closure id is unchanged;
- current feature flag matches;
- closure-history binding matches the activation approval.

This protects callers outside the Streamlit UI too.

## Reopened incident

If the same incident evidence reappears after closure, Incident Center reports
`REOPENED`.

The gate becomes blocked and no activation plan/final write may proceed.

## New incident after closure

If different incident evidence appears after a prior closure, Incident Center
reports `OPEN_NEW_AFTER_CLOSURE`.

That also blocks the gate.

## Fail-open behavior

If runtime, ledger or closure reconciliation cannot be trusted, the system does
not assume safety.

It blocks post-incident reactivation.

## Central AION

The activation panel now shows:

- Post-incident gate status;
- durable history count;
- whether plan generation is allowed.

If the gate is required and green, the UI says explicitly that this **does not
authorize reactivation**.

At final confirmation, a fresh gate is recalculated before Guardian/write.

## No new authority

The gate module is read-only and contains no:

- Checkpoint write;
- feature-flag mutation;
- worker tick;
- workflow dispatch;
- subprocess/shell;
- provider/business action;
- deploy/merge;
- real trading.

The existing activation module still contains its guarded feature-flag write
ceremony, but that write path is now preceded by the post-incident gate
validation when durable incident history exists.

## Development-state boundary

Implementing and testing this gate does not activate or reactivate the real
Global Worker.

No feature flag is changed by this PR unless a future ADMIN separately performs
the existing explicit activation ceremony.

## CI audit

The stacked Draft PR may be temporarily retargeted to `main` only to run the
repository's standard pull-request workflows, then restored to its stacked base.


## Audit trigger note

When this stacked Draft PR is temporarily retargeted to `main`, a
documentation-only synchronize commit may be used to trigger the standard
pull-request workflows. This changes no runtime behavior and grants no
activation, reactivation, deploy, merge, feature-flag, or trading authority.
