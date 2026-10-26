# AION G88 — scoped SQLite close interrupt quarantine (RED → GREEN)

**Data:** 2026-10-26. **Parent:** G87 Draft #1578, `5726a8ab235eb5e184d767dcd69fac5d7067e480`. **LAB Draft, no main merge/deploy/Worker/provider SEND. Six P0 = 0/6 HOMOLOGATED, HARD NO-GO.**

## Defeito objetivo e RED primeiro

`aion_chat/staged_store.py::OperationScopedSQLiteChatStore.__getattr__` creates a native `SQLiteChatStore` per operation, then closes it in a `finally`. The old handler around `store.close()` caught only `Exception`. This missed process interruptions such as `KeyboardInterrupt` / `SystemExit` and let a façade stay logically HEALTHY and reusable, potentially with a *real native writer lock* retained after the close failed before releasing it. A secondary interrupt from `close()` could also overwrite an earlier `LookupError` or `StorageUnavailableError`. Direct KI/SystemExit raised by delegated read operations similarly bypassed the normal failure latch.

G88 first added **six** synthetic adversarial tests in `labs/a190/test_g88_scoped_native_close_interrupt_lab.py`, with real temporary SQLite, native writer-lock probes and registered raw-handle fixture cleanup, plus a dedicated Ubuntu/Windows workflow. These tests were executed on the unchanged G87 production code.

**Genuine RED:** [run 40322751294](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40322751294), commit `46f5149c70a72f044bd52297797f2516b1e9f10b`.
- Ubuntu **19 tests**, `FAILED (failures=11, errors=2)`.
- Windows **19 tests**, `FAILED (failures=11, errors=2)`.
- The 11 failures are grouped contract/subtest failures across six new G88 cases (not 11 independent root vulnerabilities). Two extra errors arose when an unlatched store tried to inspect health while a real native SQLite writer lock was retained. Both show the failed quarantine requirement, not successful native cleanup.

## Narrow production correction

**Corrected source commit:** `738f85739abb6484b22c6ed6fc4146f74b0e04b9`.

Only `aion_chat/staged_store.py` changed:
1. Catch delegated operation `KeyboardInterrupt` and `SystemExit`, latch `OPERATION_INTERRUPTED_OUTCOME_UNKNOWN`, preserve original primary and never reopen/auto-resend on that façade. Normal `LookupError` behavior without a secondary close fault remains unchanged.
2. Capture a pending primary exception before the native `finally: store.close()` and handle `BaseException` on the close. **Always latch** `CONNECTION_CLOSE_FAILED` if close outcome is uncertain; if a primary exception already exists, do not mask it with the secondary close exception. If no primary, retain the original KI/SystemExit; ordinary close exceptions preserve the prior `StorageUnavailableError(CONNECTION_CLOSE_FAILED)` API.
3. No change to `aion_chat/store.py` close semantics or G82/G83/G84/G85 protections. No retry, rollback assumption, extra connection, provider/network access or SQLite schema mutation.

## Objective GREEN on the corrected commit

[Scoped G88 run 40322993274](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40322993274):
- **Ubuntu: 19/19 PASS**, `Ran 19 tests`, `OK`. All six G88 invariant markers confirmed.
- **Windows: 19/19 PASS**, `Ran 19 tests`, `OK`. Same six G88 markers confirmed.
- Selector covers six new G88 cases, six G84 constructor tests, five G85 legacy-thread tests, and two canonical SQLite lifecycle regressions.

[Inherited SQLite staged lifecycle run 40322993079](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40322993079): **both Ubuntu and Windows SUCCESS** on this exact corrected SHA. Other inherited G14, A186, A187 scope workflows also concluded SUCCESS (read their individual job logs for counts before citing any counts).

[A184 six-P0 run 40322993025](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40322993025) on the same source commit:
- Candidate canonical `security-unittest` and `security-pytest`: **SUCCESS**.
- External requirements `external-red` still FAIL (unmet genuine external original identity, root of trust, independent monotonic custody, live SQLite VFS and rollback-proof authority).
- Canonical dependency security-audit FAIL (known vulnerable pinned dependencies; no waiver).
- Canonical Quality candidate was **in progress** when this evidence document was prepared; do not claim green until exact job result/log `Ran ... tests`, `OK` is confirmed.

## Limits and remaining risks

Logical quarantine is not physical release of a native SQLite handle if a driver fails *before* its native close. The test fixture releases retained handles only after detecting that uncertainty; production has no such guarantee. G88's Python `sys.exc_info()` preservation also does not certify the separate anchor `os.close(fd)` path against a secondary OSError masking a primary outcome; that is a distinct future boundary. None of this implements native SQLite VFS handle attestation, external witness roots, immutable original business identity, H0 antirollback, provider ACK-loss reconciliation, or first SEND authorization.

No independent Codex session this round because authorized Windows computer was offline. Do not conflate RED/19-green synthetic proofs with six P0 certification.

**0/6 P0 HOMOLOGATED · HARD NO-GO · NO MERGE · NO DEPLOY · NO WORKER · NO REAL SEND · NO REAL FUNDS.**
