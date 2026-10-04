# AION V2.8 — Global snapshot consistency / evidence epoch

**CONSISTENCY ENVELOPE IS NOT AN ATOMIC SNAPSHOT. ATOMICITY REMAINS NOT PROVEN.**

Baseline: `32645642aa12ba3962710ae154c23deff1c47171`, validated head of #583.
Branch: `agent/codex-aion-v28-global-snapshot-consistency-20261004`.
Draft base: `agent/codex-aion-v28-cross-contract-readiness-redteam-20261004`.

## Problem and first checkpoint

Health could be CONFIRMED without explicitly stating that global atomicity was
unproven, and the board had no observation-window/completeness distinction.
Before extended architecture work, four executable failing atomicity tests were
written, run, committed and pushed (`1a5626b18`). An expanded contract baseline
reproduced 74 failures / 7 passes due principally to the absent envelope.
This absence was a bounded design gap; the implementation adds a derived view,
not a coordinated snapshot mechanism.

Owner: **AION Core Health**. Authority: **READ_ONLY_DERIVED_EVIDENCE**.
Schema: `ATLASQUANT_AION_CONSISTENCY_ENVELOPE_V1`.
Can describe observations, detect existing canonical contradictions and report
completeness. Cannot approve, authorize, execute, persist, restore, repair or retry.
No new module, collector, loader, transaction, global revision, lock, database,
write barrier or two-phase commit was added.

## Resident path and API

Existing Admin runtime load -> raw resident checkpoint ->
`build_loaded_runtime_health_evidence` -> `build_core_health_evidence` -> existing
pure domain validators -> normalized health plus `consistency_envelope` ->
`core_health_snapshot` / `consistency_envelope_view` -> Master Status Board ->
Essential and full Admin renderers.

Public adapter APIs remain `LoadedEvidence`, `HealthEvidenceError`,
`build_core_health_evidence` and `build_loaded_runtime_health_evidence`, with
`consistency_envelope_view` added for bounded display verification.
The latter verifies the version/digest and recomputes envelope fields against the
normalized payload. It is not an external JSON ingestion/attestation API and never
turns an envelope back into raw evidence. No duplicate-key JSON loader is exposed.
Raw evidence is still validated only by the canonical domain validators.

## Physical/logical identity map

| Domain | Existing canonical contract | Identity represented |
| --- | --- | --- |
| journal | `verify_request_journal` | scoped request, revision, head digest, bounded content fingerprint |
| audit_chain | same request journal validator | revision/head must agree with journal |
| recovery | existing receipt flags and embedded validated journal | actual linked revision/head, checked optional claims, receipt fingerprint |
| checkpoint | `reconstruct_checkpoint` or legacy `checkpoint_integrity_report` | independent revision/state digest where present; bounded resident document fingerprint |
| memory | typed `MemoryContractRecord`, canonical recreation and operational decision | independent version, bounded record fingerprints; no raw content in output |
| mission | validated V2.4 TaskGraphs and complete scoped inventory | bounded inventory fingerprint and derived counters; legacy missions do not certify this |

Source refs are bounded/redacted descriptors, never authority. SHA/digest labels
outside these canonical domain inputs do not create cross-binding. Runtime Git
SHA and recovery candidate SHA are not a global epoch; no new SHA loader/binding
was invented. Source refs and canonical document identities participate in the
fingerprint; a content-identical observation is not authenticated as originating
from a physical source merely by possessing its SHA.

Observations use supplied aware `LoadedEvidence.as_of` and component
`temporal.timestamp/as_of`, normalized to UTC. Event times and record creation
times are not silently relabeled as observation times. No implicit clock or TTL.

## State model and dimensions

Expected domains are fixed: journal, checkpoint, recovery, memory, audit_chain,
mission. Domain lists are bounded and ordered by this contract, not caller order.
`present_domains` describes documents fingerprinted in this build; it does not
certify them. `verified_domains` means full canonical structural validation, not
positive health/currentness. `unknown_domains` is the complement of that proof.
Degraded/stale/mismatch lists are explicit and may overlap.

- **CONFIRMED:** all six structural domain proofs complete, mandatory request
  lineage coherent, explicit expected scope fully bound, all supplied component
  freshness evaluations FRESH and observation labels equal.
- **PARTIAL:** some canonical proof exists, but a domain/binding/time proof is
  missing, stale or temporally mixed.
- **UNKNOWN:** no sufficient canonical structural proof exists. Attractive legacy
  documents alone do not even certify PARTIAL consistency.
- **MISMATCH:** an explicit canonical contradiction exists; it dominates completeness.

