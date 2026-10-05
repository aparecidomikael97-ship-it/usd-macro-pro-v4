# AION V2.8 — Cross-contract readiness and authority inversion

## Baseline and scope

Exact starting SHA: `f48434977a76daf0865da9881d4f7439ef3d5485` (PR #581).
Head branch: `agent/codex-aion-v28-cross-contract-readiness-redteam-20261004`.
Draft base: `integration/aion-core-v27-reconciliation-20261004`; never main.
No Trader, shared workflows, durable stores, memory/recovery implementation,
TaskGraph or role-authority changes. No collectors, loaders or second authority.

## Executable first checkpoint

`test_atlasquant_aion_v28_cross_contract_readiness_redteam.py` was created before
extended inspection. Its first 21 tests passed. The expanded pre-patch run had
**7 failures / 208 passes**, reproducing two functional defects:

1. A recovery receipt could contain a valid but older/newer journal than the live
   journal/audit evidence, yet all domains and readiness became CONFIRMED.
2. One missing domain produced remediation requesting all five subsystems.

Minimal fixes carry the identity returned by the existing journal validator into
recovery provenance, compare recovery with both journal views, and name only the
non-good domains using the existing health classifier. No new validator or health
classification vocabulary was introduced. Optional receipt head/revision claims
remain checked against actual validated content, including exact types.

## Real contract path

| Stage | Authority / mutability / persistence |
| --- | --- |
| Existing Admin `load_runtime_checkpoint` | Existing loader; may read runtime storage. It is not a health collector. |
| Resident raw runtime checkpoint | Mutable in-memory input; existing persisted source. Only this domain is currently resident for health. |
| `build_loaded_runtime_health_evidence` | Read-only derived bridge; replaces caller `system_context.aion_core_health`. Never uses a seeded/dirty working copy as health proof. |
| `LoadedEvidence` / `build_core_health_evidence` | Trusted Python boundary; bounded copies, explicit scope, component freshness and existing pure validators. Not a client JSON attestation API. |
| Normalized statuses / provenance | Derived independent snapshot, not persisted. No automatic mutation, clock or I/O. |
| `core_health_snapshot` | Sole existing integrity classifier; explicit failures dominate; partial evidence remains UNKNOWN. |
| `build_master_status_board` / `status_rows` | Derived readiness/display. Proven completeness/counters required; observed blockers remain visible. |
| Admin rendering | Presents state, evidence and next action; grants no execution permission. |

Canonical source contracts: journal and audit use `verify_request_journal`;
master checkpoint uses `reconstruct_checkpoint`; legacy checkpoint uses
`checkpoint_integrity_report`; memory uses `MemoryContractRecord`, recreation and
`operational_decision`; recovery validates its embedded canonical journal without
running recovery; counters require validated V2.4 TaskGraphs and a complete scoped
resident inventory. Legacy operating tasks, continuity missions, durable summaries,
live EVENT_JOURNAL_V1, business audit and UI dictionaries cannot certify these.

## Cross-contract executable matrix

| Attack | Result / proof |
| --- | --- |
| Four good + one UNKNOWN; three good + two UNKNOWN; one good + four UNKNOWN | 20 combinations remain UNKNOWN; no majority vote. |
| Recovery older/newer than live journal | MISMATCH / BLOCKED after patch. |
| Same revision / different canonical heads | Forked journals rejected across recovery/live or audit. |
| Same digest claim / altered payload | Existing journal validator rejects the content. |
| Owner/tenant/workspace/ecosystem/project/sector conflicts | 30 domain/scope cases fail closed with CROSS_SCOPE. |
| Any nonempty subset stale among current domains | 31 combinations cannot become CONFIRMED. |
| Current evidence plus expiry exactly now | Each of five domains stays STALE / UNKNOWN; no rescue. |
| Each failed domain among good domains | DEGRADED / BLOCKED; quarantine/rejection/corruption covered also by V2.7. |
| Legacy/schema/signature/verified/authority names | 54 cases cannot become CONFIRMED. |
| Multiple sources same/divergent/bad/unknown/cross-scope | 30 cases plus reversal: no first/last winner or silent merge. |
| Nested claims at eight caller paths | Real Admin replaces claims with resident-derived health; existing loader budget unchanged. |
| Unproven counts, malformed numeric types, bool, enum, decimal, fraction, huge integer | No proof upgrade; unproven zeros render “não comprovado”. |
| Real V2.4 PREPARED/BLOCKED/WAITING_APPROVAL graphs | Exact derived counters; blockers override integrity OK. |
| Security flags | 35 domain/flag cases cannot echo execution permission. Unsupported fields are not promoted into authority. |
| TOCTOU | Six source mutations do not change previously calculated output; rebuild catches cross-scope. |
| Determinism | 100 identical builds, stable sorted-JSON digest, input preservation and reversed keyword order. |
| Validator exceptions | Declared canonical ValueError becomes INVALID/BLOCKED for journal/checkpoint/memory. |
| Maximum health / authority inversion | CONFIRMED cannot permit eight write/external tools through real local executor preflight. |
| Side effects | Full pipeline and real Admin-boundary tests patch file access/write, network, subprocess, stores, persistence, recovery and provider calls to fail if invoked. |

The final V2.8 file contains **305 passing cases**. Related V2.7 covers hostile
Mappings/subclasses/conversion hooks, temporal boundary cases, canonical tampering,
unsafe receipts and protected storage behavior; those suites are rerun as regression.

## Authority-inversion trace

Repository consumer search found:
- Admin: rebuilds canonical resident health before the board; rendering, secretary
  and administrative recommendations consume observations.
- `atlasquant_aion_local_executor._status_read`: returns a board through an existing
  local allowlisted read tool. Tool preflight uses explicit access/admin/approval,
  feature policy and allowlist, not health CONFIRMED. Eight hostile tool attempts
  with maximum health remain BLOCKED before any handler.
- `atlasquant_aion_admin_copilot._status_board_recommendations`: converts attention
  into priorities/recommendations, not approvals.
- `atlasquant_aion_executive_pulse`: prioritizes unresolved observations; explicitly
  does not substitute external production validation.
- `atlasquant_aion_local_traceability`: source metadata only.

No consumer was found granting provider/broker/billing/write permission from Core
health. This is a repository trace plus executable preflight tests, not a proof
about unknown external applications.

## False positives discarded and limits

Two test setup errors were corrected through canonical factories: PLANNED cannot
transition directly to BLOCKED, and a disabled provider capability is BLOCKED,
not WAITING_APPROVAL. No production contract was weakened to make those tests pass.

Checkpoint revision, MemoryContractRecord version and TaskGraph revision are
independent namespaces. Comparing their numeric values would invent a global
clock and reject the legitimate baseline (checkpoint revision 0 / memory version 1).
No authenticated cross-domain snapshot epoch or global snapshot digest exists here.
The patch binds only the actual shared request-journal lineage. **CONFIRMED is
structural observation, not proof of an atomic global snapshot, origin authentication,
complete physical inventory or freshness where no temporal contract exists.**

Source names/SHA/digest labels do not authenticate scope or origin. LoadedEvidence
is a trusted application assertion; an arbitrary trusted Python caller can create
structurally valid objects. The real Admin boundary does not trust client claims.
Unkeyed hashes cannot attest authorship. Evidence without a temporal contract is
NOT_EVALUATED; no TTL is invented. Arbitrary programming failures outside declared
validator errors are not claimed to be recoverable health evidence.

Admin health still has checkpoint only: journal, audit_chain, memory and recovery
remain UNKNOWN, and counters remain unproven. No data was manufactured to remove
UNKNOWN. A full atomic cross-contract attestation would require a separately
specified canonical epoch/provenance contract, outside this patch.

## Validation and delivery

Validation: V2.8 **305 passed**; required 11-file block **1,143 passed / 1 skipped**;
broad 192-file regression **3,672 passed / 4 skipped / 737 subtests passed** in
150.10 seconds. Skips are unavailable Windows symlink creation, including the
V2.7 durable-store suite; no assertion or contract was weakened. Test logs are
saved beside the checkout (`AION_V28_BASELINE.log`, `AION_V28_NEW_FINAL.log`,
`AION_V28_REQUIRED.log`, `AION_V28_REGRESSION.log`).
See the delivery report beside the checkout for commit SHA, Draft PR and workflow status. Shared workflows were left untouched;
their branch filters may not trigger on this integration base. Prior green base
runs are not evidence of green runs for the new head.

ZERO MERGE · ZERO DEPLOY · ZERO PROVIDER · ZERO BILLING · ZERO PAID API ·
ZERO REAL ORDER · ZERO EXTERNAL EXECUTION · ZERO AUTO-REPAIR.
Health observation != authorization. CONFIRMED health != execution permission.
