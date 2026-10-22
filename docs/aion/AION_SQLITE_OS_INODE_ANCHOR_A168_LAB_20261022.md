# AION A168 — OS inode anchor for SQLite staged facade (LAB, 2026-10-22)

**Scope:** Draft branch stacked on Draft #1457 (which itself is stacked on #1195), not on main. No merge, deploy, Worker activation, external provider call, credentials, or production write. HARD NO-GO.

## What changes

The staged operation facade previously compared `Path.lstat()` identity around the SQLite call. This block additionally opens a **separate read-only OS file descriptor** for the database file, keeps that descriptor open until after the native SQLite connection closes, and compares `os.fstat(fd)` identity against the path observations:

1. On an existing DB, open a descriptor before constructing the native SQLite connection. Use `O_NOFOLLOW`, `O_NONBLOCK`, and `O_CLOEXEC` **only where the runtime exposes them**, with `O_BINARY` where available. Fail closed if opening or inspecting the anchor fails or the descriptor is not regular.
2. Compare the descriptor with the path before/after SQLite open, before invoking the requested method.
3. Compare again after the method. If the observation fails after a write may have committed, the result is **UNKNOWN**, the facade latches FAILED, and no automatic replay or resend is permitted.
4. Close native SQLite first and the separate descriptor afterward. An OS descriptor close error latches FAILED; a write may already have committed.
5. On the first bootstrap where no DB file exists yet, native SQLite creates the database first; an anchor is then opened and verified before exposing any result. This path has a different initialization race profile and is **not** equivalent to pre-open anchoring.

## Regression matrix

Six new offline tests cover supported open flags, `fstat` inode mismatch, `os.open` failure, nonregular opened descriptor, post-open/pre-write rejection, and post-write uncertain outcome with readback showing exactly one committed message. Faults are synthetic/injected; regular SQLite interactions and the committed message are real local SQLite.

Expected dedicated matrix once CI runs: 37 inherited baseline + 4 previous path-identity regressions + 6 new anchor regressions = **47 tests per OS**. Do not mark green until **both** Ubuntu and Windows jobs prove it.

## Limits and non-claims

- **The anchor is NOT SQLite's internal VFS handle.** Python's standard `sqlite3.Connection` does not expose that native descriptor. The independently pinned OS handle cannot prove that SQLite used the same inode at every instant.
- An adversarial pathname swap between checks (including an ABA swap that restores the same path identity) remains possible. On platforms lacking `O_NOFOLLOW`, even the anchor open is not an atomic no-follow protection. Ancestor directory symlinks/junctions are not proven safe.
- `st_dev/st_ino` equality is **not** content integrity, WAL/SHM integrity, historical monotonicity, host administrator separation, cryptographic receipt, or independent custodian attestation.
- Windows and POSIX open/rename/share behavior differs. Green CI confirms supported tests, not equivalence under a malicious OS or filesystem.
- No production claim about rollback resistance, proven external side-effect zero, producer receipt authenticity, ownership proof, or P0 acceptance follows from this block.

**Gates unchanged:** `HARD NO-GO`, `ZERO_AUTO_RESEND`, `0/6 P0 homologados`. Quality's historic 85 occurrences are not closed by these six tests.
