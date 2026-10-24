# A190 G14 — Local SQLite native marker against same-path ABA (LAB, 2026-10-23 Manaus)

## Directly observed cause

A183 demonstrated that the AION facade could open one SQLite file through the native connection while the host pathname had been renamed away and back. The independent OS pathname descriptor and PRAGMA database_list both appeared to refer to the expected name. A read could return contents of the **wrong native SQLite file**. A write could commit on the detached file before a post-operation alarm.

This is the P0 SQLite identity problem. Python's sqlite3 wrapper does not expose a verified native SQLite VFS main-file descriptor; existing OS inode checks cannot atomically prove that the native connection is bound to the same object. G14 **does not solve that fundamental missing primitive**.

## Bounded real-runtime hardening

G14 changes real aion_chat/store.py and aion_chat/staged_store.py in isolated Draft LAB:

1. Each SQLiteChatStore bootstraps a local UUID marker in a single-row aion_native_marker_v1 SQLite table (existing marker preserved on reopen). Invalid marker content fails the native startup.
2. OperationScopedSQLiteChatStore pins this local marker at the first healthy operation of its facade, beside the existing pathname/inode/ancestor-chain checks.
3. Before using a reopened native SQLite connection, the facade requires the same marker. A same-path ABA using a **separately initialized SQLite file** has a different marker and is denied before the user operation.
4. After each native operation, the marker is checked again. A post-write mismatch is reported as G14_NATIVE_MARKER_POST_OPERATION_OUTCOME_UNKNOWN, and the handle latches; the write may have committed and MUST NOT be automatically replayed.
5. Existing A183 same-filename tests are preserved and updated to assert the now-expected denial. The original pre-G14 RED remains in Git history and CI evidence.
6. Additional LAB tests check legitimate WAL writes, reopen, malformed marker, postcommit drift, backup semantics and **same-marker clone adversarial failures**.

## Exactly what the marker is NOT

- A marker is copied by backup or byte-identical rollback. An attacker who can clone a valid database clones its marker too. This is not a monotonic counter nor rollback resistance.
- The host can modify the table at will, recreate the database, patch the process or mount a VFS driver that redirects native sqlite3 connections. This does not prove independent issuer, owner identity, file-descriptor consistency or trusted recovery.
- The first healthy open pins what that **same process** sees. If the host has redirected the first open, there is no independent authenticity proof.
- A previously opened native connection can still point at a **clone preserving the same marker** while the separate OS anchor sees the original. G14 tests retain this as a **RED** for both read and write, subject to Windows filesystem denial.
- Journal/WAL sidecars and SQLite native file controls are not cryptographically attested. Neither of the two SQLite P0 compatibility/identity conditions is homologated.

## Exit criteria (not met)

A genuine fix needs native VFS/file-control identity bound **atomically** to the actual SQLite connection (with cross-OS compatibility), rollback-resistant externally controlled state, restart recovery, and negative end-to-end validation. A local UUID detector alone cannot close these gates.

All tests use disposable temporary files. No production migration, release, Worker, provider call, account, customer, spending or merge.

**0/6 P0 homologados · HARD NO-GO · UNCERTAIN · ZERO_AUTO_RESEND.**

## CI evidence

After the targeted Ubuntu/Windows suite runs, record exact tested SHA, job IDs, test counts and first-run failures in a separate evidence document. CI success may include passing RED counterexamples.
