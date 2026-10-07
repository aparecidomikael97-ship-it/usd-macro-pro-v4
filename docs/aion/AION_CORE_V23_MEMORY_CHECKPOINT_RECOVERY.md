# AION Core V2.3 — Memory, Checkpoint & Recovery Contract

Baseline: `e0ae719ee4b66403ea86e66fe4a308dcccd923f5`.

This V2.3 is deliberately an integration/governance layer over the existing
AION Core. It does not create a second orchestrator, a second memory authority,
a second runtime persistence path, or a second recovery engine.

## Canonical components preserved

| Existing component | Remains authoritative for |
| --- | --- |
| `aion_core/memory_architecture.py` | seven memory layers, state machine, tenant/domain access |
| `aion_core/provenance.py` | origin, lineage, validation and deterministic provenance digests |
| `atlasquant_aion_truth.py` | fact / inference / hypothesis / unknown truth semantics |
| `atlasquant_aion_memory.py` | canonical Checkpoint Mestre runtime model and guarded persistence |
| `atlasquant_aion_recovery.py` | reviewed runtime-history recovery flow |
| `atlasquant_aion_unified_journal.py` | tamper-evident unified request lifecycle journal |
| `atlasquant_aion_unified_journal_store.py` | physical durable request journal persistence |
| `atlasquant_aion_durable_tasks.py` | resumable task state, revision and idempotency contracts |

The V2.3 files only add missing cross-cutting contracts.

## New memory contract

`atlasquant_aion_memory_contract.py` adds:

- namespaces: ecosystem, sector, project, tenant, persona, subject, decision,
  task, evidence, result, error and lesson;
- the same seven memory classes already present in the memory architecture;
- V2.3 validation states:
  `VALIDATED / CONFLICTING / OUTDATED / DOUBTFUL / QUARANTINED /
  REJECTED / UNVERIFIED / PROPOSED`;
- explicit compatibility mapping to existing memory architecture and
  `atlasquant_aion_truth.py`;
- mandatory governance metadata for versioning, prior version, evidence,
  provenance, retention, sensitivity, rollback pointer and tombstone;
- fail-closed scope requirements for tenant/persona/sector/project memory;
- operational blocker generation for conflict, stale/doubtful/unverified,
  quarantine, rejection and tombstone states;
- lesson contract where a lesson is never promoted into a global rule;
- library-document contract validation without ingestion, embeddings or
  provider calls.

Absence of evidence is never promoted to a fact. `VALIDATED` requires evidence
or provenance. `CONFLICTING` creates an explicit blocker.

## New Checkpoint Mestre envelope

`atlasquant_aion_checkpoint_master.py` adds a pure/offline envelope around a
snapshot and append-only merge-patch journal:

- deterministic canonical serialization and SHA-256 digests;
- logical compare-and-swap via `expected_revision`;
- append-only event chain with sequence, previous digest and event digest;
- duplicate same-id/same-payload idempotency;
- duplicate same-id/different-payload conflict;
- deterministic reconstruction at current or historical revision;
- rollback candidate generation only — no automatic rollback;
- controlled compaction that preserves state/revision while resetting journal;
- bounded base, event, journal and total payload sizes;
- corruption/tamper detection;
- rejection of execution-enabling safety flags;
- explicit prohibition on replay promotion `PLANNED -> EXECUTED`;
- inactive future hook for FIDO2/platform signature over deterministic digests.

This module does **not** write the runtime checkpoint. Runtime persistence
continues through `atlasquant_aion_memory.py`. Reviewed runtime recovery
continues through `atlasquant_aion_recovery.py`.

## Existing continuity files

The V2.3 envelope can carry references to the existing continuity evidence:

- `AION_CORE_NIGHTSHIFT_CHECKPOINT.json`
- `CONTEXTO_DO_PROJETO.md`
- `HISTORICO_DE_ALTERACOES.md`
- `PENDENCIAS_MIKAEL.md`

They are references/evidence, not duplicated sources of truth.

## Recovery semantics

Recovery/replay in V2.3 is state reconstruction only.

- stale revision: conflict;
- same event id with different payload: conflict;
- corrupt digest or chain: integrity failure;
- failed append leaves the input snapshot untouched;
- rollback is a candidate requiring explicit approval;
- no provider call, payment, deploy, publication or real order can be caused by
  replay.

The existing runtime recovery module remains the only path that can prepare a
real Checkpoint recovery write, and it already requires review/approval and
conditional persistence.

## Test matrix

`test_atlasquant_aion_core_v23_memory_checkpoint.py` covers:

- namespaces and seven classes;
- truth/architecture state compatibility;
- evidence-required validation;
- explicit conflict blockers;
- tenant/persona/sector/project isolation requirements;
- sensitivity and version-chain guards;
- tombstones;
- existing memory-architecture adapter;
- deterministic memory digests;
- lessons not becoming global rules;
- library provenance/evidence contract;
- deterministic checkpoint replay;
- stale writer rejection;
- idempotency and payload conflict;
- `PLANNED -> EXECUTED` rejection;
- safety-flag rejection;
- merge-patch deletion;
- rollback candidate;
- compaction;
- tamper/chain corruption;
- malformed/non-finite/oversized input;
- original-state preservation on failed append;
- inactive digest-signature hook.

The V2.2A and all pre-existing Quality/Security/Unified-Core tests remain
unchanged and are run together with the V2.3 suite.

## Safety invariants

This branch does not:

- merge or deploy;
- activate providers;
- spend money or enable billing;
- communicate externally;
- ingest documents or generate embeddings;
- enable automatic memory promotion;
- enable automatic checkpoint persistence;
- enable automatic rollback;
- enable real orders.

The V2.3 contracts report execution as disabled and preserve human approval
boundaries.
