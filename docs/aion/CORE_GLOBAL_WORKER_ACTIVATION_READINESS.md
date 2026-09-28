# AION Global Worker Activation Readiness V1

This gate exists between "the global worker code is implemented" and "the
global worker is allowed to be activated."

It is deliberately read-only.

## What it verifies

The readiness gate checks five independent evidence groups:

1. runtime posture;
2. existing Autopilot workflow contract;
3. recent scheduled pulse health;
4. Global Worker feature-flag posture;
5. in-memory lease/fencing/kill-switch protocol simulation.

The result is an explicit activation stage rather than an automatic activation.

## Read-only guarantee

The readiness module does not:

- save the Checkpoint;
- acquire a real lease;
- arm the real worker;
- pause or kill the real worker;
- modify repository variables;
- dispatch/rerun workflows;
- write code;
- publish;
- deploy;
- pay;
- trade.

Its network access is GET-only:

- load the existing runtime Checkpoint;
- read recent runs of the existing Autopilot workflow.

The dedicated readiness workflow has:

- `contents: read`;
- `actions: read`;
- no `schedule:` trigger.

## Feature flag observation

The readiness workflow receives the repository variable:

`ATLASQUANT_AION_GLOBAL_WORKER_ENABLED`

through a separate environment name:

`GLOBAL_WORKER_FLAG_STATE`

This lets the gate observe the posture without setting the runtime activation
environment variable itself.

The report exposes only:

- UNSET
- DISABLED
- ENABLED
- INVALID

It does not echo a raw variable value.

## Runtime posture

The gate requires:

- a dedicated non-code runtime branch;
- runtime Checkpoint status CONFIRMED;
- a current runtime content SHA;
- Checkpoint integrity CONFIRMED or MIGRATION_REQUIRED;
- Global Worker namespace ABSENT or MATCH.

A mismatched Global Worker digest blocks activation readiness.

## Existing scheduled pulse

No new cron is introduced.

The source contract must still contain exactly one cron in:

`.github/workflows/autopilot-v107.yml`

and must still condition the Global Worker step on:

`vars.ATLASQUANT_AION_GLOBAL_WORKER_ENABLED == '1'`

Recent pulse evidence requires at least three successful scheduled runs and a
recent successful latest run.

## Shadow protocol probe

Every readiness execution performs an entirely in-memory simulation:

1. create a synthetic ADMIN scope;
2. stage a synthetic global arming;
3. claim fence 1 as runtime A;
4. prove runtime B is blocked while the lease is live;
5. advance beyond lease expiry;
6. prove runtime B reclaims with fence 2;
7. prove crash recovery increments;
8. stage the kill switch;
9. prove no network/runtime/feature-flag mutation occurred.

The synthetic scope is never persisted.

## Activation stages

### READY_FOR_ADMIN_ARMING

Infrastructure and shadow protocol pass, the feature flag is UNSET/DISABLED,
and the persisted runtime is not armed.

This is the expected safe state before an administrator deliberately persists
global arming.

### READY_FOR_FLAG_ENABLE

Infrastructure passes, the Global Worker is persistently ARMED with kill switch
off, and the feature flag is still UNSET/DISABLED.

This state is evidence that the second activation gate could be considered.
It does not enable the flag.

### BLOCKED

Any of the following blocks the readiness gate:

- unsafe or unavailable runtime;
- invalid Checkpoint integrity;
- broken workflow contract;
- unhealthy/stale scheduled pulse;
- failed shadow protocol;
- invalid feature-flag value;
- feature flag enabled before persisted arming;
- feature flag enabled while kill switch is active.

### ACTIVATION_ENABLED_REQUIRES_LIVE_HEARTBEAT_EVIDENCE

If both persisted arming and feature flag are already enabled, pre-activation
readiness is no longer sufficient. Live operational evidence is required before
claiming that global autonomy is functioning.

## Baseline observed before this block

At implementation time the repository evidence showed:

- `atlasquant-runtime` exists;
- Checkpoint Mestre is schema `ATLASQUANT_AION_MEMORY_V1`, version 18;
- the persisted Checkpoint did not yet contain `aion_global_worker_v1`;
- recent scheduled Autopilot runs were completing successfully.

Therefore the worker was not persistently armed.

The connected repository API available during implementation did not expose
repository Actions variables directly. The new readiness workflow resolves that
missing evidence inside GitHub Actions without modifying the variable.

## Activation remains a separate decision

A green readiness gate does not authorize activation.

The later activation sequence remains separate:

1. review readiness evidence;
2. deliberately arm and persist the Global Worker;
3. rerun readiness and require READY_FOR_FLAG_ENABLE;
4. separately decide whether to enable the repository feature flag;
5. observe real global heartbeat/receipt evidence;
6. preserve immediate kill-switch and rollback paths.

Real trading, payment, publication, deploy and merge remain outside this
activation path.
