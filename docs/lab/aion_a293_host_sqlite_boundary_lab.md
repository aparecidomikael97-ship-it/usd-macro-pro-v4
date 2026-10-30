# A293 — Host-controlled SQLite boundary probes (LAB only)

**Gate:** HARD NO-GO production and integration; synthetic, disposable SQLite
files only. **P0 homologated: 0/6.** No Worker, deploy, real orders, provider
sends, external authority, service subscriptions, or auto-resend.

This laboratory follows A292's write inventory. It exercises three *different*
failure models against the actual `SQLiteChatStore` implementation, rather than
claiming that the local SQLite authorizer and COMMIT marker form a security
boundary against the host.

## Experiments

### 1. Independent process commits a direct SQL change

A separate `sys.executable -c` process opens the same temporary SQLite
database and updates an existing conversation title. The process does not
possess or invoke the current store's cooperative write gate and never creates
its pending COMMIT marker. An independent SQLite reader confirms the change.

- With **opt-in strict** `PRAGMA data_version` checking, a *later* guarded
  read detects the external commit and leaves the local store FAILED.
- With **default multi-writer** setting, the same guarded read is allowed:
  the original local connection has no authority to prevent the external
  process from writing.
- Even in strict mode, detection is **after** the malicious or unexpected
  effect is durable. It is not an external authorization or rollback witness.

### 2. Older valid file replaces the closed database (host rollback)

A disposable store records conversation C. After closing all connections, we
copy the valid database file as an old snapshot. Reopen, append message M,
close, and verify M is committed. Next, use `os.replace` on the **closed**
temporary path to put the older valid bytes back.

The fresh strict-mode store accepts the rolled-back file as a new healthy
baseline, with M gone and no pending COMMIT marker. This is a **negative
finding**: local `data_version`, path identity and a removable marker do not
prove antirollback across restarts. No recovery or automatic send is attempted.

### 3. Hot pathname swap while the store is open

On **POSIX only**, `sqlite3.Connection.backup` creates a valid replacement,
then the pathname is atomically swapped while the original connection is open.
The local pathname/inode check detects `PATH_IDENTITY_CHANGED` on its next
explicit guard and stays FAILED. This is only a pathname check; it does **not**
authenticate SQLite's native file handle, inode contents, WAL state or VFS.

On **Windows**, hot replacement of an open SQLite file is platform-dependent
and is reported as **UNTESTED**, not silently marked as passed. The Windows
runner still executes the independent-process and closed-file rollback tests.

## Interpretation

| Threat | Local observation | Security limit |
| --- | --- | --- |
| Independent SQLite process | Strict mode detects *later*; default allows | Cannot authorize or block other PIDs |
| Closed-file host rollback | Valid older history accepted | No independent off-host witness |
| POSIX live pathname replacement | Local inode mismatch detected by explicit guard | Not native FD/VFS proof |

These tests show bounded behavior, not an integrity guarantee against
privileged host control. The `get_conversation` implementation can perform an
SQL read before its post-read guard; a local failure indication must never be
misreported as an atomic read-before-effect boundary.

## Repeat

```bash
python -m unittest -v labs.test_a293_host_sqlite_boundary_lab
python -m unittest -v labs.test_a292_staged_chat_write_inventory_lab
python -m unittest -v labs.test_a291_chat_write_gate_commit_fence_lab
python -m unittest -v labs.test_a290_sqlite_local_write_gate_lab
```

The new isolated GitHub Actions workflow runs Python 3.12 on standard Ubuntu
and Windows public-repository runners. It does not access customer databases,
spawn service workers or call providers. No third-party packages are needed.

## Authority and closure

**GO-LAB if regression tests pass; NO-GO integration; HARD NO-GO production.**
Nothing in A293 changes the core store; no external identity signer,
host-independent antirollback custodian, native VFS/FD proof, independent
authority approval or canonical P0 evidence is delivered. **0/6 P0** remain
homologated. **ZERO_AUTO_RESEND** remains mandatory.
