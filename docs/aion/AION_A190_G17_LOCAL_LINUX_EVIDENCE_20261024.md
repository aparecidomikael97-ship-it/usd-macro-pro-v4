# A190 G17 — local Linux evidence plus independent GitHub Linux CI

**Date (client timezone America/Manaus): 2026-10-24. LAB-only Draft; no production or customer DB.**

## Exact source/test inputs

- C SQLite extension blob: `6e9f9dd568153552d69bfd4b704cf6edb22edb61`.
- Python stdlib test suite blob: `bbd61c7df0d3e6556307b9f8ea7b48b934069d6e`.
- Official headers downloader blob: `b504459a3fef5c47682fdac445d5b98aa68b17ac`.
- SQLite 3.54.1 official SDK zip `https://www.sqlite.org/2026/sqlite-amalgamation-3540100.zip`, validated **SHA3-256 `92281c86e2957f9b9305890f9ac04204caa7b677cc868dc326d942689df28e30`** before selectively extracting `sqlite3.h` and `sqlite3ext.h` in `/tmp/aion_g17_sdk`.
- Compiler GCC 13.3.0. Compiled with `-std=c11 -O2 -Wall -Wextra -fPIC -shared` from exact GitHub C blob fed by stdin to gcc, output `/tmp/aion_g17_probe.so`; **exit code 0, no warnings**.
- Python 3.12.14, local Python stdlib SQLite **3.53.1** on Linux x86-64. Uses official SQLite extension API table, not APSW.
- The compiled binary was explicitly loaded into **per-test synthetic temporary sqlite3.Connection objects only**, with further loadability disabled in finally; temporary SQLite data cleaned by unittest.
- These were agent-observed local command results, not GitHub Actions logs, external trusted witness or reproducible binary provenance.

## Local observed transcript

```text
test_01_real_stdlib_connection_unchanged_file_returns_zero ... ok
test_02_loading_revoked_immediately_but_registered_function_works ... ok
test_03_native_in_memory_database_has_no_physical_handle_and_denies ... ok
test_04_backup_clone_preserves_marker_but_not_payload ... ok
test_05_same_marker_path_restored_cloned_stdlib_connection_denies ... ok
test_06_preopened_rogue_and_decoy_separate_real_sqlite_connections ... ok
test_07_sql_function_is_direct_only_no_sql_view_execution ... ok
test_08_wal_mutation_does_not_prove_sidecar_or_external_custody ... ok
Ran 8 tests in 0.054s
OK
G17_PYTHON_STDLIB_REAL_CONNECTION=HAS_MOVED_ZERO_OBSERVATION_ONLY
G17_EXTENSION_LOADING_REVOKED_AFTER_REGISTRATION=OBSERVED
G17_NO_NATIVE_MAIN_FILE=FAIL_CLOSED
G17_SAME_MARKER_CLONE_DIFFERENT_PAYLOAD=ADVERSARIAL_SETUP
G17_STDLIB_NATIVE_SAME_MARKER_ABA=MOVED_DETECTED
G17_STDLIB_ROGUE_PREOPENED_PLUS_DECOY=CONNECTIONS_DIFFERENTIATED
G17_DIRECTONLY=UNTRUSTED_VIEW_CANNOT_CALL_NATIVE_PROBE
G17_STDLIB_WAL_NATIVE_MAIN=UNMOVED_NOT_SIDE_CAR_PROOF
```

**Interpretation:** The exact native Python `sqlite3.Connection` VFS in Linux detected the known same-marker clone misbinding and distinguished preopened rogue versus decoy. This is more direct than G16 APSW. This does **not** bind native code to the currently running AION store or prove that files/sidecars cannot be swapped before or after a check.

## Independent GitHub Actions confirmation

Exact tested code + workflow SHA: **`b19b8a074c1a9bfa465429e1fe18fb9891d5b73d`** (later docs-only commits are not re-tested).

- [Workflow G17 run #40090452224](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40090452224): **completed / SUCCESS**.
- Ubuntu job **120861864007**: official pinned header download SHA3 step **SUCCESS**, GCC native extension compile step **SUCCESS**, stdlib `sqlite3` adversarial `unittest` step **SUCCESS**.
- Observed native test log: **`Ran 8 tests in 0.070s` / `OK`**, all 8 individually `... ok`.
- Logs show `G17_STDLIB_NATIVE_SAME_MARKER_ABA=MOVED_DETECTED`; `G17_STDLIB_ROGUE_PREOPENED_PLUS_DECOY=CONNECTIONS_DIFFERENTIATED`; `G17_DIRECTONLY=UNTRUSTED_VIEW_CANNOT_CALL_NATIVE_PROBE`; `G17_NO_NATIVE_MAIN_FILE=FAIL_CLOSED`.
- Separate agent local Linux 8/8 is corroboration but not a second independent host CI. Do not count 16 unique tests; 8 unique scenarios were run on two Linux environments.
- **Windows has not been run.** This workflow deliberately targets Linux. Canonical Quality/Security not rerun for G17. Native extension not integrated into AION runtime; no production GO.

**0/6 P0 homologados · HARD NO-GO · UNCERTAIN · ZERO_AUTO_RESEND.**

**0/6 P0 homologados · HARD NO-GO · UNCERTAIN · ZERO_AUTO_RESEND.**
