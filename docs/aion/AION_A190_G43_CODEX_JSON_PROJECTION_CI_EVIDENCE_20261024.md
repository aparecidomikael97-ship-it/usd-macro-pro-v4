# AION A190 G43 — Outbox JSON projection: dry-run, strict commit and independent read-only audit

**Date:** 2026-10-24. G43 Draft PR #1530 stacked on G42 Draft #1529. LAB-only branch `lab/aion-a190-g43-outbox-projection-dryrun-20261024`, **never merged or deployed**.

## Evidence from actual parallel Codex audit

Codex CLI v0.163.0-alpha.11.2, model `gpt-6.1-sol`, ran in **READ-ONLY** mode on the connected authorized Windows desktop `am12`, directory `C:\Users\apare\AtlasQuant-G18-Windows-LAB-20261024` (OLDER **G18**, not current G42/G43). Session `01a16fcb-a018-7c71-8714-9c3d3734c100`, **completed exit 0 in 97.60 sec**. It inspected source/tests only: no code edits, tests, network, provider, Worker, merge, deployment or real credentials. Its historic file:line findings are NOT assertions about newest G43 head.

Eight findings:
1. Real SQL column CONFIRMED but legacy `action_outbox.data` JSON says PENDING, so SQL/JSON consumers can disagree.
2. Public `_view()` reads decision data, not embedded Outbox JSON; malformed document can go unnoticed.
3. Cross-decision JOIN does not automatically guarantee scope/payload/decision provenance consistency.
4. A valid count in effect ledger is not semantic consistency of receipt, row state and timestamps.
5. Pre-callback observations and post-callback writes need CAS to avoid stale terminal overwrites.
6. Duplicate confirmation historically could rewrite original confirmation timestamp; new G42 candidate addresses a subset (Codex did NOT inspect it).
7. Adding SQLite triggers/views to sync JSON would conflict with `aion_chat/store.py` recovery validator, which rejects them.
8. `CREATE TABLE IF NOT EXISTS` is not validated versioned migration; malformed schema can persist undetected.

**Important follow-up adopted**: An auditor cannot claim to be strictly read-only if it instantiates SQLiteChatStore/ExecutionOutbox, since constructors can write/create schema. Use a separate raw SQLite connection opened `mode=ro` without `immutable=1`, keep query-only transaction, and avoid logging payloads. This is a local diagnostic, NOT an independently owned witness. Codex did not test or validate the G43 implementation; GitHub Actions does.

## Actual G43 LAB candidate and boundaries

- `ExecutionOutbox(..., strict_projection_lab=True)`: newly **CONFIRMED** effects update the JSON projection and authoritative columns within the same existing SQLite transaction as the effect-ledger insert and state CAS. The opt-in does **not** add physical schema, triggers, views or backfill previously saved rows.
- `projection_plan_lab(key)`: reports one versioned `AION-A190-G43-PROJECTION-DRYRUN-V1` plan with scoped identity, original raw JSON SHA-256, state, attempts, lease, effect and confirmed timestamp, plus changed flag; method has no DML, but an Outbox instance may have initialized schema before it runs.
- `apply_projection_plan_lab(plan, explicit_approval=True)`: single-row scoped DML only if opted in and exact snapshot, generation/owner/expiry and original JSON hash agree. The helper recomputes JSON from authoritative SQL columns, verifies identity and consistency with `action_effects`; **does not INSERT, DELETE or UPDATE effect ledger**, does not touch original timestamps or other rows. No automatic historic repairs.
- `labs/a190/g43_projection_readonly_auditor_lab.py`: fully separate **`sqlite3.connect(file.as_uri()+'?mode=ro',uri=True)`**, `PRAGMA query_only=ON`, BEGIN consistent snapshot. Does not invoke store/outbox constructors. Classifies projection drift, malformed JSON, forged row/decision keys, inconsistent effect records, missing/foreign decision and unsupported trigger/view schema without returning secret payload values. No adoption of `immutable=1` for active WAL.
- Historic baseline and default mode remain unchanged; **legacy writers still leave JSON PENDING**. A hostile host can restore older SQLite and erase the locally consistent confirmation. Exact real commercial truth/provider receipt is still unauthenticated.

## G43 CI

First focused [G43 #40134255513](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40134255513) at code/workflow SHA `c37c090cd9eff8925d22b02c1d1d56e1a87c3ac4`: initial 22 G43 + 307 inherited G30–G42 = **329 per OS**. Do not infer newer scanner success from this run.

Scanner follow-up added 10 more tests and changed workflow count to **32 G43 + 307 inherited = 339 distinct tests per OS, 678 executions if both pass**. Latest intended code/workflow SHA `7e7094e2afc2a34a162e858523513b0edc17b179`. [**G43 latest CI #40134418757**](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40134418757) **SUCCESS**: Windows job `120992792468` **339/339**; Ubuntu job `120992792630` **339/339**, **678 executions of 339 distinct tests**. The exact verified code/workflow SHA was `7e7094e2afc2a34a162e858523513b0edc17b179`. All required GREEN and intentional-RED markers passed. The later documentation commit is not the tested code SHA; the separate A184 canonical Quality/Security was still queued and cannot be counted green. This document is an evidence-only follow-up, not included in that tested code SHA.

Positive markers: `G43_READONLY_PLAN_GREEN`, `G43_EXPLICIT_ONE_ROW_GREEN`, `G43_NEW_CONFIRM_GREEN`, `G43_LEDGER_IMMUTABLE_GREEN`, `G43_STALE_PLAN_GREEN`, `G43_TAMPER_GREEN`, `G43_REOPEN_GREEN`, `G43_STANDALONE_RO_GREEN`, `G43_STANDALONE_DRIFT_GREEN`, `G43_SCHEMA_GREEN`.
Explicit remaining RED: `G43_LEGACY_JSON_RED` default behavior, `G43_NO_RECEIPT_RED` contradictory local confirmation without ledger, `G43_HOST_ROLLBACK_RED` same-host backup restoration erases effects. Passing RED tests demonstrates a vulnerability/reproduction, **not remediation**.

## Independent P0 blockers

No production migration has been approved. Versioned row-by-row dry-run does NOT authenticate external owner, custody or provider receipt; independent high-water recovery and hostile-host antirollback still missing. No broad H0 proof, provider-side exactly-once, first-send transactional atomicity across host/provider, SQLite native compatibility homologation or complete Quality/security remediation. A184 canonical CI is separate and cannot be inferred green from focused G43. Previously verified `pip-audit` found 48 vulnerabilities in pypdf/Pillow; must verify current separately. **0/6 P0 HOMOLOGATED; HARD NO-GO; UNCERTAIN; ZERO_AUTO_RESEND. No main/merge/deploy/Worker/provider/customer data/secrets/spend.**
