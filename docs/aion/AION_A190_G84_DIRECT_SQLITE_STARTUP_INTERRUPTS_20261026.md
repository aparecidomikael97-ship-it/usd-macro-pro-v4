# AION G84 — direct SQLite startup interruptions: RED → GREEN (LAB)

**Date:** 2026-10-26. **Stack base:** G83 Draft #1570, commit `db0904c2cd732ea19b72a929e3a08bef2baee209`.

**State:** Draft only. Six P0 = **0/6 HOMOLOGATED**; **HARD NO-GO**. No main merge, deploy, Worker, real provider SEND, real trading, keys, independent custodian or live receipt.

## Defect and tests-first reproduction

G83 handles secondary `KeyboardInterrupt`/`SystemExit` from `db.close()` *after a recognized startup error*, but a primary `BaseException` raised directly by the connection factory or schema `executescript` bypassed its outer tuple-limited `except`. This could leave the partially initialized `SQLiteChatStore` attached, labelled HEALTHY, and usable despite an uncertain native writer transaction.

G84 first committed SIX synthetic tests in `labs/a190/test_g84_direct_constructor_interrupt_lab.py` plus a dedicated Ubuntu/Windows workflow, without modifying production. Cases include primary KI/SystemExit, secondary close interruption before/after native close, and factory interruption without a returned handle. The schema proxy uses a real temporary SQLite file and `BEGIN IMMEDIATE` to probe actual writer-lock behavior; registered fixture cleanup closes the raw handle after evidence collection.

**Genuine prepatch RED:** Workflow [40314005322](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40314005322), head `e6977d24627d170ed59945b64e8450d98739b4c6`.

- Ubuntu: `Ran 111 tests`; `FAILED (failures=18)`.
- Windows: `Ran 111 tests`; `FAILED (failures=18)`.
- These are 18 subtest/assertion failures in six new tests, **not** 18 separately certified vulnerabilities. Existing 105 inherited regressions were included.
- Demonstrated: `close_count=0`, `_health_state=healthy`, `db` still attached, and unsafe operation attempted after the primary interrupt.

## Minimal production fix

Only `SQLiteChatStore.__init__` in `aion_chat/store.py` changed:
1. Catch `BaseException` during startup, mark store FAILED, attempt exactly one close, and detach `db` even if close itself raises another `BaseException`.
2. Preserve `StorageUnavailableError` directly and continue to wrap `sqlite3.DatabaseError` / `OSError` in `StorageUnavailableError` as before.
3. Re-raise other primary exceptions (including `KeyboardInterrupt`/`SystemExit`) unchanged, **without** silently turning them into ordinary storage exceptions.

No retry, rollback, forced reopening, schema change, independent witness, external SEND or provider interaction was introduced.

## Postpatch GREEN

**Corrected source commit:** `64428f98e0ac8823a0572b50bf93be7eab6a56ff`.

**Exact GitHub run:** [40314174145](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40314174145).

- Ubuntu: `Ran 111 tests in 1.007s`, `OK`, job SUCCESS.
- Windows: `Ran 111 tests in 12.316s`, `OK`, job SUCCESS.
- Six new G84 test markers confirmed in *both* logs: direct KI, direct EXIT, secondary close before/after, factory KI and factory EXIT.
- Inherited 105-test G77–G83 focused regression selector remains present and passed as part of the 111.

## Non-claims and separate blockers

The store cannot prove that a native file descriptor was physically closed if its driver's close raises before release. The synthetic test intentionally demonstrates that an external native writer lock **may remain** until authorized process/fixture cleanup. If the connection factory creates an invisible raw connection then raises without returning it, this handler cannot reclaim that unknown handle. H0 recovery needs external monotonic custody/attestation.

Two inherited CI issues observed on G83 before G84 remain separately tracked:
- Broad G71 test discovery imported G74–G76 without `requests` installed in that workflow (3 import ERRORs).
- Windows SQLite staged lifecycle had `PermissionError WinError 32` cleaning a legacy temporary SQLite file retained open by another thread/handle.

No independent Codex run for G84 was claimed: Windows machine `am12` was offline this turn. Full canonical Security/Quality on **this exact G84 stack** are not certified by the focused 111-test run; earlier Q2 Quality green belongs to a different stacked branch. 0/6 P0, HARD NO-GO remains.
