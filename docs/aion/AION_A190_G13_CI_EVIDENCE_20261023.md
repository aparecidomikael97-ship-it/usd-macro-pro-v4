# A190 G13 — Cross-platform CI evidence (2026-10-23 Manaus / 2026-10-24 UTC)

## Test identity

- Exact code, tests and workflow SHA: **b24f795480858c909a77082f9ab922f110b5b78c**.
- [GitHub Actions G13 run #40053019230](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40053019230) **completed success**.
- Ubuntu job **120749648367**: G13 15/15 + G11 20/20 + G12 9/9 = **44/44 tests OK**.
- Windows job **120749648608**: G13 15/15 + G11 20/20 + G12 9/9 = **44/44 tests OK**.
- **88 executions of 44 selected cases across both operating systems.** Checkout was SHA-pinned, no credentials persisted.
- G13 ran the actual ExecutionOutbox enqueue/claim/dispatch path against temporary SQLite. No real adapter send, network, cloud response, API credentials, Worker, payments or customer data.

## Supported bound

- Two different caller request refs and separately signed event refs for the *same signed semantic digest* map to one stable intent_ref and yield one real SQLite idempotent Outbox decision.
- The G11 DynamoDB and Firestore offline request-shapes derive the same native key; neither is sent.
- Changed action, payload, tenant, invalid signature, expired event or unsafe Outbox LAB opt-in are denied before staging.
- The G12 default dispatch gate prevents even reading an untrusted adapter.send property when callbacks return True. Outcome stays UNCERTAIN, ZERO_AUTO_RESEND.

## RED counterexamples reproduced ON PURPOSE

- **G13_CALLER_CONTROLS_PIN_AND_BUSINESS_EVENT=DOUBLE_STAGE_RED**: actor controlling signer and local pinned key invents another business_event_id with the same intended effect. This is NOT an independent issuer.
- **G13_CROSS_WORKSPACE_SAME_EVENT=LOCAL_DOUBLE_STAGE_RED_EXTERNAL_ROOT_NEEDED**: one signed event, two local Outbox scopes under the same tenant, produces separate SQLite outbox keys. Native remote key would be shared *if a real conditional external database existed*; none does.
- **G13_LOCAL_SQLITE_ERASE=REOPEN_SAME_EVENT_RED_EXTERNAL_CUSTODY_MISSING**: deleting a *temporary test-only* SQLite file allows rebootstrap and a new enqueue of the same semantic key. No antirollback attestation.

These passing test cases are reproducible demonstrations of **unsafe behavior** remaining possible; they are NOT passed P0 gates.

## Limits

- Client-controlled pin, synthetic signing keys, redacted-payload uniqueness and business_event_id origin cannot prove actual business intent. In-process caller can still manipulate both the code and source claims.
- All six P0 remain open. Real atomic external reservation, independently pinned issuer, provider-effect signed receipt, startup recovery guarantees and SQLite file identity/compatibility remain unproven.
- G12's prior canonical Quality unittest 6,449/6,449 and Security unittest 368/368 successes were tested at G12 SHA **0f6e042bfb568ef08f431a9cbebb414ce3fd7e06** and **were not rerun** by G13. The dependency security audit and external RED stay open.

**0/6 P0 · HARD NO-GO · UNCERTAIN · ZERO_AUTO_RESEND.**