Dimensions: `lineage_consistency`, `scope_consistency`, `temporal_consistency`,
`integrity_consistency`, `snapshot_complete`, `temporally_mixed` and observation
window. Existing observability remains the sole integrity classifier.
`CONSISTENCY CONFIRMED` is about the reported observations and required bindings,
not healthy/approved/execution-ready. A canonically valid QUARANTINED memory can
produce coherent observations with DEGRADED health and BLOCKED readiness.

`snapshot_complete` means the required six structural proofs/inventory assertions
are supplied; freshness and expected-scope certainty are separate dimensions.
**`snapshot_atomic=False` always**, in adapter payload, envelope, health snapshot
and displayed truth. No caller input can make it True.

## Matrices

| Health/readiness | Consistency | Complete | Atomic | Execution |
| --- | --- | --- | --- | --- |
| CONFIRMED | CONFIRMED (full supplied scoped/current observation) | True | False | False |
| CONFIRMED | PARTIAL (missing observation/time proof) | True | False | False |
| UNKNOWN (missing domain) | PARTIAL | False | False | False |
| DEGRADED / BLOCKED (QUARANTINED memory) | CONFIRMED (coherent record) | True | False | False |
| DEGRADED / BLOCKED (lineage contradiction) | MISMATCH | False or True structural inventory | False | False |
| UNKNOWN (no canonical inputs) | UNKNOWN | False | False | False |

A client cannot claim health CONFIRMED with missing required domain proof merely
by attaching an envelope. Current health requires all five integrity domains and
proven counters; a domain-missing Complete False / health CONFIRMED combination is
therefore intentionally not fabricated. Complete and atomic are not synonyms.

| Request lineage | Result |
| --- | --- |
| journal N / audit N / recovery N, same canonical head | CONFIRMED lineage |
| journal/audit N, recovery N-1 or N+1 | MISMATCH |
| same revision, different head | MISMATCH |
| any triad member missing, other canonical members present | PARTIAL lineage |
| triad coherent, checkpoint/memory/mission missing | lineage CONFIRMED, global PARTIAL |

Independent revision numbers (checkpoint 7 / memory 7, or checkpoint 100 / memory
27) can coexist with the journal. Equal numbers never prove a shared global epoch.
Scope conflicts in owner/tenant/workspace/ecosystem/project fail closed through
existing scope checks. Without explicit expected scope, scope certainty UNKNOWN,
even if compatible identity could be inferred from supplied content.

| Temporal observation | Result |
| --- | --- |
| same aware labels, all component contracts FRESH | CURRENT observation dimension; still non-atomic |
| skew 1s / 30s / 5m / 1h / 1d | exact earliest/latest; MIXED and global PARTIAL |
| any material stale source | STALE; never globally CURRENT |
| missing/invalid/naive/future labels | UNKNOWN/unproven temporal dimension |
| no temporal contract | no invented TTL; PARTIAL temporal proof |

There is no simultaneity SLA. Equal observation labels do not prove coordinated
physical capture; different labels are exposed without an arbitrary threshold.

## Epoch/digest semantics and reuse

`evidence_epoch` is SHA-256 over explicit schema, normalized scope/expected scope
and domain descriptors (content identity, source ref, independent revision/head,
validation/state, completeness, observation label and evaluated freshness).
`snapshot_digest` is SHA-256 over the complete derived envelope including the epoch,
excluding only the snapshot_digest field itself. Canonical JSON uses sorted keys,
ASCII escapes, fixed separators and no NaN. Format: `sha256:<64 lowercase hex>`.

Same evidence set -> same hashes; dictionary order -> unchanged. Changed canonical
content, scope, failure/freshness state or source descriptor -> changed hashes.
Display events and the build clock itself are not envelope identity; the explicit
clock affects the digest only through evaluated freshness/observation validity.
These hashes detect observation change, not signature/authority/authentication.

Old envelopes are independent copied outputs. Mutating caller objects cannot
retroactively change them. Rebuild always derives from actual supplied canonical
inputs; it never consumes a prebuilt envelope as health evidence. Future schemas,
legacy synced/healthy dictionaries, malformed digests, altered or rehashed fields
inconsistent with normalized evidence fail closed for display. Real Admin replaces
nested/root caller claims using its existing resident load budget.

## Reproduced defects and bounded fixes

- Missing explicit atomicity flag (4 initial failures): fixed end-to-end invariant.
- Missing envelope/UI distinction (contract baseline and 2 Admin renderer failures):
  bounded derived envelope and visible Essential/full captions.
- Receipt identity claim overrode computed fingerprint (1 failing red-team case):
  only pure memory-validator metadata can supply its internally computed digest;
  receipt claims cannot override the locally computed identity.
