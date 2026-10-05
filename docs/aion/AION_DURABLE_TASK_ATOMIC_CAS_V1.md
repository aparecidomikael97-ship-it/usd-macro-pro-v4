# AION Durable Task Atomic CAS Repository V1

Status: staging hardening only. This contract persists task state locally but
does not execute task steps, call providers, resume work automatically, merge,
deploy, trade or perform external actions.

## Problem closed

The legacy durable_tasks module intentionally operated over caller-provided
snapshots. It proved transition/revision semantics but could not, by itself,
guarantee multi-process compare-and-swap uniqueness.

The new physical repository provides that authoritative persistence boundary.

## Architecture

The responsibilities are deliberately separated:

- atlasquant_aion_durable_tasks.py remains the pure transition engine;
- atlasquant_aion_durable_task_repository.py owns physical task persistence;
- SQLite transactions provide the atomic CAS boundary;
- Checkpoint Mestre is a projection of physical task truth, not a second writer.

No duplicate task state machine was created.

## Physical identity

Every row is keyed by:

- owner_id;
- tenant_id;
- workspace_id;
- durable_task_id.

The same task id may exist in two trusted scopes without collision, while a
foreign scope cannot read or mutate another scope's row.

## Integrity binding

Each persisted task binds:

- normalized canonical JSON payload;
- full SHA-256 payload digest;
- task id;
- revision column;
- task state column;
- updated_at column.

Read fails closed if any binding diverges.

The repository normalizer does not silently heal corrupted physical state.

## Atomic compare-and-swap

A candidate update requires:

- trusted scope;
- existing physical row;
- exact expected_revision;
- candidate revision == expected_revision + 1;
- terminal-state invariants;
- UPDATE ... WHERE revision = expected_revision inside BEGIN IMMEDIATE.

A stale writer receives REVISION_CONFLICT.

No Python-only mutex is used as the correctness boundary.

## Lost response / retry

If a CAS committed but the caller lost the response, retrying the exact same
candidate is IDEMPOTENT even when the caller still carries the old expected
revision.

A different candidate from the old revision is rejected.

## Crash windows

Fault-injection tests prove:

- crash before CAS commit => old revision remains authoritative;
- crash after CAS commit => new revision remains authoritative;
- reopening the store verifies integrity;
- retry after the after-commit crash is idempotent.

## Real multi-process race

The red-team launches two separate spawned processes.

Both:

1. open independent SQLite handles;
2. read the same revision;
3. build different valid revision+1 candidates;
4. synchronize at a process barrier;
5. attempt CAS.

Exactly one process updates the row. The other gets REVISION_CONFLICT.

The final physical row has one valid revision and passes integrity verification.

## Checkpoint Mestre projection

checkpoint_projection() exports the repository state to the existing durable
tasks checkpoint shape plus repository_digest metadata.

verify_checkpoint_projection() checks:

- task digest;
- repository digest;
- task payload equality.

If physical state advances while the checkpoint copy remains old, the result is
MISMATCH.

The physical repository remains authoritative and the stale checkpoint cannot
overwrite it.

## Red-team coverage

Tests cover:

- create/load;
- idempotent create;
- task-id collision;
- one-revision CAS;
- stale writer conflict;
- same-candidate lost-response replay;
- revision skipping;
- terminal-state forgery;
- crash before commit;
- crash after commit;
- two SQLite connections racing same candidate;
- two real processes racing different candidates;
- tenant/owner/workspace isolation;
- digest corruption;
- revision-column corruption;
- state-column corruption;
- updated_at corruption;
- payload rewrite;
- stale Checkpoint Mestre projection;
- forged checkpoint projection;
- zero socket/subprocess use for repository operations;
- automatic_resume_executes=false.

## Authority boundary

Persisting or recovering a durable task restores state only.

It does not:

- execute a step;
- re-grant approval;
- dispatch a provider;
- call a connector;
- perform an external effect;
- infer that a previously valid authorization is still valid.

All execution and approval gates remain downstream and separate.
