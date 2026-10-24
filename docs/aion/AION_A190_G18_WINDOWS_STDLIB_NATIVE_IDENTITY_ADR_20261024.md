# A190 G18 — Windows exact Python stdlib SQLite native file identity (LAB)

Date: 2026-10-24. Base G17 Draft PR #1504, commit `82e4cb0381c53c2d5cee38d007b1fb12e89f6a00`.

## Hypothesis and scope

G17's `SQLITE_FCNTL_HAS_MOVED` was validated on Linux only. Windows requires its own VFS-specific native evidence. The G18 loadable C extension registers a `SQLITE_DIRECTONLY` function on a **synthetic Python stdlib `sqlite3.Connection`**, obtains the **exact current connection** with `sqlite3_context_db_handle`, invokes `sqlite3_file_control(db, "main", SQLITE_FCNTL_WIN32_GET_HANDLE, &handle)`, and reads Win32 volume serial + file index from `GetFileInformationByHandle`. Python separately opens an expected path with `CreateFileW` and compares the identities. Missing handles, unsupported VFS, missing anchor and API failures must DENY.

This is a **local snapshot observation**. It is not a host-independent signed claim, rollback-resistant custody, atomic WAL/SHM attestation, external owner authentication, first-attempt receipt, or proof of recovery after restart. Windows may prevent same-path rename while SQLite has open handles: a clone on a different path tests native identity, **not** a successful Windows same-path ABA exploit. The anchor path is itself host-controlled.

## Nine synthetic Windows tests

1. Actual stdlib connection matches independent Win32 anchor.
2. Same-marker cloned DB differs in payload and native file identity.
3. Preopened rogue connection plus honest decoy cannot substitute the rogue handle.
4. Missing expected anchor denies.
5. `:memory:` lacks native main file and denies.
6. Further extension loads disabled immediately after registration.
7. `SQLITE_DIRECTONLY` rejects untrusted SQL view.
8. WAL main identity matches, explicitly **does not attest WAL/SHM**.
9. Two real connections to one file share local identity.

## Supply-chain and execution restrictions

- **Unsigned native loadable code executes arbitrary instructions. NEVER load this artifact into the real AION runtime or customer data, install it as a dependency, auto-load it, or use it as a production authorization gate.**
- GitHub Actions `windows-latest` with MSVC compiles only the LAB C source; official SQLite headers come exclusively from G17's hash-pinned SDK fetcher.
- No main/merge, deploy, Worker, provider call, credential, cloud account, customer effect, expense or security gate bypass.
- This draft is a candidate until an exact GitHub Actions run and job logs confirm compilation and tests. A green synthetic run would not homologate P0-5 or P0-6.
- Quality/Security canonicals are not automatically covered by this synthetic-only workflow.

**0/6 P0 homologated. HARD NO-GO. UNCERTAIN. ZERO_AUTO_RESEND.**