- Fractional checkpoint revision and memory version coerced to canonical integers
  (4 failing cases): adapter requires exact integers before canonical validation;
  protected domain implementations remain unchanged.
- Partial/mismatch guidance absent (2 failing cases): board names the actual
  missing/time/binding reason and asks to reconstruct resident observation.
- Legacy-only observations incorrectly labeled PARTIAL (1 failing case): no
  canonical proof means UNKNOWN.
- Rehashed malformed metadata/scope could crash the display reader (2 failing
  cases): exact descriptor mapping checks return UNKNOWN without disrupting board rendering.

False-positive test setups corrected: blank wrapper as_of is absent when a valid
component timestamp is supplied; the invalid-time case now removes both sources.
Memory factory accepts canonical construction fields, not dataclass updated_at.
Rehashing an unchanged empty unknown_domains list is not an attack; the tampering
case now actually changes the inventory. No production rule was relaxed.

## Authority and effects

Actual local executor probes deny protected/write tools despite perfect envelopes.
Provider gates require exact feature/approval booleans; envelope objects are not
approval. Provider RBAC/capability is owned by upstream Guardian/tool contracts,
not manufactured as a new provider parameter here. Pure recovery preflight still
requires its own confirmed runtime/candidate contract. Neither BLOCKED tasks nor
CONFLICTING memory are mutated by observation building.

Guards instrument builtins.open; Path open/read/write/rename/replace; socket;
requests Session.request; subprocess; journal store construction/recovery;
taskgraph persistence/recovery; checkpoint restore; memory load/save where exposed;
and provider entry points through the prior whole-chain guard. Full envelope ->
health snapshot -> Status Board -> both Admin renderers executes with zero I/O.
Real Admin boundary tests stub existing loaders and prove one runtime load, one
memory summary, one account lookup; no additional health/consistency loader.
The entire legacy Admin application still has its existing I/O outside this chain.

## UI truth

Core row retains independent health/readiness semantics and adds consistency,
complete and `snapshot_atomic=False`. Both Admin views always show Core integrity
and global snapshot consistency, the unproven atomicity disclaimer, actual time
range when available and bounded reason/rebuild guidance. No universal
system_ready/all_good green light, automatic refresh, authorization or hidden fetch.

Real Admin remains checkpoint-only. Its consistency is PARTIAL; snapshot_complete
False; scope/time proof incomplete; journal/audit/memory/recovery UNKNOWN and
mission counters unproven. This is reported rather than repaired or filled.

## Validation, bounds and limitations

The new red-team file has the requested ten contract classes and additional
strict-type/UI/authority/bounds probes. 100 repeated builds, two-thread equality,
two independent process epochs, JSON roundtrip and 1,000-build timing are executed.
The smoke measurement is about 1.4–1.9 seconds per 1,000 small fixture builds,
not a scientific benchmark or performance guarantee. Fixture envelope <16 KB.
Input limits remain 2 MB, depth 24, 20,000 nodes, 64 domain inventory rows; envelope
has a fixed six-domain inventory and digests rather than raw payload copies.
New suite: **232 passed**. Required 12-file block: **1,375 passed / 1 skipped**.
Security adversarial/audit/local matrix: **64 passed / 112 subtests passed**.
Final broad regression across **193 files: 3,904 passed / 4 skipped / 737 subtests passed**
in 133.72 seconds. The four skips are unavailable Windows symlink creation in
existing developer intelligence, journal store/governance and V2.7 durable-store
fixtures. No assertion was weakened. Delivery details are recorded in the report
alongside the checkout.
Logs are preserved as `AION_V28_GLOBAL_*` beside the checkout, including initial
failures and final validations. Tests overlap across blocks; counts are not additive.

The trusted Python provenance boundary is not cryptographic attestation. It does
not authenticate source authorship or physical completeness. Supplied observation
labels are claims by trusted application code, not physical transaction evidence.
Pure copies/validation do not lock concurrent callers: this is explicitly not an
atomic multi-object freeze or an ongoing freshness monitor. Declared validator
errors fail closed; arbitrary programmer failures outside declared errors are
not claimed recoverable. No external application is certified by these tests.

If true atomicity is ever required, a separately owned canonical snapshot/epoch
protocol with coordinated capture and independently verified origin/bindings must
be specified first. It is not implemented or authorized by this branch.

ZERO MERGE · ZERO DEPLOY · ZERO PROVIDER · ZERO BILLING · ZERO PAID API ·
ZERO REAL ORDER · ZERO EXTERNAL EXECUTION · ZERO AUTO-REPAIR.
