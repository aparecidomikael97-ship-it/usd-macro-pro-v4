# AION Global Worker Persisted Arming Ceremony V1

This block governs the first real persistence of a staged Global Worker
`ARMED` state into the shared Checkpoint Mestre.

It is intentionally separate from:

1. the first Arming Ceremony that creates `STAGED_ARMED`;
2. later activation of `ATLASQUANT_AION_GLOBAL_WORKER_ENABLED`.

## Security objective

A staged `ARMED` checkpoint must not be persistable through the normal
Checkpoint save button.

Persisting `ARMED` requires a second ceremony bound to:

- the same authenticated ADMIN context;
- the exact staged working Checkpoint digest;
- the current persisted runtime Checkpoint digest;
- the current runtime content SHA;
- the exact arming plan / arming approval / arm digests;
- a short persistence-approval TTL;
- proof that the repository activation flag is UNSET or DISABLED.

## Feature flag proof

The persisted-arming module reads repository Actions variables with GET-only
access.

It requests the variables collection and determines only one of:

- UNSET
- DISABLED
- ENABLED
- INVALID / UNKNOWN

The raw variable value is not returned by the public report.

Persistence is blocked unless the evidence is authoritative and the state is
UNSET or DISABLED.

The module contains no PUT/POST/PATCH/DELETE operation for repository variables.

## Three persistence steps

### 1. Verify flag and generate persistence plan

The ADMIN first performs a read-only flag check.

With safe evidence, the system creates an in-session persistence plan bound to:

- working Checkpoint digest;
- persisted runtime Checkpoint digest;
- persisted runtime SHA;
- arming plan digest;
- arming approval digest;
- arm digest;
- resource budgets;
- rollback source;
- TTL.

No runtime write happens.

### 2. Create persistence approval

The same ADMIN must explicitly confirm and type exactly:

`PERSISTIR WORKER GLOBAL ARMADO`

This creates another short-lived ticket in session memory.

The ticket is invalidated when:

- actor/context changes;
- working Checkpoint changes;
- runtime SHA changes;
- runtime Checkpoint digest changes;
- staged arming digests change;
- TTL expires.

### 3. Second confirmation and guarded write

The final button requires an additional checkbox:

`SEGUNDA CONFIRMAÇÃO`

The persistence function then:

1. validates the persistence ticket;
2. re-reads the repository feature flag;
3. requires UNSET or DISABLED;
4. calls the guarded Checkpoint writer using the exact expected SHA;
5. performs the normal read-after-write verification;
6. verifies the persisted Global Worker state matches the staged arming state;
7. re-reads the repository feature flag.

The feature flag is never modified by this flow.

## Generic save bypass is closed

`save_runtime_checkpoint` now blocks a new Global Worker ARMED transition by
default.

A direct normal save returns:

`Global Worker ARMED transition requires Persisted Arming Ceremony.`

The writer accepts the transition only when the protected persisted-arming path
passes:

`allow_global_arming_transition=True`

Even with that flag, the source runtime must already be CONFIRMED and the
provided expected SHA must equal the current runtime SHA.

Once the exact same ARMED state is already persisted, ordinary later Checkpoint
saves do not represent a new arming transition and remain subject to the normal
Checkpoint guards.

## Pre-write / post-write feature-flag race protection

The activation flag is checked twice:

- immediately before the ARMED write;
- immediately after read-after-write verification.

If the post-write check no longer proves UNSET/DISABLED, the system attempts an
automatic CAS rollback to the exact pre-arming Checkpoint using the SHA created
by the ARMED write.

Successful safety rollback returns:

`ROLLED_BACK`

If rollback itself cannot be confirmed because the runtime changed or the write
failed, the result is:

`CRITICAL_ROLLBACK_FAILED`

No success claim is allowed in that case.

## Rollback source

The persistence plan records:

- pre-arming runtime SHA;
- pre-arming runtime Checkpoint digest.

The actual pre-arming Checkpoint is held by the running persistence operation
and is used as the rollback body only if the post-write safety check fails.

The rollback uses the standard guarded writer and the newly written ARMED SHA as
its expected SHA, preserving CAS semantics.

## What is persisted

A successful persisted arming writes the already-staged Global Worker control
plane to the Checkpoint Mestre.

It does not:

- change the repository feature flag;
- execute a worker tick;
- call an AI provider;
- publish;
- make a payment;
- deploy;
- merge;
- execute subprocess/shell;
- place a market order;
- enable real trading.

The expected final state after successful persistence is:

- Global Worker state: ARMED
- activation feature flag: still UNSET/DISABLED
- no lease claimed by this ceremony
- no worker execution performed

The next required evidence state is:

`READY_FOR_FLAG_ENABLE`

from the separate Activation Readiness gate.

## UI behavior

When a new Global Worker ARMED transition is present in the working Checkpoint:

- the generic `Salvar Checkpoint Mestre no runtime` button is disabled;
- the UI displays `Persisted Arming Ceremony`;
- feature-flag verification is required;
- persistence plan generation is required;
- exact phrase confirmation is required;
- a persistence ticket is required;
- a second explicit confirmation is required;
- only then is the special ARMED persistence button enabled.

## Current development boundary

Building and testing this path does not persist ARMED.

The real runtime remains unchanged until a human uses the final ceremony and
explicitly authorizes the write.

A normal conversational continuation such as "vamos lá" is not interpreted as
authorization to persist ARMED.

## CI audit procedure

Because the repository's traditional pull-request quality workflows target
`main`, this stacked draft may be temporarily retargeted to `main` only for
CI audit. A documentation-only synchronize commit may be used to trigger those
workflows. After validation, the base is restored to
`cursor/aion-global-worker-arming-ceremony-v1`.

This audit process does not persist ARMED, modify the runtime Checkpoint,
change the repository feature flag, execute the Global Worker, merge or deploy.
