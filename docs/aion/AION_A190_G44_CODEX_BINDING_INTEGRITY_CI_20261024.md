# AtlasQuant AION A190 G44 — Scoped Outbox/Decision/Effect local integrity admission LAB

**Date:** 2026-10-24. **Draft PR #1531**, stacked on G43 Draft #1530. G44 **final tested code/workflow SHA `9e5d380d96ca26ef6bea10e048dd6e52aee3d222`**; code remains **LAB-only, opt-in**. No merge to main, deploy, Worker, customer/provider data, external send, credentials or spend.

## Independent Codex actually executed

Codex CLI v0.163.0-alpha.11.2, model `gpt-6.1-sol`, ran **read-only** on the connected Windows desktop `am12`; checkout `C:\Users\apare\AtlasQuant-G18-Windows-LAB-20261024` (**older G18** — not latest G43/G44). Session `01a16fd5-2957-77c0-85eb-f20a48e0187e` completed with **exit code 0 in 104.95 s**. Codex read code/static tests; it **did not inspect this newest diff**, edit code, execute tests, contact a provider, invoke Worker, merge or deploy.

Codex priority recommendations:
1. Every decision has exactly one Outbox; Outbox exactly one decision; scoped effect ledger exists iff local confirmation.
2. Owner/tenant/workspace must bind across each table and never expose a cross-scope decision through a partial JOIN.
3. Recompute version-matched payload SHA-256, deterministic idempotency key and decision ID from persisted canonical fields.
4. Reject malformed and duplicate-key JSON, nonobject payloads, silently coerced field types and unknown versions.
5. Validate aggregate sequence, scoped predecessor constraints, leases/timestamps conservatively; a historical `action_outbox.data.state=PENDING` is not independently current state.
6. Ledger state, effect ref/confirmed_at and scope must match. A local matching receipt remains untrusted commercially.
7. Recovery schema must avoid triggers/views and use read-only, scoped auditing. No auto repair or migration in audit path.
8. A coherent restored local SQLite snapshot can still omit a subsequently confirmed external effect; independent antirollback custody is required.

These are **static recommendations against G18**, not proof that G44 was tested by Codex.

## Current-code candidate

- Root `atlasquant_aion_outbox_binding_lab.py`: pure `binding_issue_lab(db,key,scope)` checks scoped outbox, decision, JSON, payload digest, deterministic idempotency material, decision ID derivation, semantic reservation consistency, outbox state/attempts and effect ledger's scope/ref/time. Validating a hash ensures local consistency **only**. Duplicate JSON keys, multiple Outboxes pointing to one decision and orphan decisions are also detected.
- `audit_binding_readonly_lab(path,owner,tenant,workspace)`: independent SQLite `mode=ro` + `query_only=ON` + single read transaction; it does not instantiate schema-writing Outbox/store and returns classification codes/counts without business payload. It detects scoped orphan effect/decision records.
- `ExecutionOutbox(...,strict_binding_integrity_lab=True)`: explicit opt-in; guards before claim, dispatch, after authorization callback, before/after send property getter/callback, before reconciliation property getter and result admission, and within the transaction for confirmation/ledger. On contradiction fail closed with `G44_BINDING_INTEGRITY_DENIED:...`, no adapter and no repair/retry. Default first-send quarantine remains.
- Scoped Outbox direct retrieval/listing and claim joins now require `d.owner=o.owner`, `d.tenant=o.tenant`, `d.workspace=o.workspace`. Corrupted cross-scope decisions do not leak through the normal direct-read projection.
- **No physical schema migration**, trigger, view, new persistence/claim authority, external witness, unverified binary or automatic backfill; older writers remain able to bypass optional integrity gate.

## G44 synthetic tests and evidence state

`labs/a190/test_g44_binding_integrity_lab.py` has **31 new** tests covering:
- expected baseline local identity/digest, cross-scope decision refusal and no data leak;
- corrupted decision JSON/field values, modified digest/material, duplicate JSON keys;
- malformed Outbox JSON, illegal state, negative persisted generation;
- confirmed without ledger, foreign ledger scope, conflicting receipt reference/time, ledger on nonconfirmed row;
- missing/orphan/duplicate decision reference detection, semantic reservation mismatch;
- authorization callback reentry and invalid data preventing claim or adapter property lookup;
- standalone mode=ro report privacy/zero writes and explicit **RED**: a valid local hash does not prove a commercial event.

