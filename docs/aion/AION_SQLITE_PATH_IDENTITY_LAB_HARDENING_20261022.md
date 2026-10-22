# AION P0 — SQLite staged path identity hardening (2026-10-22)

**Scope:** isolated LAB only, stacked on unmerged Draft #1195. NO-GO for production and Worker. No merge, deployment, host installation, external effect, credential, or paid service is authorized by this branch.

## Motivation and invariant

The operation-scoped SQLite facade from Draft #1195 checked the bound path before opening the native SQLite connection, but did not check the path identity between opening and executing the requested method, nor after method execution. This LAB change adds observations at all three boundaries. A different path identity cannot produce an ordinary success response after being detected. Once detected, the affected facade latches a failed state and refuses further operations.

## Laboratory acceptance behavior

| Observation | Required behavior |
| --- | --- |
| Final DB path is a symlink (including Windows-style reparse behavior exposed as a symlink by `lstat`) | Deny before native SQLite open with `BOUND_DATABASE_SYMLINK_DENIED` |
| Final DB path is not a regular file | Deny before native open with `BOUND_DATABASE_NOT_REGULAR_FILE` |
| Previously bound `st_dev/st_ino` differs before operation | Deny with `BOUND_DATABASE_REPLACED` |
| Identity differs immediately after native SQLite open | Deny before requested method with `BOUND_DATABASE_CHANGED_DURING_OPEN` |
| Identity differs after requested method | Deny ordinary success with `BOUND_DATABASE_CHANGED_DURING_OPERATION`; mark facade failed |
| Post-operation drift occurs after a write | **Outcome UNKNOWN:** a commit could already exist. No transparent replay or automatic resend; separate evidence and independent readback are required. |

Four new deterministic regression tests exercise the alias, nonregular path, after-open drift, and after-commit uncertainty behaviors. They supplement the inherited SQLite lifecycle, host-staging, and resilience suites. The dedicated Ubuntu and Windows matrix is the acceptance gate; do not count expected tests as passing until the actual CI finishes.

## Boundaries that are NOT proven

- A sequence of `lstat` calls is **not** atomic binding of the SQLite file descriptor. A hostile or compromised host can race between observations and native SQLite activity.
- The final-component check does not authenticate the entire parent directory chain, filesystem, kernel, or host administrator.
- Same-inode content tampering, copy/restore, replacement of WAL/SHM, inode reuse, backup rollback and cross-host independence are **not** solved.
- A passing CI job or readback on the same host does not constitute an external nonrollback custodian witness, producer receipt, independent identity proof, or P0 homologation.
- This module does not grant release authority to the Worker or resolve the Quality historic activation/independent producer gate red baseline.

## Next security decision

Keep `HARD NO-GO`, `ZERO_AUTO_RESEND` and `0/6 P0 homologados` unchanged. A production-grade design would require atomic OS handle-based identity pinning and platform-specific verification plus external witness/producer evidence before any claim of rollback resistance or real-operation safety.
