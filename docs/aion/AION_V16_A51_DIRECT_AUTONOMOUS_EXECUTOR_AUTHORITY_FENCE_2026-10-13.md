# AION V16-A.51 — direct internal autonomous executor authority fence

## Parent and scope
Isolated child of [A49 Draft #1262](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/pull/1262), parent exact HEAD `c1c7f5940eef913d60ff2f77e3bc1de3181db2f2`. A51 [Draft #1264](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/pull/1264). The Codex local owns Outbox/Saga 31 ERROR and Codex Cloud owns original ZIP 45 recovery; this is separate Global Worker executor admission security work.

## RED reproduced in real code (mocked in-memory side effects only)
The previous A47 Global Worker front door and A48 CAS writer hard-stop did not constrain a direct call to `atlasquant_aion_background_executor._execute_due_local_work_authorized`. Its argument `authorization_mode` allowed `GLOBAL_WORKER` or `ARMED_WORKER` with only a nonempty caller-provided `authorization_digest` and local administrative fixture. This was an unenforced prerequisite, not a separately verified source/owner/latest-head witness.

Three exact real-kernel adversarial tests were added to the existing `test_atlasquant_aion_background_executor.py` file and independently required by `.github/workflows/aion-core-security-gate.yml` on RED HEAD `a361873feff35683c1f41b6a299459cc01eb3265`. [Security run 38488428311](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/38488428311) recorded **2 intentional FAIL of 3**:
- Direct `GLOBAL_WORKER` called the mock of `handle_runtime_intent` once despite no witness.
- Direct `ARMED_WORKER` with fabricated in-checkpoint `independent_witness=VERIFIED` reached `seal_executor_receipt_envelope`, which was forced to raise `A51_NO_RECEIPTS`.
- Valid explicit `HUMAN_CLICK` local workflow continued to pass.

This reproduces unauthorized *in-process local staging/handler reachability*, not real network/external actions. All handler/provider and receipt-envelope calls in the two attack tests were intercepted by mocks and no real external effects occurred.

## LAB fix after RED
`_execute_due_local_work_authorized` now rejects **both** unattended authorization modes at the start of the callee with `BLOCKED/INDEPENDENT_AUTONOMOUS_AUTHORITY_NOT_ENROLLED`, before reading scheduler, generating a receipt/envelope or calling runtime Core handler. No external trust authority exists for admission, and **caller strings, admin privileges and forged local checkpoint markers are not sufficient**.

Denial returns unchanged deep-copied checkpoint, zero due/processed/outcome counters, empty receipt/outcome arrays, no checkpoint save, no external state or simulated worker started, and explicit `independent_witness_verified=false`. Legitimate `HUMAN_CLICK` is preserved and is specifically regression-tested; its local receipts do not grant independent producer effect verification.

This is a containment guard, **not** a real owner-enrolled witness. Future productive autonomous admission requires owner-approved design review, source binding, independent latest-head antirollback witness and producer causal proofs. Do not add a local test token or environment flag as a bypass.

## Transparency and open blockers
Original 31 historical Outbox/Saga ERROR and 21 Worker legacy mock-positive FAIL stay visible in Quality; this patch is not a test cleanup. A12/A16 original 45 ZIP cases not recovered or executed. Physical Windows/TPM/HUMAN_OWNER, source↔owner↔tenant↔repo/path trust root, producer causal `COMMITTED_EFFECT` and provider-fenced terminal `NO_EFFECT_FENCED` are still absent.

**0/6 P0 homologated; 20/20 first-install gates HARD NO-GO.** No merge, deploy, Worker/Render activation, AM12 changes, external provisioning, accounts, keys, signatures, costs or sends. Report exact-head new CI results separately; RED proof alone is not a green certification.
