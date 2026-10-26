# AION G96 — PersistentNonceRegistry deterministic native SQLite close (LAB)

**Recorded:** 2026-10-26. **Parent:** G94 Draft #1585 corrected source `7e7789b8581b001bb58f37710c561fe8f830548b`. **Draft, 0/6 P0 HOMOLOGATED; HARD NO-GO.**

## Bug / test-first RED

G94 explicitly closed the 26 native SQLite connections created in `DurableExecutionStore`, reducing **historical** Windows 6,449-case canonical Quality from **109 ERROR to 68 ERROR** without excluding tests (G95 [40328832712](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40328832712)). More `WinError 32` remained on B2B nonce and writer-related temporary SQLite files.

Found **six** additional scopes of `with self._connect() as conn:` in `atlasquant_aion_nonce_registry.py::PersistentNonceRegistry`. This commits/rolls back via sqlite3 context manager but never deterministically closes the native handle. Includes schema init, nonce claim (duplicate/replay denial), contains, read_claim, count and schema version reads.

G96 tests-first added four real temporary SQLite spy cases asserting **native `close()` exactly once**, no usable raw handle after scope, successful claim and idempotent/replay denial semantics, and preservation of an injected SQL exception. Registered raw-fd fixture cleanup runs even on genuine RED and precedes Windows temp directory removal.

**RED before production changes**, [run 40329518692](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40329518692): Ubuntu `Ran 4 tests`, **16 assertion FAIL**; Windows `Ran 4 tests`, **16 assertion FAIL and 3 ERROR**. Failures are subtest contracts across four cases, not 19 independent vulnerabilities.

## Minimal patch and cross-OS GREEN

**Exact corrected code SHA `372333558dec8a16bbb188f3a1dc7d1fed6cfbce`**: in the nonce registry only, add `from contextlib import closing`; replace six original `with self._connect() as conn:` scopes with `with closing(self._connect()) as conn, conn:`. The inner sqlite3 transaction manager commits/rolls back before outer closing releases the underlying native handle. No schema, SQL, replay decision, signature or permission changes.

[Corrected G96 CI 40329642624](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40329642624) — **Ubuntu 4/4 PASS**, **Windows 4/4 PASS**, and all four invariant markers present in both logs:
- `G96_NONCE_SCHEMA_GREEN=PHYSICAL_CLOSE`
- `G96_NONCE_CLAIM_GREEN=SUCCESS_AND_REPLAY_CLOSE`
- `G96_NONCE_READS_GREEN=ALL_FOUR_CLOSE`
- `G96_NONCE_SQL_ERROR_GREEN=PRIMARY_ERROR_PRESERVED_AND_CLOSED`

**Independent broader verification**: G97 Draft #1588 on exact G96 corrected code re-runs all 17 previously Windows-locked B2B modules, both OS's original 6,449-case Quality selector, and Ubuntu original Security (workflow [40330164503](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40330164503)). Results are not claimed before completion; G96's four passing test cases cannot certify all other native handles.

## Remaining external NO-GO
These local native lifetime fixes do not pin the internal SQLite VFS fd/inode, prove same-inode antirollback after restore, furnish independent monotonic custody, authenticate original business identity or owner, establish external root fingerprints, live first SEND or provider ACK-loss reconciliation. External A184 red acceptance remains five true unmet requirements. Do not merge/deploy/run Worker or transact funds.

**0/6 P0 HOMOLOGATED · HARD NO-GO · NO MERGE/DEPLOY/REAL SEND.**
