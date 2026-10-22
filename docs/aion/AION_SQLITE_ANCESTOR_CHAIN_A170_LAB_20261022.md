# AION A170 — SQLite parent-chain alias and drift guard (2026-10-22 LAB)

**Only LAB / Draft:** stacked on A169 #1459 -> A168 #1458 -> SQLite path guard #1457 -> original SQLite Draft #1195. No merge, deploy, Worker, provider, paid dependency, or external side effects.

## Original finding

A169 reproduced the following on Windows and Ubuntu: a symlink in the **parent directory** is accepted by the final database filename's `lstat` and the independent OS descriptor. A169 also reproduced a Linux **ABA rename away/back** that path/inode snapshots did NOT detect; this remains open.

## A170 policy and behavior

The operation-scoped staged facade now walks each ancestor from `db_path.parent` up to the filesystem root, using `Path.lstat` for that directory component, and `Path.is_junction()` where available (Python 3.12+). Each observed component must be a genuine directory, not a symbolic link or Windows junction. Missing parents are tolerated **only** at first initialization so the existing SQLite staged bootstrap may create them. The newly created chain is checked and pinned immediately after open.

- Reject alias components with `BOUND_DATABASE_ANCESTOR_ALIAS_DENIED`.
- Reject non-directories with `BOUND_DATABASE_ANCESTOR_NOT_DIRECTORY`.
- Reject unavailable ancestors with `BOUND_DATABASE_ANCESTOR_UNAVAILABLE`.
- Latch on parent-chain mismatch before native open, after native open, or after an operation. Existing bound handles reject parent replacement between operations.
- If a discrepancy is found *after* an operation may already have committed, report uncertainty and **never** replay automatically.

This is an additional best-effort path observation guard. The OS descriptor in A168 still belongs to the facade, **not** the SQLite VFS. The checks are not atomic, and a malicious ABA rename that restores the same inode can still evade them. A junction/symlink inserted and removed entirely between observations can also evade detection.

## Tests and acceptance

A169's actual-parent-symlink scenario becomes a **denial regression** on this stacked branch. Six new offline tests cover real alias, simulated Windows junction, non-directory, parent identity drift during SQLite open, parent identity drift following a committed write (readback exactly once), and safe bootstrap of absent nested directories.

Expected dedicated CI matrix: **58 tests per OS** (52 inherited + 6 new); an actual symlink unsupported by OS must be marked **skipped**, not counted as observed rejection. Ubuntu and Windows both required. The historical A169 PR remains an unmodified record of the original vulnerability, while this branch documents a LAB candidate fix.

## Boundaries / release posture

- Parent directory binding cannot prove the SQLite connection's internal file descriptor or eliminate ABA/rollback attacks.
- Symlinks/junctions may be legitimate in some deployments; rejecting them needs product/host-path compatibility review before adoption.
- Attestation of WAL/SHM, host integrity, independently administered custody, receipts for external effects, and all six P0 remain unresolved.
- **HARD NO-GO. ZERO_AUTO_RESEND. 0/6 P0 homologados.** Not production-ready and not evidence of independent custodian trust.
