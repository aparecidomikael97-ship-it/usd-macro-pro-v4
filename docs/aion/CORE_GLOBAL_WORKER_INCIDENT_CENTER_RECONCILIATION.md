# AION Global Worker Incident Center Closure Reconciliation V1

## Purpose

This block teaches the Central Incident Center to recognize durable Global
Worker closure records without allowing historical closure to hide current
evidence.

It is read-only.

It reconciles:

1. the normal Incident Center snapshot;
2. the current Global Worker Operational Supervision snapshot;
3. the durable closure ledger from the **confirmed shared runtime Checkpoint**.

## Core safety rule

**A prior closure never authorizes reactivation and never suppresses newer
incident evidence.**

The reconciliation layer always keeps:

- `reactivation_authorized=false`;
- `automatic_reactivation=false`;
- `feature_flag_modified=false`;
- `runtime_modified=false`;
- `global_worker_modified=false`;
- `executes_action=false`;
- `real_trading_enabled=false`.

## Durable evidence source

Closure history is trusted only from:

- `runtime_result.status=CONFIRMED`;
- the durable ledger
  `aion_global_worker_incident_closure_ledger_v1`;
- valid ledger schema/count/digest;
- individually valid durable record schema/digest/timestamps/authority flags.

A local session-only human closure record is not enough.

If runtime or durable evidence cannot be verified, reconciliation is **fail-open
for safety**: the current incident remains OPEN.

## Individual durable record validation

Every durable record is revalidated independently even after the ledger digest
passes.

The reconciler requires:

- durable record schema;
- record digest match;
- closure record id/digest;
- closure package digest;
- incident evidence digest;
- remediation digest;
- human decision = APPROVED;
- valid human/persistence timestamps;
- persistence not earlier than human decision;
- no Incident Center authority mutation;
- no reactivation authority;
- no feature-flag mutation;
- no Global Worker mutation;
- no real trading.

Any invalid durable row blocks closure reconciliation.

## Current incident identity

Global Worker supervision creates a deterministic evidence digest from:

- live status;
- heartbeat/tick/work receipt confirmation;
- unsafe receipt count;
- stale lease state;
- runtime id;
- heartbeat/tick timestamps;
- feature-flag state/proof.

The Incident Center id is:

`INC-AION-GW-<first 12 chars of evidence digest>`

## Reconciliation states

### OPEN

No durable closure exists for the current Global Worker incident evidence.

The incident remains active.

### CLOSED_HUMAN_VERIFIED

This is allowed only when:

- the exact `incident_evidence_digest` has a valid durable closure record; and
- the current incident observation timestamp is no later than that durable
  persistence timestamp.

This represents historical evidence that was later closed.

It is moved from the active incident list into read-only closure history.

### REOPENED

If the exact same incident evidence appears with an observation timestamp
**after** the durable closure persistence timestamp, it is not hidden.

It becomes:

`REOPENED`

with the prior closure id retained as evidence.

### OPEN_NEW_AFTER_CLOSURE

If a different Global Worker incident evidence digest appears after a prior
durable closure, it remains active as:

`OPEN_NEW_AFTER_CLOSURE`

The historical closure is preserved, but does not apply to the new evidence.

### FAIL_OPEN

If runtime/ledger/record evidence is unavailable or invalid:

- no closure is applied;
- current incident remains OPEN;
- UI explains that durable reconciliation is unavailable.

## Active vs closed counts

The Incident Center now distinguishes:

- `total`: active incidents only;
- `counts`: active incidents by severity;
- `closed_total`: durable/historically closed Global Worker incidents;
- `closed_incidents`: read-only closure history.

Historical closed incidents do not reduce or overwrite unrelated active
incidents.

## Existing incidents are preserved

The reconciler starts from the normal Incident Center snapshot.

Application, integrity, engine, account, reliability and other incidents remain
unchanged.

The Global Worker incident is added/reconciled independently and active counts
are recalculated.

## UI

The Central Incident Center shows:

- active incident count;
- reconciliation state;
- durable closure count;
- explicit warning for `REOPENED`;
- explicit warning for new incident after prior closure;
- fail-open warning if closure evidence cannot be trusted;
- a separate **Histórico de incidentes fechados** table.

The history table always says:

`Reativação autorizada = NÃO`

## Response plan

Global Worker incidents receive specific read-only response guidance:

1. preserve current and historical closure evidence;
2. treat reopened/new evidence as active;
3. rerun Supervisão → Remediação → Closure Review;
4. keep reactivation/feature flag/trading separate from incident closure.

## No mutation authority

This reconciliation module contains no:

- runtime Checkpoint write;
- feature-flag write;
- activation/deactivation;
- worker tick;
- workflow dispatch;
- subprocess/shell;
- deploy/merge;
- external/business action;
- real trading.

## CI audit

The stacked Draft PR may be temporarily retargeted to `main` solely to run
the standard PR workflows, then returned to its stacked base.

No reconciliation test or CI action authorizes real closure persistence,
activation, reactivation, deploy, merge, or trading.


## Audit trigger note

When this stacked Draft PR is temporarily retargeted to `main`, a
documentation-only synchronize commit may be used to trigger the standard
pull-request workflows. This changes no runtime behavior and grants no closure,
activation, reactivation, deploy, merge, or trading authority.
