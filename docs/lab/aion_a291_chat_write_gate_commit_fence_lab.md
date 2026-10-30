# A291 — Compose a local SQLite write gate with the REAL chat COMMIT fence

**Research LAB only; HARD NO-GO; P0 homologated 0/6;
ZERO_AUTO_RESEND; no paid service, Worker, deploy, provider sends or orders.**

## Why this experiment exists

A289 showed that a Python SQLite authorizer is checked when SQL is
compiled, not on every execution; prepared-statement cache may retain an
expired local Boolean grant. A290 tested cache-free and rearm variants
with a synthetic SQLite table, and showed that whoever holds the raw
Python connection can disable the authorizer.

A291 now composes the rearmed local authorizer with the **real**
SQLiteChatStore's A247/A250/A251 pre-COMMIT pending marker in the
A288 strict local-version staging mode. No aion_chat/store.py changes.

## Native test procedure

1. Create a temporary file-backed SQLiteChatStore using actual
   create_conversation and append_message methods.
2. After every authorized chat write, re-install set_authorizer to
   invalidate previously authorized cached statements.
3. Verify a direct raw UPDATE on the same handle is denied after
   a successful chat commit, including the exact cached SQL shape.
4. Use a sqlite3.Connection subclass that really calls
   super().commit(), then raises a **synthetic lost ACK**. Distinguish:
   - before COMMIT: row count 0, marker kept, handle FAILED;
   - after COMMIT: row count 1, marker kept, handle FAILED.
5. In BOTH paths, a blind second append is denied and reopening
   encounters the pending marker. A real second connection observes
   the number of rows after each attempt.
6. Negative control: a same-process caller can call
   store.db.set_authorizer(None), write raw SQL, and still see a
   green local data_version and quick_check. This is NOT a trust root.

## Fail-closed invariant under test

An unconfirmed COMMIT MUST NOT turn into a known safe failure or
authorize an automatic retry. The local marker must survive until
manual review. Whether the COMMIT really persisted is unknown to the
application at the ACK-loss boundary, even though the synthetic
test harness may inspect the local database afterward.

## What remains unresolved

- This same-process authorizer cannot distinguish genuine code ownership
  or resist raw Python handle access, host control, VFS/FD replacement,
  same-inode rollback, or a malicious administrator.
- The local pending marker is deletable/rollbackable by the host and
  is not a durable off-host witness. Reopening does not restore trust.
- No external provider receipt or delivery effect is in these tests.
- No P0-5 or P0-6 promotion. The built-in COMMIT marker is only a veto.
- The companion authorizer is not applied to all SQLiteChatStore methods,
  and remains a test-only facade, not an operational guard.

## Acceptance criteria

18 new A291 unit tests plus A285–A290 regressions in Ubuntu and
Windows Python 3.12, pinned standard GitHub-hosted runners (free for
the public repository). No external package or new subscription.

Next possible LAB: enumerate all production-path staged-chat writers and
check that none bypasses the protected COMMIT lifecycle in ordinary
cooperative code. Still HARD NO-GO until independently witnessed P0s.
