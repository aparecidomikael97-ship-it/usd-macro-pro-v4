# AION A190 G39 — Strict semantic identity and authority scope candidate (Codex parallel review)

**Date:** 2026-10-24. Branch `lab/aion-a190-g39-strict-semantic-reservation-auth-20261024`, Draft PR #1526 stacked on G38 #1525. **LAB candidate only. No operational release.**

## Independently executed Codex review

Read-only Codex CLI on the authorized Windows machine `am12`, checkout `C:\Users\apare\AtlasQuant-G18-Windows-LAB-20261024` (G18 is **OLDER** than the current GitHub G38/G39 stack); session `01a16f92-669b-73d2-bb66-16b234a758f7`, model `gpt-6.1-sol`, process exited **0** after 90.74s. **Static reading only:** it did not execute tests, edit code, network, Worker, provider, merge or deploy. Line numbers in its report refer to G18 only; their match to G39 head is not asserted.

Codex recommended eight follow-up actions:
1. Atomic reservation independent of caller request ID and payload digest, partitioned by authenticated origin+tenant+event.
2. Cross-workspace **and cross-owner** tenant-wide uniqueness, retaining per-workspace read isolation.
3. Strict idempotent replay without silently extending prior permission TTL or altering previously staged decisions.
4. Mandatory owner/tenant/workspace scope binding in callback authority results.
5. All locally signed test permits and custody tokens remain **synthetic and untrusted** until external root verified.
6. Reliable fresh time/lease recheck after potentially delayed callbacks, not only supplied/stale `now`.
7. Distinct scoped permission for reconciliation LOOKUP vs approval of new external SEND; no blind retry on reported absence.
8. Versioned migration preserving historical rows and resolving duplicates explicitly, no silent backfill or `INSERT OR IGNORE`.

## Current real Outbox code candidate

At code/workflow SHA `45ccfd2f8d9147145e8de2d1091c73022b3f58ad`:
- Optional `ExecutionOutbox.enqueue(..., semantic_event_id_lab=...)` demands a caller asserted `business_event_id` token in the unredacted payload, then writes an exact `semantic_reservations_lab` record **within the same `BEGIN IMMEDIATE` and `COMMIT` as Outbox decision and intent**, unique on `(tenant, business_event_id)` for all owners/workspaces in the tenant. A second request alias or cross-workspace/cross-owner insertion returns a generic conflict and does not stage a second strict-mode intent; same identical request is idempotent.
- Different tenants can use the same local string without conflicts. Scoped Outbox `list()` still does not expose other workspaces' rows.
- Optional `ExecutionOutbox(..., strict_authority_scope_lab=True)` denies a missing, empty or mismatched `tenant_id`/`workspace_id` returned by authorization callback before examining send adapters. Complete fields still **do not** enable SEND without independent first-attempt witness.
- Strict options **do not silently change legacy callers**. This also means legacy writers can bypass these defenses and are **not** eligible for operation; the new table is not a live migration.
- No trusted source namespace or authoritative origin exists: two genuine source systems sharing an event string may conflict (fail-closed); a malicious origin can choose two different event IDs for one obligation (RED). Local SQLite tables and signatures do not prove real event truth or antirollback independence.
- Redacted credentials remain unsuitable as business-semantic identity; no production access to external provider or Worker was enabled.
- Older G34 schema tests count tables with `action_*`; new LAB table deliberately uses `semantic_*` and a non-destructive CREATE TABLE to preserve action schema counting. This is not approval of unreviewed migration.

## G39 targeted matrix and historical CI troubleshooting

New suites:
- `labs/a190/test_g39_atomic_semantic_lock_lab.py` (16 checks): same-ref replay, alias conflict, owner/workspace/tenant separation, rollback atomicity, reopening, legacy bypass RED, fabricated event alias RED.
- `labs/a190/test_g39_strict_authority_scope_lab.py` (12 checks): required tenant/workspace binding, wrong/blank scope, callback failure and full-scope no-send.
- `.github/workflows/aion-a190-g39-semantic-auth-lab.yml`: Ubuntu+Windows 28 G39 plus G38–G30 197 regressions = 225 distinct per OS.

First validation [#40129675083](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40129675083) **not fully green**: Windows test 13 left reopened SQLite handle open and failed temp directory removal (`WinError 32`); Ubuntu G39 28/28 passed but inherited G34 schema-count regression failed `4 != 3` due newly added `action_*` table. **Both were corrected** in follow-on commits (explicit `store.close()`; rename LAB table to `semantic_reservations_lab`), along with cross-owner tenant uniqueness enforcement. No acceptance from first CI.

**FINAL VERIFIED focused workflow [#40129939905](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40129939905): SUCCESS on both systems**, exact tested code/workflow SHA `45ccfd2f8d9147145e8de2d1091c73022b3f58ad`. Ubuntu job `120979306956`: **28 G39 + 197 G30–G38 = 225/225**. Windows job `120979306836`: **225/225**. **450 total test executions of 225 distinct tests**, with the GREEN and intentionally RED markers verified in the job logs. This report is a follow-up documentation commit; its later HEAD is not the tested code SHA. At evidence update, 12 other triggered workflows succeeded, while A184 was still queued and must not be reported as PASS.

## Nonnegotiable NO-GO

G39 is an **opt-in local contract correction, not P0 closure**. The synthetic authority still controls event naming; legacy writers bypass; cross-file databases have no global uniqueness; no source-authenticated namespace, real HUMAN_OWNER identity, independent provider receipt, separate custody or hostile-host antirollback. Fresh clock and reconciling authorization are still pending as Codex advised. A184 historical RED and security dependency audit remain; path-specific G39 checks do not constitute homologation.

**0/6 P0 homologados · HARD NO-GO · UNCERTAIN · ZERO_AUTO_RESEND · No main/merge/deploy, provider/Worker, customer data, secrets or spend.**
