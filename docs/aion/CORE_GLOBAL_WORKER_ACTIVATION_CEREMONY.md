# AION Global Worker Activation Ceremony V1

This block governs the repository feature-flag transition that wakes the
already-persisted Global Worker through the existing GitHub Actions pulse.

It is intentionally separate from:

1. staging ARMED;
2. persisting ARMED;
3. proving that a real global worker heartbeat/receipt occurred.

A successful feature-flag write is **not** treated as proof that the worker ran.

## Preconditions

Activation planning requires all of the following:

- authenticated ADMIN context;
- runtime Checkpoint status CONFIRMED;
- runtime content SHA present;
- persisted Global Worker state = ARMED;
- Global Worker kill switch = false;
- no existing global lease owner;
- Activation Readiness status = PASS;
- Activation Readiness stage = READY_FOR_FLAG_ENABLE;
- no readiness blockers;
- current repository variable state = UNSET or DISABLED.

If any condition is missing, activation remains blocked.

## Current evidence is collected read-only

The Central can run:

**Verificar readiness atual para ativação**

This collector:

- reads the repository feature flag;
- reads recent Autopilot scheduled runs;
- reads the local Autopilot workflow contract;
- evaluates the persisted runtime Checkpoint;
- runs the existing in-memory shadow protocol.

It does not mutate the Checkpoint, repository variable, worker, schedule, or any
external business system.

## Activation plan

The activation plan is bound to:

- actor and Context scope;
- current runtime SHA;
- current runtime Checkpoint digest;
- arm digest;
- arming plan digest;
- arming approval digest;
- resource budgets;
- max jobs;
- lease duration;
- readiness stage and timestamp;
- current feature-flag state;
- approval expiry.

Default ticket TTL is 600 seconds. Allowed range is 300–1800 seconds.

## Explicit human phrase

The same ADMIN must type exactly:

`ATIVAR WORKER GLOBAL`

and explicitly approve the activation plan.

This creates a short-lived activation ticket in session memory. It still does
not change the repository variable.

## Final confirmation

The final activation button requires another explicit confirmation:

**Habilitar Worker Global (feature flag)**

The UI also passes through the existing Guardian `write_runtime` WRITE-risk
gate.

A normal conversational continuation such as "vamos lá" is not interpreted as
authorization for this external repository mutation.

## Fresh runtime verification

Immediately before changing the flag the activation function:

1. reloads the runtime Checkpoint;
2. requires the same runtime SHA;
3. requires the same Checkpoint digest;
4. requires the same arm/approval digests;
5. requires ARMED + kill switch false;
6. requires no lease owner;
7. re-reads the feature flag;
8. requires the same safe prior state recorded in the ticket.

If the runtime or flag changed, no enable write occurs.

## Repository variable write

Only this variable is targeted:

`ATLASQUANT_AION_GLOBAL_WORKER_ENABLED`

If the confirmed prior state is UNSET, the variable is created with value
`1`.

If the confirmed prior state is DISABLED, the existing variable is updated to
value `1`.

The module does not dispatch a workflow and does not run a worker tick directly.
The existing scheduled Autopilot workflow remains the wake-up mechanism.

## Post-write verification

After the enable write, the system:

1. reads the variable again and requires ENABLED;
2. reloads the runtime Checkpoint again;
3. revalidates the exact activation ticket against that runtime.

Only then does it return:

`ACTIVATED_PENDING_LIVE_EVIDENCE`

That status means only that the flag was confirmed enabled and runtime remained
the approved ARMED state.

It explicitly does **not** mean that a worker tick happened, a heartbeat is
live, a receipt exists, or 24/7 autonomy is proven.

The returned truth flags remain:

- `global_worker_executed = false`
- `live_heartbeat_confirmed = false`
- `live_receipt_confirmed = false`
- `runtime_checkpoint_modified = false`
- `real_trading_enabled = false`

## Safety rollback

If the enable write is accepted but ENABLED cannot be confirmed, or if the
runtime changes during activation, the system attempts to force the feature
flag back to DISABLED.

A successful safety rollback returns:

`ACTIVATION_ROLLED_BACK`

If the rollback cannot be confirmed:

`CRITICAL_ACTIVATION_ROLLBACK_FAILED`

No operational-success claim is allowed in that state.

If the initial write outcome itself is uncertain and the follow-up read shows
the flag ENABLED, the same safety-disable path is used.

## Safety deactivation path

The Central also exposes a separate explicit stop path.

The ADMIN must type:

`DESATIVAR WORKER GLOBAL`

The system then sets the repository variable to a disabled value and reads it
back.

This stop action does not modify the Checkpoint, execute a worker tick, enable
trading, publish, deploy, merge, or pay.

## No Checkpoint write in this block

Activation Ceremony V1 never calls `save_runtime_checkpoint`.

It changes only the dedicated repository variable after the full activation
approval path.

## No direct worker execution

The module does not call:

- `run_global_worker_once`;
- worker tick functions;
- workflow dispatch;
- subprocess/shell;
- trading;
- payment;
- publication;
- deploy;
- merge.

## Next gate: Live Activation Verification

After a future explicit real activation, the required next block is:

**Global Worker Live Activation Verification V1**

It must prove from shared runtime evidence that:

- a new GLOBAL_WORKER heartbeat/tick occurred after activation;
- the receipt belongs to the approved persisted arm contract;
- fencing/lease remained coherent;
- no forbidden external effect occurred;
- the worker remained within budgets;
- the latest scheduled pulse is healthy.

Until then, the truthful state is:

`ACTIVATED_PENDING_LIVE_EVIDENCE`

not "global worker operational".


## CI audit procedure

Because the repository's traditional pull-request workflows target `main`,
this stacked draft may be temporarily retargeted to `main` only for CI audit.
A documentation-only synchronize commit may be used to trigger those workflows.

After validation, the PR base must be restored to
`cursor/aion-global-worker-persisted-arming-v1`.

This audit procedure must not:

- call the activation function;
- change the repository variable;
- persist ARMED;
- dispatch the worker;
- merge;
- deploy.
