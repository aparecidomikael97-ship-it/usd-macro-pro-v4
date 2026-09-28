# AION Global Worker Arming Ceremony V1

This block inserts a mandatory ceremony between readiness and any staged
`ARMED` Global Worker state.

It does not persist the runtime checkpoint and does not enable the repository
feature flag.

## Why this exists

The previous Global Worker control plane could stage `ARMED` after a simple
boolean confirmation.

That was sufficient for an early control-plane prototype, but it did not bind
the arming decision to:

- the exact ADMIN context;
- the exact current Checkpoint digest;
- a short approval TTL;
- explicit resource budgets;
- an exact human confirmation phrase;
- a one-time anti-replay boundary.

Arming Ceremony V1 closes those gaps.

## Three-step flow

### 1. Generate plan

The ADMIN chooses:

- max local jobs per tick;
- lease duration;
- approval TTL.

The system creates an in-memory arming plan bound to:

- actor ID;
- exact Context scope;
- source Checkpoint digest;
- allowed capabilities;
- hard resource budgets;
- approval expiry;
- the requirement that the external readiness gate be
  `READY_FOR_ADMIN_ARMING`.

The plan explicitly sets:

`readiness_verified_by_plan = false`

because readiness evidence belongs to the read-only readiness gate, not to the
plan generator.

Generating a plan changes no Checkpoint and no runtime data.

### 2. Create temporary approval

The same authenticated ADMIN must:

- explicitly confirm the plan;
- type exactly:

`ARMAR WORKER GLOBAL`

The approval is valid only while the plan TTL remains valid.

The approval ticket is integrity-protected and bound to:

- plan digest;
- actor;
- scope;
- source Checkpoint digest;
- lease;
- hard budgets;
- capability set;
- expiry;
- confirmation-phrase proof.

Creating this ticket still changes no Checkpoint and no runtime data.

### 3. Stage ARMED

`stage_arm_global_worker` now requires the valid approval ticket.

It validates the ticket against:

- current authenticated ADMIN;
- current exact Context;
- current Checkpoint digest;
- expiry;
- requested max jobs;
- requested lease;
- exact allowlist;
- zero external-action budgets.

Only then can it produce:

`STAGED_ARMED`

This changes only the working Checkpoint.

It does not save the runtime Checkpoint.

## Anti-replay

The ticket contains the source Checkpoint digest.

After the first successful staging, the Checkpoint changes because the global
worker namespace is added/updated.

Reusing the same ticket against that changed Checkpoint returns:

`ARMING_APPROVAL_CHECKPOINT_CHANGED`

A new plan and new approval are required.

## Hard budgets

The ticket hard-binds:

- `max_jobs_per_tick`;
- `max_runtime_checkpoint_writes_per_tick = 2`;
- `provider_calls_per_tick = 0`;
- `paid_service_calls_per_tick = 0`;
- `publications_per_tick = 0`;
- `payments_per_tick = 0`;
- `deploys_per_tick = 0`;
- `merges_per_tick = 0`;
- `subprocess_calls_per_tick = 0`;
- `market_orders_per_tick = 0`;
- `real_trading_enabled = false`.

The persisted `ARMED` state is also semantically checked against these rules.
A permissive budget is rejected even if a matching state digest was recomputed.

## Schedule assumption is not a budget

The current Autopilot cron implies approximately 48 scheduled pulses per UTC
day.

The plan records this only as a schedule assumption:

- existing pulses per hour: 2;
- estimated scheduled ticks per day: 48;
- hard daily limit claimed: false.

This prevents the system from presenting a cron-derived estimate as a hard
resource guarantee.

## TTL

Default approval TTL:

`900 seconds` (15 minutes)

Allowed range:

`300–3600 seconds`

TTL authorizes the **staging action** only.

It is not the lifetime of a persistently armed worker. Once a valid approval is
used to stage the exact state and that state is later explicitly persisted, the
historical approval expiry remains audit metadata.

## Already-armed state

A new arming plan is blocked when the working Checkpoint is already `ARMED`.

Re-arming after a pause/kill/disarm requires a new plan and a new short-lived
approval.

## Central AION UX

The old direct:

`Armar Global (staged)`

button is removed.

The Central now shows:

1. **Gerar plano de Arming**
2. exact plan digest / expiry / budgets
3. typed phrase + explicit confirmation
4. **Criar autorização temporária**
5. approval digest / expiry
6. **Preparar ARMED (staged, sem salvar)**

Pause and Kill remain separate staged controls.

## What this block does not do

This block does not:

- persist `ARMED` to `atlasquant-runtime`;
- set or modify `ATLASQUANT_AION_GLOBAL_WORKER_ENABLED`;
- execute the Global Worker;
- dispatch GitHub Actions;
- call a provider;
- publish;
- pay;
- deploy;
- merge;
- call subprocess/shell;
- trade.

## Required post-staging sequence

After a future explicit decision to persist the staged ARMED state:

1. enter the separate **Persisted Arming Ceremony**;
2. prove the repository activation flag is UNSET/DISABLED;
3. bind a second short-lived approval to working digest + runtime digest + runtime SHA;
4. type the dedicated persistence phrase and provide a second explicit confirmation;
5. persist only through the special guarded ARMED path;
6. verify read-after-write and the exact persisted arming contract;
7. re-check the feature flag and automatically roll back on safety violation;
8. rerun Activation Readiness;
9. require `READY_FOR_FLAG_ENABLE`;
10. keep the feature flag disabled until a separate activation decision.

Arming and activation remain separate approvals.

## CI audit procedure

Because the repository's traditional pull-request quality workflows target
`main`, this stacked draft may be temporarily retargeted to `main` only for
CI audit. A documentation-only synchronize commit may be used to trigger those
workflows. After validation, the base is restored to
`cursor/aion-global-worker-activation-readiness-v1`.

This audit procedure does not merge, deploy, persist ARMED, modify the runtime
Checkpoint, modify the repository feature flag, or execute the Global Worker.
