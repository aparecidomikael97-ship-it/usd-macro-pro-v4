# A190 G19 — Real AION ExecutionOutbox offline RED evidence

Date: 2026-10-24. Exact tested SHA `803c5daf1c07c01d64fecdd997f0800346863ee8`.

## Executed
- [GitHub Actions #40119282841](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40119282841): completed SUCCESS.
- Windows job `120947088073`: **5/5**.
- Ubuntu job `120947088260`: **5/5**.
- **10 total executions of five distinct tests**; no provider adapters, no dispatch, no network calls.
- Real classes: `aion_chat.store.SQLiteChatStore` and `atlasquant_aion_execution_outbox.ExecutionOutbox`, using synthetic temporary SQLite databases.

## Confirmed RED (tests intentionally assert unsafe local behavior)
1. `G19_REAL_OUTBOX_ROLLBACK_RED=OLD_DB_FORGETS_PRIOR_ENQUEUE`: a closed local DB restored from a pre-enqueue snapshot forgets the prior decision. Re-enqueue returns `ENQUEUED` again, not `IDEMPOTENT`. This shows local journal cannot be an independent monotonic witness.
2. `G19_REAL_OUTBOX_SEMANTIC_ALIAS_RED=TWO_REQUEST_REFS_TWO_KEYS`: identical action/payload/aggregate under distinct caller-supplied `intent_ref` values yields distinct keys. Caller-supplied request references are not independently established semantic identity.

Other observations: unchanged `intent_ref` remains idempotent in unchanged local history, outbox stages without adapter execution, and synthetic evidence callbacks remain disabled by default.

## Strict limitations
The tests do NOT demonstrate a real duplicate external effect or that any production adapter can send: they never call `dispatch_claimed`. The REDs demonstrate that local-only state is not sufficient for an independent durable semantic reservation under hostile-host rollback. Independent trusted owner/provider roots and monotonic custody are still missing. No production code changed. No merge, deploy, Worker, provider, customer data or expense. Canonical Quality/Security not rerun.

**0/6 P0 homologated · HARD NO-GO · UNCERTAIN · ZERO_AUTO_RESEND.**
