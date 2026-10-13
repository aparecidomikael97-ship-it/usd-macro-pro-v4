# AION V16-A.43 — Local Saga chain integrity is not an independent witness (LAB / NO-GO)

**Exact parent:** A.42 Draft PR #1255, HEAD `8d398413828b18ae032358bccaff54d830c91868`. Draft-only laboratory. Main/Core V1/AM12 unchanged.

## Root cause, reproducible at source level

The real `ExecutionSagaCoordinator.integrity_report()` only loops over local `aion_execution_saga_events`. With a valid Saga still in `aion_execution_sagas`, deleting **every** event yielded `rows=[]`, an empty `blockers` list and `state=MATCH` with `events=0`. A tail deletion leaving only a valid genesis hash could also yield `MATCH` despite an already `RUNNING` Saga. These are **false local consistency results**, not proof of any external effect. The hash chain and Saga row reside in the *same mutable local SQLite failure/administration domain*.

## Minimal correction

- Require the local event chain to be nonempty (`EVENT_CHAIN_EMPTY`) and begin with `SAGA_CREATED` (`GENESIS_EVENT_MISSING`).
- After all local event sequence/hash checks pass, require local latest event state to equal current Saga state (`LATEST_EVENT_STATE_MISMATCH`). Detect simple truncated-tail and local state rewrite, without pretending to defeat a writer who can rewrite both tables and recompute hashes.
- Preserve existing `state=MATCH|MISMATCH` semantics for **local** checks, but add explicit `proof_scope=LOCAL_SQLITE_CHAIN_ONLY`, `independent_witness_verified=false`, `producer_effect_verified=false`, `authorizes_execution=false`.
- Four new actual SQLite tests verify: all events deleted, latest event deleted, Saga state rewritten, intact chain with **no externally authenticated authority**.
- Root Quality retains every original Outbox and Saga test; Security Gate runs all four new test cases as a **separate mandatory** step (no skip, xfail, waiver, or always-green wrapper).

## Honest assurance boundary and remaining P0 blockers

Even `MATCH` only demonstrates local consistency of the snapshot being inspected. It does **not** verify independent latest-head custody, immutability/antirollback, trusted owner approval, a provider's idempotent committed effect, terminal `NO_EFFECT_FENCED` guarantee, external timestamps or actual provider execution. A sufficiently privileged same-domain writer may still rewrite/re-hash local tables or restore a coherent old snapshot. Such attacks need a separate external current-head witness in a distinct failure/admin domain; this change deliberately does not fake one.

The **31 historical Quality errors** (23 Outbox + 8 real Saga) are *not* solved by this patch. The separate nine pure simulation tests are not productive receipts. Original A.12/A.16 45 ZIP tests still require source recovery/execution. **0/6 P0 homologated and first installation 20/20 HARD NO-GO** until verifiable external evidence and an explicitly authorized physical acceptance exist.

No merge, deploy, installer, Worker/Render, provider call, credentials/keys, spend, physical host operation or external effect authorized. 
