# AION Core — Checkpoint Memory Bridge V1

This block connects AION Core Intelligence memory to the existing AtlasQuant
Checkpoint Mestre without creating a second remote persistence system.

## Persistence model

Core memory is staged under the existing `aion_core_intelligence_v1`
namespace inside the working Checkpoint Mestre. The namespace contains a
scope-bound, versioned bundle with records, human-approval state, local Core
events and its own digest.

Staging a record does **not** write to GitHub or any other external service.
Remote durability still occurs only through the existing
**Salvar Checkpoint Mestre no runtime** flow, which keeps conditional SHA
protection, Guardian checks, read-after-write verification and explicit
administrator approval.

Because the Core namespace is part of the master checkpoint, the existing
version history and recovery/rollback path carry the Core bundle with the rest
of the checkpoint. No separate backup service or paid storage is introduced.

## Human approval

A USER_APPROVED Core memory record requires two distinct human boundaries:

1. The authenticated administrator reviews the exact memory text, checks the
   explicit confirmation control and clicks to stage it. A one-shot receipt is
   bound to actor, scope, approval ID, subject digest, action and decision.
2. External persistence remains separate. The staged checkpoint is not written
   remotely until the administrator explicitly uses the existing master
   checkpoint save control.

An approval receipt is consumed once. It cannot authorize physical execution,
publication, payment, deploy or market operations.

## Isolation

The Core bundle remains bound to the exact Context key:
tenant + workspace + actor + task + domain.

A different actor or context does not receive the stored records. A context
mismatch is isolated and cannot overwrite the existing namespace implicitly.

## Integrity

The nested Core bundle has its own SHA-256 digest. The legacy Checkpoint
integrity report now includes the Core namespace when it is present.

A mismatch:
- marks master-checkpoint integrity as MISMATCH;
- blocks the checkpoint save path before a network write;
- prevents a tampered Core bundle from being treated as trusted memory.

The master checkpoint conflict digest also includes the Core namespace, so a
staged Core-memory change participates in normal optimistic-concurrency checks.

## Runtime behavior

When the existing working Checkpoint is supplied to the runtime bridge:
- MEMORY becomes available locally;
- OBSERVABILITY can read scoped Core events;
- Administration reports `CHECKPOINT_MASTER_STAGED`;
- no Core read automatically exports or persists a changed bundle;
- no database directory or SQLite file is created.

Without a supplied Checkpoint, the earlier fail-closed behavior remains:
persistence and checkpoint-dependent Core capabilities are UNAVAILABLE.

## Safety boundaries

This block does not:
- call a provider;
- call the network from the Core checkpoint bridge;
- run subprocesses or commands;
- deploy;
- merge;
- publish content;
- move money;
- place market orders;
- enable real trading;
- bypass Guardian;
- automatically save the Checkpoint Mestre.

Physical execution and external actions remain false/blocked.

The checkpoint bridge itself remains network-free; only the pre-existing master
checkpoint save flow may perform the separately approved external persistence.
