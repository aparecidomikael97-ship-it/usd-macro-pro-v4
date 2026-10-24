# A190 G21 — Real Outbox read-only recovery bridge CI evidence

Date: 2026-10-24. Exact tested code/workflow SHA `3bbabeca16f82865a8a90f9beb876f17ddf63e4a`.

- First CI [#40119689441](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40119689441) failed: real `ExecutionOutbox.get` raises `LookupError("action intent unavailable")` on missing key. The bridge originally mapped that to generic read failure; test expected specific missing-row denial. Corrected fail-closed exception mapping in tested SHA.
- Second CI [#40119732733](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40119732733): **SUCCESS**.
- Ubuntu job `120948440919`: **12/12**.
- Windows job `120948441069`: **12/12**.
- Total: **24 executions of 12 distinct adversarial read-only tests**.

The bridge reads real `atlasquant_aion_execution_outbox.ExecutionOutbox.get` and `aion_chat.store.SQLiteChatStore` rows in synthetic temporary databases. It calls the G20 recovery contract. Matching synthetic attestations yield only `UNCERTAIN_ZERO_AUTO_RESEND`; missing witness, mismatched root, digest, sequence, invalid signature and missing rows deny. No `dispatch_claimed`, no provider send, no state mutation.

## Limits
Witness `verify` is an in-process Boolean test double, **not cryptographic verification or external custody**. The Outbox idempotency key is a diagnostic key, not independently proven semantic identity. The row projection derives `sequence` from `attempts + 1` for laboratory comparison; this is **not an independently anchored monotonic sequence**. This is an isolated read-only bridge, not wired into operational AION. It does not prove H0 availability, rollback resistance, WAL/SHM, owner identity, provider receipts, or first-attempt safety.

No canonical Quality/Security suite rerun, no merge/main, deploy, Worker, provider, customer, credentials or spending.

**0/6 P0 homologated · HARD NO-GO · UNCERTAIN · ZERO_AUTO_RESEND.**
