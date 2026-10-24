# A190 G27 — Durable local SQLite custody CI evidence

Date: 2026-10-24. Exact tested code SHA `d06a6b89f30e103d0ffc8d7b691870abeebca10e`.

## Runs and correction
- First run [#40121401404](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40121401404): Ubuntu success; Windows **FAIL** with seven `PermissionError [WinError 32]` cleanup errors. Cause: test cleanup captured the original SQLite connection method before tests reopened a replacement handle. The reopened connection was left active during Windows temporary-directory removal.
- Corrected cleanup to close the *current* SQLite connection, not the old bound method.
- Second run [#40121460030](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40121460030): **SUCCESS**.
- Ubuntu job `120953713281`: **18/18**.
- Windows job `120953713496`: **18/18**.
- Total: **36 executions of 18 distinct tests**.

## GREEN and RED
- `G27_RESTART_GREEN=RESERVATION_SURVIVES_REOPEN`: a committed semantic reservation survives closing and reopening the same SQLite custody database on both OSes.
- `G27_HOST_DELETE_RED=LOCAL_CUSTODY_RECORD_LOST`: same-host file deletion erases custody history.
- `G27_HOST_ROLLBACK_RED=OLD_SQLITE_CUSTODY_ACCEPTED`: restoring an old SQLite file makes an old custody state appear current.
- `G27_HOST_COUNTER_ROLLBACK_RED=SEQUENCE_REUSED_AFTER_RESTORE`: restoring an old file reuses the prior sequence number.
- Transactional `BEGIN IMMEDIATE`, unique semantic key, `AUTOINCREMENT` and `synchronous=FULL` do NOT prevent same-host rollback.

## Limits
This is a separate local SQLite file, **not** an independent external witness or hostile-host-resistant monotonic store. The signing key is ephemeral and supplied in-process; no independent key provisioning, real external first-attempt reservation, provider receipt, operational AION integration or H0 proof. This lab uses `journal_mode=DELETE`, not an AION WAL/SHM compatibility validation. Canonical Quality/Security not rerun. No merge/main/deploy/Worker/provider/customer/credentials/spend.

**0/6 P0 homologated · HARD NO-GO · UNCERTAIN · ZERO_AUTO_RESEND.**
