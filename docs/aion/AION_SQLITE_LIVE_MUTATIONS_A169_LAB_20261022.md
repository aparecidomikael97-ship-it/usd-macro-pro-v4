# AION A169 — Real filesystem mutation probes (LAB, 2026-10-22)

**Scope:** an adversarial LAB probe stacked on Draft #1458 -> #1457 -> #1195. No production execution or Worker, no merge or deployment, no credentials, no external provider effects. This block adds **tests**, not a claim of eliminating filesystem races.

## Test protocol

All databases are created by SQLite inside temporary directories on the CI runner. A small instrumented subclass acts between the facade's observations, while the facade and SQLite still use real OS descriptors and real SQLite connections. No remote filesystem is tested.

| ID | Probe | Meaning of the observation |
| --- | --- | --- |
| A169-01 | `os.replace` DB after facade's OS anchor but before the native SQLite `__init__` | If OS allows the replacement, path check must fail closed at `CHANGED_DURING_OPEN`; if OS denies replacement, record `OS_DENIED` without claiming attack detection. |
| A169-02 | `os.replace` after native SQLite is open but before facade's final path check | If OS allows it, facade must report `CHANGED_DURING_OPERATION` and latch FAILED; OS refusal is a separate outcome. |
| A169-03 | `os.replace` path away and back to the original **same inode** during an operation | If OS allows ABA, the simple dev/inode observations and independently held anchor may miss it: explicitly log `ABA_COMPLETED_NOT_DETECTED`. An expected blind spot is **not** a green security certificate. |
| A169-04 | A separate real SQLite connection commits to same DB inode during facade operation | Commit should be visible on later readback; stable inode is not content integrity or rollback attestation. |
| A169-05 | An intermediate directory component is a symlink | When creation is permitted, the final file's inode checks accept the path; this documents missing ancestor-chain attestation. When symlink creation is disallowed, test is formally skipped. |

The matrix retains 47 inherited tests plus these five scenarios. On platforms where A169-05 is skipped, report the skip explicitly. Run both Ubuntu and Windows. The attempts and classification are in the GitHub Actions logs; do not infer a Windows filesystem primitive was exercised solely because a test returns OK.

## Security judgment

- A169-01/02 observe a fail-closed property **only when a replacement actually happens**.
- A169-03 and A169-05 are intentional counterexamples/visibility limits, not hardening evidence.
- Same-inode concurrent writes and possible WAL/SHM effects mean a path identity check does **not** prove immutability.
- An independent anchor descriptor is not SQLite's native VFS descriptor. These tests cannot prove atomic SQLite file binding or defeat a hostile administrator, physical rollback, inode reuse, or compromised kernel.
- A production fix for untrusted host/filesystem behavior would require a revised trust boundary, independent witness/monotonic evidence, and platform-specific atomic primitives. No such proof is available in this block.

**Governance unchanged:** HARD NO-GO; ZERO_AUTO_RESEND; 0/6 P0 homologados. Historical Quality occurrences remain unresolved; do not relax any critical gate to green the suite.
