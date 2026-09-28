# AION Global / Durable Worker V1

This block extends the AION worker stack beyond one browser session by using the
existing AtlasQuant runtime-data branch and the already-scheduled Autopilot
workflow.

It does **not** create a second cron, a new paid service, or a general-purpose
external-action worker.

## Activation requires two independent gates

The global runner executes only when both are true:

1. an authenticated ADMIN has staged **ARMED** global delegation and that state
   has been explicitly persisted in the Checkpoint Mestre;
2. repository/runtime variable
   `ATLASQUANT_AION_GLOBAL_WORKER_ENABLED=1` is explicitly enabled.

The feature flag is off by default.

If the flag is off, `run_global_worker_once` exits before loading the runtime
checkpoint and reports `network_called=false`.

## Cost model

No additional cron schedule is introduced.

The runner reuses the existing:

`AtlasQuant - Automatic Scanner + Autopilot`

pulse:

`7,37 * * * *`

The new worker step is conditionally skipped unless the feature flag is exactly
enabled. Therefore the design does not add a separate scheduled GitHub Actions
job.

## Shared control plane

Global worker state lives inside the existing Checkpoint Mestre under:

`aion_global_worker_v1`

It contains:

- DISABLED / ARMED / PAUSED / KILLED state;
- global kill switch;
- exact delegated ADMIN scope;
- local allowlist;
- maximum jobs per tick;
- lease duration;
- monotonic fencing counter;
- current global lease;
- global runtime statistics;
- activation and safety posture;
- independent digest.

The namespace is included in the master Checkpoint integrity report and source
conflict digest.

## Delegated service principal

The global runner does not claim that the administrator clicked each tick.

Explicit arming stores only the identity material necessary to reconstruct the
same isolated AION Context. The trusted runner then operates as:

`aion-global-worker`

Receipts use:

`authorization_mode = GLOBAL_WORKER`

and record:

- empty per-tick `human_confirmation_digest`;
- delegated actor;
- service execution principal;
- global authorization digest;
- lease/fencing-bound execution.

The original ADMIN arming remains the authority source for the delegated scope.

## CAS and fencing

The lease is stored in the **same Checkpoint Mestre file** that stores schedules
and executor receipts.

Claim flow:

1. read Checkpoint Mestre + current GitHub content SHA;
2. validate global control-plane digest and ARMED state;
3. calculate next monotonic fencing token;
4. write the lease with conditional GitHub Contents API SHA;
5. read back and verify owner, token, fencing token and expiry;
6. execute only safe local allowlisted Core work;
7. write receipts + final heartbeat/release with the SHA produced by claim.

This prevents a stale worker from successfully committing after another worker
has claimed the checkpoint: the stale writer's expected content SHA no longer
matches.

GitHub 409/422 responses are treated as CAS conflicts, not as permission to
overwrite.

## Lease / crash recovery

Default lease: 1200 seconds.

Allowed range: 300–1800 seconds.

A different runtime cannot claim an active lease.

After expiry, another runtime can reclaim the lease and increments the crash
recovery statistic. Every new claim receives a monotonically increasing fencing
token.

The global runner ID comes from the GitHub Actions run ID + attempt when
available.

## Durable queue

The global worker does not create another queue format.

It reuses the durable scheduler + executor receipts already inside the same
Checkpoint:

- schedules define due work;
- occurrence keys provide idempotency;
- FAILED receipts carry retry/backoff;
- terminal SUCCEEDED/BLOCKED receipts prevent repeat execution.

This means queue, lease, receipts, integrity and checkpoint SHA are coordinated
through one runtime document.

## Global allowlist

The global runner is narrower than the local/session executor.

Allowed:

- ADMINISTRATION
- MEMORY
- RESEARCH
- CONTENT draft
- OBSERVABILITY

Not globally allowed:

- VOICE/provider calls
- DEVELOPER command execution
- AUTOMATION recursion
- BUSINESS
- TRADER
- INVESTMENTS
- any future capability not explicitly added

A schedule outside the global allowlist is recorded as BLOCKED rather than
being guessed or escalated.

## Automatic persistence boundary

Unlike the session Worker V1, the global runner must persist internal
operational state to coordinate across runs.

It is allowed to automatically write **only** the runtime Checkpoint on the
dedicated non-code branch for:

- lease/fencing;
- heartbeat/statistics;
- safe local execution receipts;
- retry/idempotency state.

Every write is conditional on the current runtime content SHA and is verified
with read-after-write.

This operational persistence is explicitly separated from business/external
actions.

## Actions that remain prohibited

Global Worker V1 cannot automatically:

- call an external AI/model provider;
- generate paid neural audio;
- publish social/media content;
- publish marketplace listings;
- charge a customer;
- move money;
- buy media;
- deploy production;
- merge code;
- run subprocess/shell commands;
- place market orders;
- enable real trading.

The returned safety posture remains false for provider/business/external action
flags.

## Global pause and kill switch

The Central AION can stage:

- Arm Global
- Pause Global
- Kill Global

These controls only modify the working Checkpoint first.

They become globally authoritative only after the administrator explicitly
saves the Checkpoint Mestre through the existing guarded persistence flow.

The global runner reads the persisted shared checkpoint. A persisted KILLED
state exits before lease claim or task execution.

## UI truth model

The Central clearly distinguishes:

- session Worker Runtime;
- global/durable control plane;
- staged state vs persisted state;
- local observation of the activation flag;
- lease state;
- fencing counter;
- global statistics.

A local UI cannot claim the GitHub repository variable is enabled unless that
flag is actually visible to its own environment.

## Infrastructure posture

This block materially improves the previous limitation:

- heartbeat no longer requires an open browser once the runner is enabled;
- lease state is on shared runtime storage;
- CAS is based on GitHub content SHA;
- fencing is monotonic and persisted;
- queue/receipts are durable;
- runner identity is auditable.

However the actual wake-up cadence is still the existing GitHub Actions
Autopilot pulse, not a dedicated real-time scheduler.

Therefore the truthful claim is:

**global durable periodic worker prepared and feature-gated**, not continuous
real-time execution.

## No merge / deploy activation

A Draft PR containing this code does not activate the worker.

The runner cannot become active until the stack is merged to the code branch,
the ARMED state is explicitly persisted, and the feature flag is explicitly
enabled.
