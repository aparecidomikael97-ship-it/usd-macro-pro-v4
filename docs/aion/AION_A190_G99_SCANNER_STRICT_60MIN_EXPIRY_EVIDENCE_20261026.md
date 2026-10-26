# AION G99 — strict M15 scanner expiry at 60 minutes (LAB)

Date: 2026-10-26. Stacked on G98 Draft #1589, code baseline cb82a27e4e9d7d6a0b5b45d026b987d60d2691ee.

## RED

Original master_panel_v102.py::_scanner_for_pair considered age <= 60.0 fresh, contrary to test_scanner_freshness_v1074 requiring exactly 60.0 minutes to be expired. Original test mocked _time.time, while age was computed by pd.Timestamp.now, creating a boundary race.

Five deterministic tests inject elapsed age 59.999 (fresh), 60.0 (expired), 60.001 (expired), None (expired), unavailable scanner (expired). Seven original scanner tests remain unchanged as selectors.

Prepatch [RED run 40336232171](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40336232171): Ubuntu 12 tests with 1 FAIL, Windows 12 tests with 2 FAIL. Those subcases reproduce a single threshold/fixture defect, not independent vulnerabilities.

## GREEN

Code commit 1c1bd40f6b33c514c85c71c1485570b1b2f670aa changes only the freshness condition to age < 60.0. Test commit 749fa5a21831cb231930f1ce63b50dc2342660e9 makes the original test deterministic by mocking the actual computed elapsed value to 60.0 and retaining both stale and age assertions.

[Corrected G99 run 40336582530](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40336582530): **12/12 PASS Windows**, **12/12 PASS Ubuntu**. Five G99 markers confirmed, including G99_AT_60=EXPIRED. No original tests waived/skipped or runtime trade authorization changes.

This only adjusts display data freshness. It is not authenticated market data, provider proof, external monotonic custody, independent trust root, first-SEND exactly-once or native SQLite VFS antirollback.

**0/6 P0 HOMOLOGATED; HARD NO-GO. No merge/deploy/Worker/real SEND/funds.**
