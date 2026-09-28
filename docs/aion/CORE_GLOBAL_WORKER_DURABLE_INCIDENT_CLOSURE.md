# AION Global Worker Durable Incident Closure Record V1

## Purpose

This block persists the human closure decision created by Human Incident Closure
Ceremony V1 into the shared runtime Checkpoint.

It does **not** reactivate the Global Worker and does **not** change the computed
Incident Center status.

The persisted object is an audit/governance record that says a human closure
decision was approved and durably recorded.

## Separate authority boundary

Durable persistence is a different authority from:

- human closure decision;
- Global Worker arming;
- activation;
- feature-flag mutation;
- lease ownership;
- worker tick;
- workflow dispatch;
- deploy;
- merge;
- real trading.

A persisted closure record therefore keeps:

- `authoritative_incident_center_status_modified=false`;
- `reactivation_authorized=false`;
- `feature_flag_modified=false`;
- `global_worker_modified=false`;
- `real_trading_enabled=false`.

## Required upstream record

The module accepts only:

`HUMAN_CLOSURE_DECISION_RECORDED_SESSION_ONLY`

The record must also have:

- human closure decision recorded;
- human decision = APPROVED;
- authoritative incident closed = false;
- persistent = false;
- session_only = true;
- reactivation authorized = false;
- closure record id;
- closure record digest;
- closure package digest;
- incident evidence digest;
- remediation digest;
- recorded timestamp.

## Human-record integrity

Before any durable plan is created, the module reconstructs the exact digest
payload used by the human closure ceremony.

The expected `closure_record_digest` and `GW-CLOSE-...` record id must match.

Tampered session records fail with:

`HUMAN_CLOSURE_RECORD_INTEGRITY_MISMATCH`

## Durable ledger

Namespace:

`aion_global_worker_incident_closure_ledger_v1`

The ledger contains immutable closure records and an integrity digest.

A durable record contains:

- closure record id/digest;
- closure package digest;
- incident evidence digest;
- remediation digest;
- human-recorded timestamp;
- operator-note digest (the note text itself is not persisted here);
- human decision = APPROVED;
- persistence timestamp/actor;
- source runtime SHA/checkpoint digest;
- feature-flag state at persistence;
- record digest.

The ledger is fail-closed on schema, count or digest mismatch.

Duplicate same-id/same-digest writes are idempotent.
Same id with a different digest is a conflict.

V1 blocks when the ledger reaches 100 records; it does not silently evict audit
history.

## Plan

A durable persistence plan requires:

- ADMIN context;
- confirmed runtime Checkpoint;
- runtime write preflight allowed;
- current runtime SHA;
- authoritative feature-flag state;
- valid human closure record;
- healthy closure ledger integrity.

The plan binds:

- human closure id/digest;
- source runtime SHA;
- source checkpoint digest;
- exact Global Worker state digest;
- current ledger digest;
- current feature-flag state;
- TTL and rollback source.

The plan performs no write.

## Exact persistence phrase

`PERSISTIR FECHAMENTO INCIDENTE WORKER GLOBAL`

This phrase creates only a short-lived persistence approval.

It does not by itself write anything.

## Second confirmation

The actual checkpoint write requires a second explicit confirmation after the
approval remains valid.

Normal conversational phrases such as “vamos lá” do not satisfy this ceremony.

## Pre-write invariants

Immediately before the write:

- approval integrity must match;
- ADMIN/scope must match;
- ticket must be unexpired;
- human closure record must still match;
- runtime SHA must still match;
- checkpoint digest must still match;
- Global Worker state digest must still match;
- ledger digest must still match;
- feature flag must still equal the state bound to the approval.

## CAS write

The write uses the runtime checkpoint SHA as `expected_sha`.

It does not pass or request the Global Worker arming transition exception.

Only the closure ledger is added/extended by the candidate builder.

## Post-write verification

After the write, the module requires:

1. saved + verified runtime result;
2. the exact durable closure record is present;
3. Global Worker state digest is unchanged;
4. feature flag is still confirmed in the exact pre-write state.

If any post-write invariant fails, the module attempts a CAS rollback to the
exact source checkpoint.

Possible outcomes:

- `CONFIRMED`
- `ROLLED_BACK`
- `CRITICAL_ROLLBACK_FAILED`

## Success truth state

A confirmed persistence may report:

- `durable_closure_persisted=true`;
- `shared_closure_record_persisted=true`.

It still reports:

- `authoritative_incident_center_status_modified=false`;
- `feature_flag_modified=false`;
- `global_worker_modified=false`;
- `global_worker_executed=false`;
- `reactivation_authorized=false`;
- `real_trading_enabled=false`.

## Central AION

The Central exposes:

`💾 Persistência durável do fechamento`

Flow:

1. read authoritative feature flag;
2. generate persistence plan;
3. type exact persistence phrase;
4. confirm evidence review;
5. create short-lived approval;
6. second confirmation;
7. Guardian `save_checkpoint`;
8. CAS write + read-after-write verification;
9. rollback on invariant violation.

The implementation exists for later explicit use. Creating/reviewing this PR
does not execute the persistence.

## No real execution in this block

No durable closure record is being persisted merely by implementing or testing
this code.

No merge, deploy, arming, activation, reactivation, worker tick or trading
action is part of this development block.

## CI audit

The Draft PR may be temporarily retargeted to `main` solely to trigger the
repository's standard pull-request workflows. It must be returned to its stacked
base after audit.
