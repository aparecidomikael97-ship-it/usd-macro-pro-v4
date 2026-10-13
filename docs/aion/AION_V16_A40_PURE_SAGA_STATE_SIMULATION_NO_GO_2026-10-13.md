# AION V16-A.40 — separate pure Saga simulation, NOT receipt evidence

**Security state:** NO-GO. This isolated LAB stage is child of [Draft #1252](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/pull/1252), HEAD `1ac2cad968b961073edd4aa47edc778a56f905f6`. A.39 already blocks forward and compensation promotion of local `CONFIRMED` and `FAILED` in the real Saga. Original full Quality: 6,174 tests, 31 errors (23 historical Outbox + 8 historical Saga) and zero failures. The green targeted Security Gate does not override these errors.

## Exact scope

This PR adds only a **test-only pure reference**:
- `test_atlasquant_aion_saga_pure_simulation_reference.py` has its own fully in-memory `_TestOnlySagaProjection` and `_TestOnlyScopeBudget`. It does **NOT IMPORT the real Saga, Outbox, SQLite store, producer adapter, receipt signer, witness, or execution API**.
- `.github/workflows/quality-tests.yml` explicitly registers the new root test file. The original eight failing Saga tests are NOT removed, replaced, skipped or marked expected-failure.
- `.github/workflows/aion-core-security-gate.yml` runs the simulated tests as a distinct, clearly labeled **NONPRODUCTIVE** step alongside the existing three real Saga anti-forgery tests, seven real Outbox hard-deny tests and nine untrusted-receipt tests.
- No actual application/module execution logic, data schema, effect ledger, provider enrollment, credential management or productive CI gate is changed.

## Why this is necessary

The eight historical Saga liveness tests used a test-only SQL fixture which first verified the real producer hard stop and then inserted locally fabricated `CONFIRMED`, `FAILED` and effects rows to exercise historical forward/compensation state transitions. Before A.39 the production Saga coordinator could promote those local states into real `COMPLETED`, `COMPENSATION_REQUIRED` or authority counts without an independently authenticated producer. A.38 proved the defect as two NEW red tests; A.39 denied before mutation, causing eight old state-machine tests to error.

The new reference demonstrates the same *hypothetical orchestration rules* only, without a persisted operational state or signer. It cannot be confused with producer verification because:
- every outcome must be one of three strings prefixed `SIMULATED_ONLY_`; arbitrary real-looking `CONFIRMED`, `NO_EFFECT_FENCED`, signature maps and `trusted=true` are rejected;
- every model reports `proof_status=SIMULATED_ONLY_NO_EXTERNAL_EVIDENCE`, `external_action_authorized=false`, `effect_ledger_authorized=false` and `retry_authorized=false`;
- its counted effects are only `hypothetical_effects` on a model budget, not `CumulativeAuthorityBudget` nor authoritative AION effect records.

## Test correspondence to original red scenarios

| Pure reference test | Original historical Saga topic | Real production path still requires |
|---|---|---|
| 01 — two forward commits in order | all forward steps confirmed/complete | Producer-signed committed effect |
| 02 — second failure and explicitly approved compensation | second-step failure/compensation | Producer no-effect fenced proof and verified compensation receipt |
| 03 — three-step reverse order | three-step reverse compensation | Scoped real receipts for each effect/rollback |
| 04 — irreversible prior effect | irreversible effect escalation | Independently verified real receipt and owner review |
| 05 — uncertain forward freeze | ambiguous forward/reconciliation | Independent authenticated readback |
| 06 — uncertain compensation freeze | ambiguous rollback/reconciliation | Authenticated compensation observation |
| 07 — negative compensation manual escalation | unverified compensation negative/manual | Terminal producer-enforced no-effect fence |
| 08 — shared effect budget | scope-window budget with second transaction | Productive `CumulativeAuthorityBudget` and real source proof |
| 09 — reject apparently trusted inputs | additional safeguard | Trusted provider admission and witness outside this model |

**These nine cases are NOT substitutes for the eight historical tests.** The old eight are intentionally left RED in root Quality and remain uncovered in the current production trust model. Passing a pure model does not prove production Saga correctness, actual liveness or side-effect safety. To safely share logic in the future, independently review extraction of an effect-free pure transition kernel from Saga after provider-admission contracts are established. Never rewire productive Saga to accept simulated projection results.

## Current unmet gates

P0 remains 0/6 HOMOLOGATED; all 20 first-install physical requirements HARD NO-GO. The 23 Outbox post-send cases and 8 historical Saga liveness cases remain open; A12 37 + A16 8 original ZIP cases unavailable and unexecuted. No external producer-issued COMMITTED_EFFECT or terminal NO_EFFECT_FENCED receipts, independent current-head witness, HUMAN_OWNER/host authenticated enrollment, or physical AM12 acceptance exists.

Do not merge, deploy, activate Worker/Render, select a provider, issue/rotate keys, incur costs, install on AM12 or perform external effects. No outcome from this reference is an authorization.
