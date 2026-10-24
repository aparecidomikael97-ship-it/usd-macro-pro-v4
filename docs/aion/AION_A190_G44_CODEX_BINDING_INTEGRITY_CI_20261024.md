# AtlasQuant AION A190 G44 — Scoped Outbox/Decision/Effect local integrity admission LAB

**Date:** 2026-10-24. **Draft PR #1531**, stacked on G43 Draft #1530. G44 candidate exact code/workflow SHA `41765b107abbf954cd6173fbe20e330b5fc4d1af`; code remains **LAB-only, opt-in**. No merge to main, deploy, Worker, customer/provider data, external send, credentials or spend.

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

`.github/workflows/aion-a190-g44-binding-integrity-lab.yml` runs **31 new G44 + 339 inherited G30–G43 = 370 distinct tests per OS, 740 cross-platform executions if both pass**. Candidate [G44 CI #40135351231](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40135351231), code/workflow SHA `41765b107abbf954cd6173fbe20e330b5fc4d1af`: Ubuntu and Windows jobs were still queued at this document creation. Do **not** claim successful tests until checking both jobs and original tested SHA; this is a separate evidence-doc commit.

## Outstanding RED

- Opt-in local integrity gate is not a trusted provider receipt, authenticated origin/HUMAN_OWNER identity, durable independent monotonic antirollback custodian, host-proof crash recovery, or distributed exactly-once first SEND guarantee.
- A structurally consistent old SQLite file can pass local checks after the host rolls back to a previous snapshot. No automatic SEND if state was uncertain.
- Historical A184 canonical Security/Quality and dependency audit remain independent. Last known issues included `pip-audit` vulnerabilities in pypdf and Pillow, prior BASE failures and missing external six-P0 evidence. Path-specific passing CI is not homologation.
- Schema version admission/fingerprint, full scope-wide orphan consistency, multi-connection concurrent actor qualification and recovery migration approvals remain distinct blockers.

**0/6 P0 HOMOLOGATED · HARD NO-GO · UNCERTAIN · ZERO_AUTO_RESEND.**
