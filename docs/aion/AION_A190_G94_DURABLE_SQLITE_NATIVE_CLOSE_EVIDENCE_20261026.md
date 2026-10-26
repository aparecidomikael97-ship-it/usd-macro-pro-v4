# AION G94 — DurableExecutionStore native SQLite deterministic close (LAB)

**Recorded:** 2026-10-26. **Parent:** G90 Draft #1581, exact source `df81c7482f5ee15a87d0f82bd222a38856bd4b8b`. **Status:** Draft; **0/6 P0 HOMOLOGATED; HARD NO-GO**.

## RED first / origin
Windows G91 full canonical Quality on G90's patched dependency stack: 6,449 tests, **109 ERROR, 15 FAIL**, [run 40325759222](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40325759222). Exactly original G89 pre-upgrade Windows run [40326597735](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40326597735) also had **109 ERROR** (and 14 FAIL); the errors predated G90. They clustered in 17 B2B durable execution/certificate modules with `PermissionError WinError32` cleaning `execution.sqlite3`.

Root found in `atlasquant_aion_durable_execution_kernel.py`: exactly **26 `with self._connect() as conn:` occurrences**. Python's sqlite3 connection context manager commits/rolls back but does **not close** its native file descriptor on exiting the scope. Five new synthetic tests wrap a real SQLite connection with a spy, require exactly one native close, original error and real closed-handle rejection, covering bootstrap, get-missing, idempotency get, synthetic query failure, prepare.

**Prepatch genuine RED** run [40328201809](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40328201809): Ubuntu 5 cases, **16 contract assertion FAIL**; Windows 5 cases, **16 contract assertion FAIL + 4 ERROR**. Native `close()` was never invoked. Synthetic fixture registered raw-handle close as cleanup even if production failed.

## Minimal patch and GREEN
**Corrected code SHA `7e7789b8581b001bb58f37710c561fe8f830548b`**: import `contextlib.closing`, replace all 26 scopes with `with closing(self._connect()) as conn, conn:`. Python context managers exit in reverse order: inner `conn` commits or rolls back **before** outer `closing` invokes physical `conn.close()`. No change in SQL, idempotency, authorized SEND policy, schema or automatic retry.

[Corrected G94 CI 40328435649](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40328435649): **5/5 PASS Ubuntu**, **5/5 PASS Windows**, all five native-close contract markers confirmed. This proof is scoped to the five synthetic paths but applies one source pattern to all 26.

## Broader measurement, not claimed full Windows green

G95 follow-up Draft #1586 [run 40328832712](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40328832712):
- Ubuntu full canonical Quality **6,449/6,449 PASS**; inherited Ubuntu canonical Security job SUCCESS.
- Windows full canonical Quality **6,449 tests; 68 ERROR, 15 FAIL**. Reduced by **41 ERROR from pre-G94 109**, but remains RED.
- Windows focused 17 B2B modules **175 tests; 66 ERROR**, indicating additional native connections, especially persistent nonce registry. G96 #1587 addresses the next six `with _connect` scopes.

Do not equate a reduction of failures with production readiness. The remaining Windows Quality/pytest issues and all five independent external-red acceptance cases are still open. Closing native handles locally does not prove native SQLite VFS identity, durable independent monotonic custody/checkpoint, authenticated original business event identity, externally pinned root, antirollback after same-inode restore, first-provider-send exactly once or availability after restart.

**NO MERGE · NO DEPLOY · NO WORKER · NO REAL SEND · NO MONEY · 0/6 P0 · HARD NO-GO.**
