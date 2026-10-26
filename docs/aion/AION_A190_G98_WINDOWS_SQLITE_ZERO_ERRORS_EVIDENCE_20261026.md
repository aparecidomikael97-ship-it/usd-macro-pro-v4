# AION G98 — Windows B2B fixture close / native SQLite handles (LAB)

Date: 2026-10-26. Parent G97 Draft #1588 source b2ac40dcf6ba7ebe5a75fd2a90fd7ab10b33b775. Parent includes G94: 26 deterministic SQLite durable execution close scopes, and G96: six persistent nonce close scopes. Draft LAB only. 0/6 P0 homologated, HARD NO-GO.

## Red evidence and narrow test-only patch

G97 [run 40330164503](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40330164503) on Windows ran all 17 formerly erroring B2B modules: 175 tests / 1 ERROR. The sole failing test, test_fresh_store_migrates_to_schema_v2_with_additive_tables, used a directly created sqlite3.connect() context manager inside a TemporaryDirectory. SQLite's Connection.__exit__ commits or rolls back without closing its native handle; Windows then failed to delete execution.sqlite3 with WinError32.

G98 test-only patch commit 545f266bf96b89aaef98d9da812b55704f1afd03 imports contextlib.closing and wraps exactly this one sqlite3 schema-inspection connection with an outer closing context. It preserves all original schema SQL/assertions, production logic, test counts, and security guards. No skip, xfail, exception masking or network-guard weakening.

## Objective G98 code checks

Run [40330695734](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40330695734), exact tested source 9bdbeb781fc2593f046582b7ad3b28b89f6e0c3a:
- Windows targeted all 17 B2B modules: 175/175 PASS, Ran 175 tests in 26.059s, OK, 0 errors (job 121599023358).
- Ubuntu original Quality: 6449/6449 PASS, Ran 6449 tests in 51.160s, OK (job 121599023733).
- Ubuntu original Security unittest 368/368 PASS, Security pytest 2825/2825 PASS (job 121599023835).
- Windows full original canonical Quality: 6449 tests, 0 ERROR and 15 FAIL (job 121599023674). All previously measured 109 Windows SQLite native WinError32 error entries were eliminated from this fixed branch. Full Windows Quality is STILL RED: 14 inherited UI/admin/runtime tests collide with A183 LAB socket deny ("LAB network forbidden"), and a separate scanner at-exactly-60-minutes freshness test fails intermittently due to time source discrepancy.

## Windows full canonical comparison — unchanged original selectors

| Code | ERROR entries | FAIL entries |
| --- | ---: | ---: |
| G91 on G90 dependencies (40325759222) | 109 | 15 |
| G95 with G94 close (40328832712) | 68 | 15 |
| G97 with G94+G96 nonce close (40330164503) | 1 | 15 |
| G98 with test-owned SQLite close (40330695734) | **0** | 15 |

Historical pre-G90 G89 base Quality on Windows G92 [40326597735](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40326597735) already had 109 errors and 14 UI network-guard failures. The 15th scanner failure was not consistently reproduced in the historical baseline; do not attribute it unambiguously to G90.

## Security limits unchanged

No independent monotonic custody, immutable authenticated owner/original business identity, externally pinned trust root, live SQLite VFS fd/inode attestation, native rollback-proof write boundary, proven real external first SEND, or H0 post-restart availability was demonstrated. A184 external RED still has five genuine unmet requirements. Correct local FD lifetime does not prove H0 or all six P0.

NO MERGE, NO DEPLOY, NO WORKER, NO REAL SEND, NO FUNDS. 0/6 P0 HOMOLOGATED. HARD NO-GO.
