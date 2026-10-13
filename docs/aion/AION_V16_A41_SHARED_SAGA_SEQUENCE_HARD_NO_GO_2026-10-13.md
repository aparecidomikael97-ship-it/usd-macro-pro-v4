# AION V16-A.41 — shared pure Saga sequencing, not effect proof (HARD NO-GO)

**Parent:** A.40 Draft PR #1253 at `9165e11daed6b349329b9ce54763c55d3339b65f`. Stacked laboratory changes only, no merge/deploy/producer enrollment/owner ceremony.

## Verified code-level issue in parent

Productive `ExecutionSagaCoordinator.enqueue_next` selected the next step by consulting only the persisted `aion_execution_saga_steps.state` projection. A.39 denies promoting a local Outbox `CONFIRMED/FAILED` through `sync_forward_outcome`, but a directly manipulated Saga step row `CONFIRMED` with no producer evidence could still satisfy its sequence check and cause a *subsequent Outbox intent* to be staged. The independent Outbox provider send hard stop remains in force; this is **not** evidence that a provider action could execute. Nonetheless downstream intent staging based on fake proof is not acceptable.

## Narrow A.41 change

1. `atlasquant_aion_saga_sequence_policy.py`: pure `select_forward_step` and `select_compensation_step`. No SQLite, adapter, sender, signer, witness, effect ledger, authority budget writes or receipt validation. Their return values are **indices**, never approvals/effects.
2. Production Saga forward and reverse candidate selection use those **same** pure functions, instead of copy/pasted eligibility/order checks.
3. In real `enqueue_next`, choosing an ordinal after the first **always fails closed** with `INDEPENDENT_PRODUCER_RECEIPT_NOT_ENROLLED` before `outbox.enqueue`, until a future separately reviewed producer-admission path exists. This is conservative intentionally: local `CONFIRMED` is not a receipt. The first step may still be *staged*, but existing Outbox provider hard deny prevents actual sending.
4. `test_atlasquant_aion_saga_sequence_policy.py`: pure selectors exercised across state/sequence cases; real SQLite adversarial regression for fake `CONFIRMED` verifies no second Outbox insert, no Saga mutation and no additional authority effect count. No external provider, network, signer, manual owner approval, fake trusted receipt or action.
5. CI explicitly compiles/tests the shared selector and adversarial regression in Security Gate; root Quality includes the new test file. A.40 nine separate simulation cases and all historical 23 Outbox + 8 Saga errors remain.

## Strict nonclaims

- This is NOT a complete shared Saga state machine: it extracts **sequence/candidate selection only**. Outcome promotion still requires an independent real producer receipt/terminal fence, which does not exist here.
- Pure selector returning index 1 for `["CONFIRMED","PENDING"]` **does not authorize** real Saga. The production fence denies it, even when the previous row was fabricated locally. No simulated/positive receipt may flow into productive authorization.
- This does not certify compensation liveness, compensation outcome, transactional atomicity, shared real effect budget or cross-host antirollback. Forged Saga compensation rows merit a subsequent separate positive-proof/producer-enrollment review; do not infer they are safe just from pure selection.
- The 8 original Saga errors are not converted to PASS by this extraction, and no original A.12/A.16 45 ZIP tests have been recovered. Core V1, main, AM12, Worker, Render, keys and contracts remain untouched.
- Homologation unchanged: **0/6 P0**, **20/20 first installation gates HARD NO-GO**, overall Quality remains RED until independently proven otherwise.

## Acceptance checklist

- Exact-HEAD security and certification checks verify this regression. If Quality errors differ from the 31 historical ones, investigate; never mark them expected failures or remove tests.
- Document PR branch and parent SHA; never auto-merge.
- Real independent issuer, producer-enforced late-effect fence and current-head witness are prerequisites for any positive productive Saga path. Owner must separately authorize critical actions.
