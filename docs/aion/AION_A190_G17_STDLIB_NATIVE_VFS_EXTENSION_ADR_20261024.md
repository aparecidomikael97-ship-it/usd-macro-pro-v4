# A190 G17 — exact Python stdlib sqlite3 native VFS probe (LAB only)

## Problem and proven previous gaps

G14 protected distinct local SQLite UUID markers but backups/clones retain them. G15 demonstrated Linux process descriptor deltas cannot identify the file used by one specific connection when a decoy is present. G16 obtained the first same-connection VFS results through experimental APSW, but AION currently uses Python's standard `sqlite3` library.

**G17 is a LAB-only feasibility demonstration** that the standard `sqlite3.Connection` itself can invoke SQLite's documented `SQLITE_FCNTL_HAS_MOVED` through a small **explicitly loaded C extension**. It is not a production-ready security mechanism.

## Documented interface (no CPython internals)

1. Python `sqlite3.Connection.enable_load_extension(True)` exclusively for the synthetic test connection.
2. `load_extension(verified_temp_binary, entrypoint="sqlite3_aiong17_init")` registers a `SQLITE_DIRECTONLY` read-only SQL function `aion_lab_native_has_moved()`.
3. Immediately call `enable_load_extension(False)`, including on load errors.
4. In its execution, the C function gets **the exact running SQLite connection** using `sqlite3_context_db_handle(context)` and calls `sqlite3_file_control(db, "main", SQLITE_FCNTL_HAS_MOVED, &moved)`.
5. Return `0` only for VFS-backed current-file observation, `1` for moved-file denial, otherwise SQL error / fail closed.

This does not enumerate process FDs, compare a separate unrelated connection, require undocumented CPython C layout, or allow a caller-supplied fake marker to stand in for native VFS identity.

## LAB security boundary

The extension is **native executable code**. SQLite permits arbitrary native extension behavior if loadable code is malicious. Therefore:
- Never enable SQLite extension loading for customer data, production, services, default app boot, or a live AION process in this experiment.
- Do not merge/deploy/install extension artifact as-is; no signed distributor or publisher identity or independent trusted binary digest exists.
- `SQLITE_DIRECTONLY` reduces exposure through untrusted views/triggers but does **not** sandbox a malicious extension binary.
- The test disables further extension loading but the registered native function stays in the synthetic connection until close. This is expected and must not be mistaken for removing code.
- Only official SQLite 3.54.1 SDK headers are downloaded (SHA3-256 locked); no arbitrary ZIP extraction. The local `sqlite3` engine may be a different version but uses the stable extension API table.
- No Windows build/test is claimed. Windows default VFS may not implement `HAS_MOVED`; the G16 Windows HANDLE approach remains unvalidated.

## Required before any actual runtime integration

- Independent security review of C source, threat model and native artifact supply-chain; host trust, signed binary validation, recovery and crash behavior.
- Windows-native path/handle tests and a supported alternative to `HAS_MOVED` where unavailable.
- Explicit per-operation pre/open/post checks on the **same live connection**; handle path and ancestors, sidecar binding/WAL, concurrent writers, and rename/restore races.
- Postcommit mismatch = **UNCERTAIN**, preserve durable intent and **never automatic retry**.
- Owner identity and independently authenticated provider receipts plus monotonic external checkpoint are *separate* P0 gates.
- Quality/Security canonical coverage with tested SHA, independent witness, and real deployment review. A green synthetic suite is not homologation.

### Official interface references

- https://www.sqlite.org/loadext.html
- https://www.sqlite.org/c3ref/file_control.html
- https://www.sqlite.org/c3ref/context_db_handle.html
- https://www.sqlite.org/c3ref/c_fcntl_begin_atomic_write.html
- https://docs.python.org/3/library/sqlite3.html#sqlite3.Connection.load_extension

**0/6 P0 homologados · HARD NO-GO · UNCERTAIN · ZERO_AUTO_RESEND.**
