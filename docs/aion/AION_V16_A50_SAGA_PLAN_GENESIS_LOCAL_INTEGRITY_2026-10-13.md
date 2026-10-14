# AION V16-A.50 — Saga persisted plan/Genesis integrity (local only)

**LAB only:** [Draft #1265](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/pull/1265), child of A.49 #1262 exact HEAD `c1c7f5940eef913d60ff2f77e3bc1de3181db2f2`. This A.50 investigation was performed in the Windows sandbox `C:\Users\apare\Downloads\AQ_LAB_A50_OUTBOX_SAGA_20261013` by the local Codex, separately from the Codex Cloud 45 ZIP hunt and A.51 worker bypass investigation.

## Concrete pre-existing bug

In `ExecutionSagaCoordinator.integrity_report`, correctly hashed genesis/events and a matching final Saga state led to `MATCH` even if the persisted *immutable step plan* (payload, risk, compensation payload, missing step) or `plan_digest` was separately modified in SQLite without updating the events. Such `MATCH` is only a **local-integrity false positive**, not evidence of producer effect or independent antirollback.

## RED — original test artifact preserved

The local Codex created `test_a50_plan_integrity.py` in its dedicated LAB, which was copied verbatim (39 lines, seven unittest methods) into `test_atlasquant_aion_saga_plan_integrity_a50.py` on this Draft branch. Registered in Quality and as a mandatory, named Security Gate step.

- Windows local original source: `RED`: **7 cases / 5 FAIL / 2 PASS**. `GREEN` after candidate: **7/7 PASS**. Twenty-one selected original unrelated inert tests retained **21/21 PASS** both before and after, no tests modified. Windows Python 3.11.9, SQLite 3.45.1, temporary simulated SQLite, no network/connect.
- [GitHub Linux real baseline Security Gate RED run 38489672243](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/38489672243) on TESTS-ONLY HEAD `1e343ef40739a3e331d4c7ba2cd1716ffb8e9ddb`: exactly **5 FAIL** out of seven in the A50 mandatory step (payload, risk, compensation, deleted steps, plan digest), before any A50 runtime fix.

## Minimal fix — what it can prove

Reconstruct exactly the original `create()` plan fields from persisted `get()` steps; derive forward risk, worst-case risk and effect count; recompute `_digest(plan)` and require a match to stored plan digest. Independently bind the original `SAGA_CREATED.detail_digest` to stored plan digest and those totals, adding `PLAN_DIGEST_MISMATCH` and/or `GENESIS_PLAN_BINDING_MISMATCH` to the integrity blockers. Do not repair, overwrite, rehash or quietly re-enroll invalid source.

Matches only **local SQLite consistency**. Privileged simultaneous rewriting of plan/events/digest, old-state rollback, delete/recreate or missing independently held latest-head anchor remain **not detected**. `independent_witness_verified=false`, `producer_effect_verified=false`, `authorizes_execution=false`; no receipt authority. The patch does **not** change `dispatch_claimed`, `sync_forward_outcome`, Global Worker or direct CAS writer, and cannot green the historical producer-dependent cases.

## Quality and active blocks

A.49 parent Quality: **6247 / 31 ERROR (23 Outbox +8 Saga) +21 FAIL (Global Worker)**. These remain RED by design until independently verified producer/witness authority, not fixtures. A.51 #1264 on a sibling branch had 6250 /32 ERROR+32 FAIL from intentionally closing direct autonomous executor access; do not combine those counts with A.50 without a separate future integration and CI.

Original A12 37/A16 8 ZIP tests: **0/45 recovered, 0/45 run** per independent Codex Cloud report, artifacts still unverified. Missing owner/tenant/repo/path independent source trust, monotonic antirollback witness, causal COMMITTED_EFFECT & NO_EFFECT_FENCED producer receipts, physical HUMAN_OWNER/Windows proof.

**0/6 P0 homologated; FIRST INSTALL 20/20 HARD NO-GO. No merge, deploy, Worker, Render, Windows host changes, signing, credentials, provision, spending or external actions.**

Run final exact-head Linux CI Security/Quality and compare with A.49 before asserting regression stability. Keep all failing historical tests. No production GO inferred from green targeted A50 results.