**Historical superseded candidate**: workflow [G44 #40135351231](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40135351231) at old SHA `41765b107abbf954cd6173fbe20e330b5fc4d1af` had 31 new cases, with one fixture error under Windows after intentionally corrupting decision JSON. The harness was fixed. **This old run is NOT final validation.** Latest G44 workflow uses 39 new G44 tests plus 339 inherited, as verified below.

## Second Codex review of the ACTUAL G44 branch and verified fixes

Unlike the first G18 static audit, the **second read-only Codex CLI** actually reviewed the clean detached HEAD `3e7e8a440536a9b7340dff57a5dc337151ef6848` on the user's Windows computer at `C:\\Users\\apare\\AtlasQuant-G44-Audit-LAB-20261024`. Codex model `gpt-6.1-sol`, session `01a16fe0-450c-7120-9b98-2a342d802ca4`, **exit 0 in 77.55 seconds**; no edits, tests, Worker/provider, merge or deployment were done by Codex. Later code changes were informed by its static findings, but Codex did **not** re-review the final patched HEAD.

It found **ten** candidate gaps. Four high-priority findings have been corrected and tested on the local Windows checkout:
- Original producer JSON has `ensure_ascii=False`, while G44 auditor omitted this; align canonicalization for Unicode payload. `G44_UNICODE_GREEN` passed.
- G44 must revalidate after the potentially executable `adapter.reconcile` property getter before invoking callback. `G44_RECONCILE_GETTER_GREEN` passed.
- The claim predecessor query used INNER JOIN; an earlier decision with no Outbox row could disappear and incorrectly release later work. Use scoped LEFT JOIN and block when predecessor is missing. `G44_ORPHAN_PREDECESSOR_GREEN` passed.
- Even without G42 strict opt-in, G44 strict mode must preserve first confirmation timestamp/effect ledger upon identical replay. `G44_RECONFIRM_GREEN` passed.

Additional safety contracts applied: version-bound decision `schema` and `grants_authority=False` admission, and correctly scope-qualified local orphan-detection joins. Remaining independent Codex observations stay OPEN: versioned physical SQLite schema/constraints admission, G43 auditor scope/duplicate-key hardening, authorization-critical reauth field tampering without independent sealed binding, WAL sidecar write guarantees, and tests for eligible reconciliation after further reentrancy. These are not cleared by the passing targeted suite.

**Intermediate Codex refinement SHA** `2b8b24440e4b858981e05f49a2e31a2e055ca15d` passed 37/37 new tests and 339/339 regressions on local Windows. Its GitHub run [#40135893785](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40135893785) was superseded by the final predecessor-integrity fix. Do not merge evidence from different SHAs.

## Third Codex review: predecessor terminal integrity, and final LAB repair

A **third actual read-only Codex** ran on the **updated G44 checkout SHA `2b8b24440e4b858981e05f49a2e31a2e055ca15d`** (not old G18), at the isolated detached Windows worktree, session `01a16fe6-030a-7023-bb60-f272abca75d2`. It **completed exit 0 in 46.50 seconds**, without modifications, tests, Worker/provider, credentials, merge or deploy. The review confirmed the four prior fixes by static inspection but found another concrete blocker:

- A predecessor in terminal state `CONFIRMED` could lack its `action_effects` row, yet `claim_next` permitted the successor because its anti-overtake predicate only inspected the predecessor's state.
- The opt-in G44 claim now verifies **every earlier decision's Outbox/Decision/Effect binding inside the same BEGIN IMMEDIATE transaction** before reserving the selected successor. Invalid or missing receipt/ledger refuses advancement; a truly consistent confirmed predecessor still permits claiming.
- Added `test_38_terminal_predecessor_missing_effect_denies_successor` and `test_39_consistent_confirmed_predecessor_allows_successor_claim` with explicit proof markers. Both **passed on local Windows**.

**FINAL VERIFIED:** exact code/workflow SHA `9e5d380d96ca26ef6bea10e048dd6e52aee3d222`. Local Windows isolated checkout: **39/39 new G44 + 339/339 inherited G30–G43 PASS = 378/378**. [G44 GitHub Actions #40136260759](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40136260759) **SUCCESS**: Ubuntu job `120998306465` **378/378**, Windows job `120998306653` **378/378**, **756 executions of 378 distinct tests**, both mandated terminal-predecessor GREEN markers checked in log. This report was committed later and is NOT part of that tested source SHA. Separate [A184 #40136260770](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40136260770) was still **queued** at final G44 focused-CI validation; do not assert global Security/Quality/P0 homologation.

## Outstanding RED

- Opt-in local integrity gate is not a trusted provider receipt, authenticated origin/HUMAN_OWNER identity, durable independent monotonic antirollback custodian, host-proof crash recovery, or distributed exactly-once first SEND guarantee.
- A structurally consistent old SQLite file can pass local checks after the host rolls back to a previous snapshot. No automatic SEND if state was uncertain.
- Historical A184 canonical Security/Quality and dependency audit remain independent. Last known issues included `pip-audit` vulnerabilities in pypdf and Pillow, prior BASE failures and missing external six-P0 evidence. Path-specific passing CI is not homologation.
- Schema version admission/fingerprint, full scope-wide orphan consistency, multi-connection concurrent actor qualification and recovery migration approvals remain distinct blockers.

**0/6 P0 HOMOLOGATED · HARD NO-GO · UNCERTAIN · ZERO_AUTO_RESEND.**
