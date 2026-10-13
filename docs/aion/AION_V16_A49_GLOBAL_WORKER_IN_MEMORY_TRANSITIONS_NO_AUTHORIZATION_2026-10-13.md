# AION V16-A.49 — in-memory Global Worker transition laboratory (NOT productive authorization)

**Exact parent:** [A.48 Draft #1261](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/pull/1261) HEAD `1c5a2822594f4bfc9b529c08ee6b27018efe0236`. New isolated LAB child, Draft/unmerged. No production change, external request, deploy, account, host, Worker/Render activation or key.

## Why this is a separate lab

A.47 blocks the real `run_global_worker_once` before any lease CAS without an independently enrolled source/owner/tenant/current-head witness. A.48 separately blocks the internal `_persist_runtime_checkpoint_cas` entry before config access and GitHub PUT. Together these leave historical positive tests of mocked Worker write/reconciliation and tick execution **RED on purpose**, not proof of provider availability. Exact A.48 root Quality baseline: **6,236 tests / 31 ERROR** (23 historical Outbox + 8 historical real Saga) **+ 21 FAIL** in original Worker mock-positive assertions. Those original failing tests must stay in Quality unchanged, not skipped, waived, monkeypatched into a green productive path or relabeled as real-world verification.

A.49 adds **one new standalone test module**, `test_atlasquant_aion_global_worker_pure_simulation_lab.py`, that calls *only* local state-transition and governor functions, not the productive Worker entrypoint, writer, executor or GitHub checkpoint reader. The lab builds a locally invented ARMED fixture and a deterministic token labeled `A49_TEST_ONLY_INERT_TOKEN_NOT_AN_AUTHORITY`. This is a test scenario, not an owner-armed delegation. All tests install **fail-if-called sentinels** on `requests.get`, `requests.put`, `load_runtime_checkpoint`, `_persist_runtime_checkpoint_cas`, `_execute_due_local_work_authorized`, and `run_global_worker_once` and require each to have **zero calls**.

## Eleven test cases

1. Local claim yields fencing token 1 without mutating the input or storing anything.
2. Another runtime's claim is refused while an active local lease exists.
3. Expiry permits local reclaim with fencing counter increment and simulated crash recovery count.
4. Reentry by same owner preserves the active local token/fence.
5. A purely simulated all-zero batch releases the local state and clears inflight.
6. Wrong owner/token/fence are refused by the pure local release function.
7. Tampering with an in-memory work-intent digest is detected.
8. Overlarge work-intent occurrences are refused.
9. Invalid runtime ID values are refused.
10. Governor reports never grant permission, arm or execute.
11. Test-local token cannot be treated as source/witness/owner verification.

Both root Quality and a **named independent Security Gate step** execute this test module. It imports state helpers from real source to exercise authentic transition logic; it does **not** reproduce success from the real write/executor code and claims **no positive productive evidence**.

## Still explicitly OPEN

- The 21 original Worker historical FAIL on A.48 remain **unaltered and red**. A.49 supplements their positive algorithm intent without declaring them restored or passing. Separating comprehensive liveness and storage compensation into a fully independent fixture will need its own future evidence/review.
- The existing 31 historic Outbox/Saga errors remain real red, no waivers/xfail/skip.
- Producer-enrolled causal `COMMITTED_EFFECT` and terminal provider-fenced `NO_EFFECT_FENCED` not enrolled.
- No independent signed monotonic latest-head antirollback witness, current source/owner/tenant/repo/path binding, HUMAN_OWNER physical identity, Windows AM12 verification or initial installation authority.
- A12 original `AION_V16_A12_MOBILE_SIX_SOURCE_GATE_20261013.zip` 37 test cases and A16 original `AION_V16_A16_MOBILE_REAL_MODULE_REGRESSIONS_PREP_20261013.zip` 8 cases are still unavailable. Do not fabricate replacement bytes or certification.
- **0/6 P0 homologated; 20/20 first-install HARD NO-GO.** No main merge, Worker/Render, provider, credit, credentials, TPM/AM12, install, sending, costs or deploy.

The motto remains safety before claims: the local test fixture is explicitly nonauthoritative, and all observed CI failures remain visible.
