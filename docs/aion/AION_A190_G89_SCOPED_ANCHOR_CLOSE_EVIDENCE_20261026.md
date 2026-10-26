# AION G89 — SQLite scoped anchor close preserves primary error (LAB)

**Date:** 2026-10-26. **Stack base:** G88 Draft #1579, exact commit `8554225d8e4776c22f83d7fd28279b7d53448055`. **Draft LAB, 0/6 P0 HOMOLOGATED; HARD NO-GO, no merge/deploy/Worker/real provider SEND.**

## Security defect (RED first)

The connection-free `OperationScopedSQLiteChatStore` has an OS descriptor (anchor) opened separately from the native SQLite connection for path/inode observation. In `aion_chat/staged_store.py`, a secondary `OSError` from the anchor's `os.close(anchor)` raised `StorageUnavailableError("BOUND_DATABASE_ANCHOR_CLOSE_FAILED")` **even while an earlier primary error was already propagating**. Thus it masked the actual `LookupError`, `StorageUnavailableError`, `KeyboardInterrupt`, or `SystemExit`, reducing confidence in the operation's uncertain outcome.

G89 first added **seven synthetic tests**, using real temporary SQLite and an actual OS fd opened by the scoped facade, with synthetic before/after `os.close` faults and registered fixture-only fd release. Cases: read close-before, committed write close-after, four distinct primary error identities, and one healthy normal control. No network/provider, no uncontrolled loop, no real money.

**Genuine prepatch RED** on unmodified G88 production code:
- [Run 40323854949](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40323854949), commit `86be6a05728b14396f4aa4c97fe64616d4b80bd1`.
- **Ubuntu:** `Ran 26 tests`, `FAILED (failures=4)`.
- **Windows:** `Ran 26 tests`, `FAILED (failures=4)`.
- Four assertion failures correspond to the four original-error identity tests. The other G89 cases, inherited G88/G84/G85, and two canonical lifecycle regressions were controls, not false-green allowances.

## Minimal code correction

**Corrected source SHA:** `33a5727eea57e2d889e902cc7b4a4cc6c062f91e`.

Only the `os.close(anchor)` finalization in `aion_chat/staged_store.py` changed. It records any already-pending Python exception **before** calling `os.close`. A secondary OSError latches the facade as `BOUND_DATABASE_ANCHOR_CLOSE_FAILED`; if a primary exists, it preserves that original exception (adds a Python exception note where supported) rather than masking it. If no primary exists, it retains the original public `StorageUnavailableError("BOUND_DATABASE_ANCHOR_CLOSE_FAILED")` contract. No implicit rollback, retry, reconnect, re-send or security-guard override.

## Objective GREEN

- [G89 run 40324033243](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40324033243) **SUCCESS on both Ubuntu and Windows**:
  - Ubuntu: `Ran 26 tests in 0.245s`, `OK`.
  - Windows: `Ran 26 tests in 2.699s`, `OK`.
  - All seven named G89 markers are present in both logs; 7 G89 + 6 G88 + 6 G84 + 5 G85 + 2 existing lifecycle = 26.
- [G88 inherited run 40324033347](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40324033347): both OS jobs **SUCCESS**.
- [SQLite staged lifecycle 40324033274](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40324033274): both OS jobs **SUCCESS**.
- [A184 candidate security/Quality/external run 40324033279](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40324033279) on the same corrected source commit:
  - Canonical Quality candidate **6449/6449 PASS**: `Ran 6449 tests in 51.875s`, `OK`, source SHA256 `67897c3b4340771ffb301f8779227f9bf93dfa115e9d1bc7142ec4cbcf33bfc0` (job `121575971118`).
  - Canonical Security unittest candidate **368/368 PASS**, `OK` (job `121575971398`); canonical Security pytest candidate **2825 passed** (job `121575971216`). Both use Security gate SHA256 `927c30233f38f7727d5e15c5a78af3d31176d0ade1614aec0fc17b63fa132485`.
  - Candidate dependency security-audit remains **FAILED**, and external-red **five genuine unmet requirements** on both OS remain **FAILED**. Baseline deliberately RED and not waived.

## Precise non-claims

This anchor is a separately opened, ordinary OS read-only fd. Passing tests do **not** prove it is SQLite's native VFS handle, prevent same-inode rollback, establish monotonic external custody, guarantee physical close of the descriptor if `os.close` raises before release, authenticate original event identity, establish third-party receipt independence or prove first-SEND exactly-once outcomes.

This narrow patch catches **OSError** from anchor close; a BaseException such as a synthetic KI/SystemExit raised by a monkeypatched `os.close` is not separately covered here. It must not be silently called certified. No independent Codex review for this branch: authorized Windows desktop remains offline.

**0/6 P0 HOMOLOGATED · HARD NO-GO · NO MERGE · NO DEPLOY · NO WORKER · NO REAL SEND/FUNDS.**
