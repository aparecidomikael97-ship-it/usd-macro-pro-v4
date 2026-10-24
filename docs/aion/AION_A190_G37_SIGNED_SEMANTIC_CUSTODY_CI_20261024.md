# A190 G37 — Authority-signed semantic custody LAB evidence

**Date:** 2026-10-24. **Exact tested code/workflow SHA:** `1ba031b8fa7efd09fda65523863b49db97c53cbb`. Branch stacked on G36 Draft #1523, G37 Draft #1524. **Not merged/deployed.**

## Objective and achieved LAB boundary
G36 witness signed arbitrary host-provided snapshot digests. G37 instead requires an Ed25519 **authority-signed business-event permit** and issuer public key pinned in the witness. The permit includes scope, business event ID, action, aggregate, positive amount and bounded expiry. Witness derives semantic identity from signed scope + event ID, **not request ID**; reserves that event once in a local SQLite UNIQUE record; rejects a signed conflicting amount for the same event; and signs a latest sequence/chain head with fresh nonce using a distinct custody key.

A read-only gate compares both pinned signatures and signed permit fields against a **real local ExecutionOutbox** decision. Even perfect synthetic evidence yields only **Admission.UNCERTAIN, never SEND or RETRY**.

## CI — verified
[**G37 Actions #40128314105**](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40128314105): **SUCCESS** at the exact code SHA.
- Ubuntu job `120974392726`: 34 new G37 + 139 inherited G30–G36 = **173/173**.
- Windows job `120974392860`: **173/173**.
- **346 executions of 173 distinct tests**. Logs show mandatory RED and GREEN proof markers.

## GREEN, narrowly interpreted
- `G37_RAW_DIGEST_DENIED_GREEN`: a raw host-supplied hash cannot reserve.
- `G37_ISSUER_GATE_GREEN`: valid pinned issuer signature required.
- `G37_SEMANTIC_DEDUP_GREEN`: two request aliases for the same signed event share **one witness-side reservation**.
- `G37_CONFLICT_GREEN`: conflicting signed amounts for a single event are rejected.
- `G37_DOUBLE_PIN_RECOVERY_GREEN`: two pinned signatures + nonce + real Outbox semantic binding return **UNCERTAIN only**, zero provider access.
- Witness key pin and reserve survive simulated local process reopens.

## RED, unresolved
- `G37_LOCAL_ALIAS_RED`: real Outbox still has **two rows** for a single semantic business event under two different caller request IDs. Witness-only dedup is not global exactly-once.
- `G37_HOST_WITNESS_ROLLBACK_RED`: restoring the local witness SQLite file rewinds its sequence, permitting reuse. A signed chain + AUTOINCREMENT is not antirollback custody.
- `G37_OUTBOX_ROLLBACK_RED`: permit signature alone does not prove latest Outbox state.
- `G37_COROLLBACK_RED`: rollback of local Outbox AND witness files together yields matching but old signed evidence.
- `G37_ISSUER_CAPTURE_RED` and `G37_FABRICATED_AUTHORITY_RED`: issuer private key held by test host can sign fictitious commercial events that the witness will accept. Cryptographic authorship does **not** establish real-world event existence or legitimate authority.

## Scope and required next proof
This is a synthetic protocol with **two local keys and same-host storage**, not independently provisioned owner identity or independent custodian. Witness cannot autonomously verify business truth, and the issuer key is not real owner proof. There is no atomic external first-attempt reservation, provider-signed receipt, antirollback storage, verified identity, deployed Worker, live provider or physical fault certification. Pinned local attestations authorize no external effect.

The G37 path-specific workflow **did not rerun A184** canonical Quality/Security or dependency audit. Historical A184 HARD NO-GO and dependency vulnerabilities are not cleared.

Next: LAB G38 independently authenticated *source-event provenance* and signed semantic-identity collision tests; ensure attestations binding to external monotonic state, never conflate same-host signed evidence with outside trust. Separate read-only Codex audit on the user's isolated Windows checkout may guide additional tests, but is NOT considered G37 CI.

**0/6 P0 homologated. HARD NO-GO · UNCERTAIN · ZERO_AUTO_RESEND. No main/merge/deploy, Worker, real provider, customer secrets or spend.**
