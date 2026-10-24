# A190 G16 — evidence for *local Linux* execution (not canonical CI)

**Date (user client):** 2026-10-24. **Authorization:** LAB only, PR Draft #1503. Never treat these notes as independent attestation, P0 closure or Windows result.

## Exact tested inputs
- Branch at source extraction: `lab/aion-a190-g16-native-file-control-bridge-20261024`, HEAD `30acdb5bcd1f961e8e79b91e160d2a5c06dbeb78`.
- Probe module Git blob `4b2811239487610d208b0c0d11c67ea0e9789a4e`.
- Test module Git blob `80c3e0da2fa113ce11c80e11bb877474671a9e13`.
- APSW `3.54.1.0`, SQLite bundled `3.54.1` (verified via `apsw.apswversion()`, `apsw.sqlitelibversion()`).
- Python `3.12.14`, `Linux-6.18.55-x86_64-with-glibc2.39`.
- Isolated installer target: `/tmp/aion_g16_apsw` with `--no-deps --only-binary=:all:`. No application environment changed.
- Source and tests fetched as exact GitHub file bodies, compiled and executed in-memory with `unittest`; test-created SQLite databases lived inside per-test `TemporaryDirectory` and were cleaned by the test.

## Direct observed local stdout (summary)

```text
test_01_has_moved_runs_on_actually_opened_connection ... ok
test_02_clone_keeps_local_marker_and_differs_in_payload ... ok
test_03_native_has_moved_detects_same_marker_transient_swap ... ok
test_04_preopened_rogue_plus_decoy_does_not_fool_connection_control ... ok
test_05_windows_native_handle_matches_independent_real_path ... ok
test_06_windows_native_handle_denies_incorrect_target_path ... ok
test_07_fake_host_file_control_cannot_be_external_trust ... ok
test_08_wal_scenario_still_not_receipt_or_rollback_proof ... ok
Ran 8 tests in 0.061s
OK
G16_OFFICIAL_HAS_MOVED_UNSWAPPED=G16_NATIVE_HANDLE_NOT_MOVED_OBSERVATION_ONLY
G16_SAME_MARKER_DIFFERENT_BYTES=ADVERSARIAL_SETUP_CONFIRMED
G16_NATIVE_VFS_SAME_MARKER_ABA=MOVED_DENIED_ON_LINUX
G16_PREOPENED_ROGUE_VS_DECOY=NATIVE_CONNECTIONS_DIFFERENTIATED
G16_WIN32_NATIVE_HANDLE=OTHER_OS_DENIED
G16_WINDOWS_WRONG_ANCHOR_PATH=MISMATCH_OR_NON_WINDOWS_DENY
G16_CALLER_CONTROLLED_FAKE_MAY_REPORT_SAFE=NOT_EXTERNAL_TRUST_RED
G16_WAL_NATIVE_MAIN_OBSERVATION=SIDE_CAR_AND_ROLLBACK_UNPROVEN
```

**Nuance:** tests 05 and 06 execute and pass the *non-Windows unsupported branch* under Linux; they DO NOT validate the Windows native Win32 APIs. This is 8/8 Linux test methods, not 8 native cross-platform proofs.

## GitHub CI state and changes after local run

G16 workflow exists but `github_fetch_commit_workflow_runs` returned **no run** for HEADs `c8e2bbbb8ae6550681d85153fdd962a0e5cc596d` and `30acdb5bcd1f961e8e79b91e160d2a5c06dbeb78`. A mirrored G16 job was added to the prior G15 workflow on commit `47cc2b696e11139463f5e039f321869fa1dd56be` to attempt triggering Windows/Ubuntu. At time of writing, **no G16 GitHub run/job log has been observed or certified**. Verify future SHA and jobs independently before declaring cross-platform success.

## Security conclusion

Same native Linux connection `SQLITE_FCNTL_HAS_MOVED` can deny the G14 same-marker transient clone when observed after the swap; it does distinguish rogue and decoy connections in this isolated APSW test. It **does not yet protect the stdlib Python `sqlite3.Connection` running in AION**, does not pin atomically across race/writes and restart, validate WAL/SHM, trust a hostile host, prove owner identity, signed provider receipts, or rollback custody.

**0/6 P0 homologados · HARD NO-GO · UNCERTAIN · ZERO_AUTO_RESEND.**
