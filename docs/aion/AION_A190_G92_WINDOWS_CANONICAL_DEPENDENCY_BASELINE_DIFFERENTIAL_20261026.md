# AION G92 — Windows canonical Quality differential: G89 before vs G90 after patched deps

**Date:** 2026-10-26. **All evidence is LAB only; 0/6 P0 HOMOLOGATED; HARD NO-GO. No merge, deploy, Worker or real SEND.**

## Why the comparison was necessary

G90 Draft #1581 fixed 48 known `pip-audit` vulnerabilities and passed the unchanged canonical full Ubuntu Quality (6449), Security unittest (368) and Security pytest (2825); cross-OS canonical dependency audit passed with *zero known findings* on the updated pins. G91 Draft #1582 separately ran original canonical Quality on Windows and reported 6449 tests with 15 failures and 109 errors. That result **cannot** be attributed to the dependency update until verified against original requirements under the same Windows runner and A183 Python socket guard.

## Exact tests and paired results

| Evidence | Source checkout | Versions | Windows Quality result |
| --- | --- | --- | --- |
| [G91 candidate run 40325759222](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40325759222) | G90 upgraded stack `7cb7619df87293e2308def515ae0f7631f647199` | Streamlit 1.66.1, pypdf 6.21.2, Pillow 13.0.0 | `Ran 6449 tests in 155.456s`, `FAILED (failures=15, errors=109)` |
| [G92 historical baseline run 40326597735](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40326597735) | Exactly G89 pre-upgrade `b1808eb5bef98665c53ebf605cf3dcb322acdcb4` | Streamlit 1.64.0, pypdf 6.19.0, Pillow 12.3.0 (transitive) | `Ran 6449 tests in 175.350s`, `FAILED (failures=14, errors=109)` |

Both use Windows Python 3.12, pinned `pip==26.2.1`, `pytest==9.1.1`, `playwright==1.63.0` and unchanged `scripts/run_a183_canonical_lab.py quality`; same LAB socket deny. No selective test skipping, forced green or waivers.

**Result by category:**
- All **109 error entries** occurred in the *same 17 B2B SQLite durable execution / certificate test modules* before and after the dependency changes. Logs repeatedly show `PermissionError [WinError 32]` on temporary `execution.sqlite3` files (218 appearances in each log, generally repeated trace/cause).
- The **14 shared failures** are UI/admin/runtimes tests reporting `AssertionError: LAB network forbidden` under the offline socket mock.
- The sole additional G91 candidate failure is `test_scanner_freshness_v1074.ScannerFreshnessV1074Tests.test_exactly_60_minutes_is_stale_by_conservative_boundary`, asserting the exact 60-minute boundary should be stale. Its implementation `master_panel_v102._scanner_for_pair` currently admits `age <= 60.0` while the test requires staleness at exactly 60; `_minutes_since` calls `pd.Timestamp.now()` and the test only patches `_time.time`, so the float boundary may be timing-dependent. This is an observed one-run delta, **not proven caused by the G90 versions**. A separate deterministic source/test fix and Windows rerun are required to certify closure.

## Windows canonical Security independently checked on G90 candidate

G92 candidate Windows Security unittest [run 40326597735](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40326597735), job `121584784240`: **368/368 PASS**, `Ran 368 tests in 4.318s`, `OK`. The Windows checked-out canonical workflow bytes have a platform-specific SHA due to line endings; this is not used to claim a changed logical selector.

G92 candidate Windows Security pytest, job `121584783566`: **1 FAIL, 2823 PASS, 1 SKIP**. Failure: `test_atlasquant_aion_v26_core_health_adapter.py::test_real_admin_builder_replaces_client_claim_and_loads_only_once` via `AssertionError: LAB network forbidden`. This is not a proven vulnerability or G90 dependency regression by itself. Independent pre-G90 Windows Security pytest baseline is being run in Draft G93 #1584; do not call it inherited until compared.

## Acceptance classification

**G90 audit remediation passes and is distinct from full Windows canonical Quality.** No evidence supports claiming the Windows entire 6449-test suite GREEN. The failure clustering shows 109 historical Windows-only database handle errors, separate from the G84–G89 focused local SQLite guards that passed. These old B2B SQLite tempfile-handle errors are still real compatibility blockers, not waived by Ubuntu success or by CVE remediation. No native VFS/owner attestation or rollback proof is established.

Five A184 external-red requirements remain genuinely unmet: independent monotonic custody/checkpoint, immutable authenticated original business identity, externally pinned trust root, authenticated native live SQLite VFS snapshot/version, same-inode rollback-proof write boundary.

**0/6 P0 HOMOLOGATED · HARD NO-GO · NO MERGE/DEPLOY/WORKER/REAL PROVIDER SEND/FUNDS.**
