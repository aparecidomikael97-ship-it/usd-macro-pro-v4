# AION V16-A.42 — deny forged Saga compensation admission (HARD NO-GO)

**Exact parent:** A.41 Draft #1254, HEAD `585ba5c47f42dab993b7583abc2b6e2a7f9e5857`. Child lab only; Core V1/main/AM12 unchanged.

## Proven boundary gap in the pre-patch coordinator

Two productive Saga methods relied on local SQLite fields, with no enrolled independent producer or HUMAN_OWNER verification:

1. `prepare_compensation` looked for `saga.state=COMPENSATION_REQUIRED` and step `CONFIRMED`; callers could assert `explicit_human_approval=True` and pass arbitrary `approval_ref` / `reauth_ref`. SQL-fabricated confirmation and those caller parameters could mutate the local Saga into `COMPENSATING`, though no verified external effect or owner ceremony occurred.
2. `enqueue_next_compensation` selected the next `COMPENSATION_PENDING` local row in a `COMPENSATING` Saga, then staged a compensation Outbox intent from locally stored `effect_ref`, `compensation_approval_ref`, `compensation_reauth_ref`. Nothing in that Saga boundary independently authenticated an effect or approval. Outbox provider SEND is separately denied by existing producer gates; the gap concerns unauthorized **staging**, not evidence of any external send.

Neither the A.40 simulation nor the A.41 pure selector is a producer or trusted signer.

## Minimal fail-closed A.42

- After ordinary local shape/state checks, `prepare_compensation` now rejects before any Saga mutation with `INDEPENDENT_PRODUCER_RECEIPT_NOT_ENROLLED`. A caller Boolean + reference pair is NOT signed owner proof.
- After shared pure reverse candidate selection, `enqueue_next_compensation` rejects before `outbox.enqueue` with `INDEPENDENT_PRODUCER_COMPENSATION_NOT_ENROLLED`, even for SQL-fabricated `COMPENSATING` + pending rows. No effect or authority-budget write is permitted.
- Existing A.39 positive/negative `sync_forward_outcome` and `sync_compensation_outcome` hard denials are unchanged.
- A.41 first forward intent can still be staged but cannot send without producer enrollment, and subsequent forward steps still cannot be staged from fake local confirmation.
- Eight real-Saga SQLite adversarial tests exercise fake confirmed+no-effect rows, forged owner refs, wrong owner flag type, forged compensation state, multi-step reverse selection, blank refs, simulated-looking effect string and refusal in unprepared state. Tests assert Saga/event/outbox/effect/authority counts unchanged by each denied call.
- CI compiles/runs these tests separately in Security Gate and includes them alongside all existing root Quality tests. No historic test omitted/xfail/skip.

## Deliberately NOT solved

The patch does not establish independent causal `COMMITTED_EFFECT` receipts, producer-side `NO_EFFECT_FENCED` late effect guarantee, signed HUMAN_OWNER compensation approval bound to Saga and plan, witness-backed antirollback, trustworthy process isolation from direct SQLite writers, hardware identity or production liveness. It intentionally **blocks** compensation preparation and staging until real independently verified prerequisites are developed in separately authorized change. No affirmative proof is ever derived from simulated labels, local SQLite or user-supplied approval booleans.

The old eight Saga liveness errors and 23 Outbox errors remain authentic RED, as do the 45 original A12/A16 ZIP tests pending recovery. **0/6 P0**, **20/20 first-install HARD NO-GO**. No merge, deploy, Worker/Render, external calls, keys, provider enrollment, spending, or AM12 changes.

## Acceptance requirements

Exact-HEAD GitHub Security Gate must pass the adversarial regression; root Quality must execute the additional eight tests and report no newly introduced errors beyond 23 historic Outbox + 8 historic Saga. Never claim productive compensation validated merely because the negative-path tests pass.
