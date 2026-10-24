# A190 G22 — Coordinated host rollback real Outbox RED evidence

Date: 2026-10-24. Exact tested SHA `26fb299de8163a3fbf472e388f097b3671bcb413`.

## Executed
- [GitHub Actions #40119927264](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40119927264): completed SUCCESS.
- Ubuntu job `120949047164`: 5/5.
- Windows job `120949047366`: 5/5.
- Total: **10 executions of 5 distinct tests**, on real `ExecutionOutbox` / `SQLiteChatStore` with temporary SQLite only.

## RED markers reproduced
- `G22_COORDINATED_HOST_ROLLBACK_RED=OLD_HISTORY_FAKE_WITNESS_MATCHES`: after host restores a one-intent SQLite snapshot and supplies a matching old fake attestation, the G21 read-only bridge yields `UNCERTAIN` and cannot establish that a later local intent had existed. It does NOT return SEND.
- `G22_HOST_FORGED_SIGNATURE_RED=FAKE_VERIFY_TRUE_IS_ACCEPTED`: test-double `verify` always returns True. This is an intentionally **compromised synthetic witness**, not a bypass of an actual independent cryptographic verifier.
- `G22_SEMANTIC_ALIAS_RED=REAL_OUTBOX_DISTINCT_REQUEST_REFS`: distinct caller-supplied intent references create distinct keys for identical synthetic action/payload/aggregate.

## Strict interpretation
The tests demonstrate the insufficiency of **same-host or fake witness custody** and the limitations of caller-supplied idempotency references. They do NOT prove that a properly provisioned independent external witness can be rolled back or forged. They do NOT demonstrate real provider duplicate effects. No production code was modified and no `dispatch_claimed` was called.

Outstanding: externally pinned owner/provider/witness trust, independently monotonic external first-attempt reservation, real crash/restart and H0 recovery, SQLite WAL/SHM and P0 integration. Canonical Quality/Security not rerun. No merge/main/deploy/Worker/provider/customer/spending.

**0/6 P0 homologated · HARD NO-GO · UNCERTAIN · ZERO_AUTO_RESEND.**
