# AION Core V2.4 — Security / Observability Hardening Audit

Baseline audited: `e0ae719ee4b66403ea86e66fe4a308dcccd923f5`.

Scope: AION Core only. No Trader UI, Business UI, provider activation, billing,
external communication, real trading, merge or deployment is part of this work.

## Evidence-based disposition of preliminary findings

| Finding | Disposition | Evidence / action |
| --- | --- | --- |
| Journal partial write / crash | MITIGATED_ALREADY | `UnifiedJournalStore._atomic_write` writes a temp file, flushes + fsyncs it, atomically replaces the target and fsyncs the directory. Existing journal-store tests already inject crash windows and verify recovery/quarantine. No duplicate checksum layer was added. |
| Role forgery / authority escalation | MITIGATED_ALREADY | Authority resolves only the eight official role IDs and unknown roles fail closed. Exact approval remains `is True`. Added explicit confusable/unknown-role regression coverage. |
| Durable-task concurrency | DESIGN_BOUNDARY / PARTIALLY_MITIGATED | Durable task helpers are pure state transformations. A mutex inside `validate_transition()` would not protect independent processes and would be misleading. The existing revision contract is optimistic concurrency control; this branch adds a regression proving a stale second writer is rejected by `upsert_durable_task(..., expected_revision=...)`. Any future shared physical task store must enforce the same compare-and-swap contract atomically. |
| Runtime critical flags require a thread lock | FALSE_POSITIVE | Request processing builds local immutable/frozen response state; the security defaults are not shared mutable globals. Regression confirms response defaults remain fail-closed. |
| Separate audit ledger required | NOT_REQUIRED | The unified journal remains the integrity/audit chain. Creating a second ledger would introduce competing authorities. Observability remains a redacted operational view rather than a second source of truth. |

## Hardening added in this branch

### Read-only Core health snapshot

`atlasquant_aion_observability.core_health_snapshot()` exposes bounded local
health state without probing any provider. It reports:

- core/schema versions;
- journal/checkpoint/recovery/memory/audit-chain status;
- pending, blocked, waiting-approval and ready-handoff counts;
- last recovery/checkpoint references;
- redacted observability summary;
- derived integrity state: `DEGRADED`, `OK`, or `UNKNOWN`.

The function never upgrades absent evidence to healthy. `OK` is returned only
when every supplied subsystem status is explicitly good. Any status containing
a corruption, mismatch, failure, block, quarantine, tamper, invalid or unsafe
marker produces `DEGRADED`.

The snapshot is state-only and always carries:

- `health_snapshot_is_read_only=True`
- `external_action_executed=False`
- `execution_allowed=False`
- `executes_provider_call=False`
- `executes_billing=False`
- `real_orders_enabled=False`

### Regression / adversarial coverage

A dedicated V2.4 test verifies:

- Unicode-confusable and unknown roles fail closed;
- approval requires exact boolean `True`;
- stale durable-task writers are rejected at the revision commit boundary;
- nested secret families are redacted;
- health evidence fails closed on UNKNOWN and degrades on tamper/mismatch;
- runtime response defaults remain non-executing.

Existing journal-store crash and quarantine suites remain authoritative for
physical persistence failure windows; this branch does not duplicate them.

## Concurrency boundary

The durable-task module currently transforms caller-provided snapshots. It does
not own a shared physical task database. Therefore process-local locking inside
a pure transition validator cannot guarantee cross-process uniqueness. The
security contract is:

1. read authoritative task + revision;
2. derive the next snapshot locally;
3. commit through an authoritative persistence boundary with expected revision;
4. reject stale revision;
5. never execute external work during recovery/replay.

If a durable physical task store is added later, the compare-and-swap must be
atomic in that store (transaction / file lock / database conditional write).
Do not replace this requirement with a Python-only mutex.

## Remaining risk

> Status update — 2026-10-05 / Draft PR #710: a physical SQLite CAS repository
> now implements this previously documented persistence requirement in staging.
> It uses scope-bound rows, canonical payload digests, `BEGIN IMMEDIATE`,
> revision-conditional UPDATE, real two-process race tests, crash-window tests
> and a Checkpoint Mestre projection. This update does not activate production
> persistence or execution. The text below is preserved as the original audit
> finding that motivated the closure work.

The current in-memory/list `upsert_durable_task` proves the revision semantics,
but a future multi-process persistent task repository must implement the CAS
atomically. This is an architectural persistence requirement, not evidence that
`validate_transition()` itself is unsafe.

## Invariants

This hardening does not authorize any external side effect. It does not call
providers, spend money, communicate externally, merge branches, deploy
production or enable real orders.
