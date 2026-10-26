# AION A190 G86 — Bounded CI selectors and canonical Quality on G85 stack

**Date:** 2026-10-26. **Parent:** G85 Draft #1576, base head `5dc6ea638de6dc4fd3aec9d8a20255e60a9d418e`. **Status:** Draft LAB; **0/6 P0 HOMOLOGATED; HARD NO-GO**.

## Inherited RED before correction

1. G71 CI [40315872401](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40315872401): Windows and Ubuntu jobs failed: `test_g[3-7]*.py` discovery selected G74–G76 newly added tests outside the historically bounded G71 scope. Three `ModuleNotFoundError: No module named 'requests'` import errors, 757 tests observed instead of original 699.
2. G73 CI [40315872169](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40315872169): both OS failed for same three out-of-scope imports, while job demanded original 719 tests.
3. A184 canonical candidate Quality [40315872261](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40315872261): `Ran 6449 tests`, `FAILED (failures=1)`; the unchanged convergence guard rightfully denied inherited `.github/workflows/aion-a190-g72-secret-fixture-hygiene-lab.yml`, whose filename includes `secret`. The safe workflow rename had already been validated on Q2 branch, but not applied to this G85 stack.

## Narrow change, no test skips

- Added `scripts/run_a190_numeric_g_suites_lab.py`, a self-enforcing, numeric-generation module loader selecting exactly original G3..G71 or G3..G73 from the **same** `test_g[3-7]*.py` universe. It emits a SHA256 module manifest and explicit included/excluded file list; denies missing ceiling or unexpected changes to the exact accepted test count (699 / 719) instead of silently changing coverage.
- G71 and G73 workflow jobs call that loader, keep all pre-existing stable-denial marker greps, same pinned `cryptography==46.0.3`. Newer G74–G79 suites remain **outside this bounded acceptance contract**; they must be validated by their own workflows, not falsely counted as passed here.
- Carried forward the previously verified G72 workflow **filename-only correction**, and its internal path trigger. Original secret scanner and convergence test remain unchanged.
- Added dedicated G86 cross-check of the exact canonical Quality selector, using pinned canonical dependencies and the pre-existing A183 LAB network guard. No change to production modules, security test expectations, exclusions or provider gates.

## Independent GitHub CI evidence — exact G86 candidate

**Initial G86 PR code head:** `503a24a97fdc94fde659b1f37dbb007a311a212f`. The below runs executed against that candidate, before adding this documentation-only commit.

| Workflow | Ubuntu | Windows | Evidence |
| --- | --- | --- | --- |
| G71, bounded numeric through 71 | **699/699 PASS** | **699/699 PASS** | [40320320365](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40320320365) |
| G73, bounded numeric through 73 | **719/719 PASS** | **719/719 PASS** | [40320320476](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40320320476) |
| G72 synthetic fixture hygiene | **SUCCESS** | **SUCCESS** | [40320320243](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40320320243) |
| Exact canonical Quality | **6,449/6,449 PASS** | Not run | [40320320531](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40320320531) |

Quality log: `CANONICAL_SOURCE .github/workflows/quality-tests.yml sha256 67897c3b4340771ffb301f8779227f9bf93dfa115e9d1bc7142ec4cbcf33bfc0`, `Ran 6449 tests in 73.619s`, `OK`.

G71 manifest: `51 modules`, `7 excluded later`, `sha256 b6b8e762cc94431af5401986e915a70d1758fb6855f39aa96131a29f07ed2265`, `G86_EXPECTED_TESTS=699 ACTUAL=699` on both OS.

G73 manifest: `52 modules`, `6 excluded later`, `sha256 70a1c82976b2a9160a890f9db8cc7fe666c22a7d6a5b45304790277595fffb1e`, `G86_EXPECTED_TESTS=719 ACTUAL=719` on both OS.

## Distinct remaining Security/P0 blockers, NOT fixed here

A184 external-red last checked on G85 [40315872261](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40315872261) still had five genuine unmet external-acceptance tests:
- Independently monotonic custody and checkpoint rollback detection.
- Immutable authenticated original business event identity/enrollment.
- Externally pinned trust authority/identity root.
- Authenticated live restored SQLite snapshot/version and native VFS identity.
- Denial of write authorization after same-inode SQLite rollback.

A184 candidate Security unittest and Security pytest succeeded on that historical run, but supply-chain audit failed on pinned vulnerable dependencies (notably `pypdf` and `pillow`). These are separate from canonical Quality and bounded G71/G73 test gates. No production migration, real external witness enrollment, live H0, authorized first SEND or rollback-proof custody was exercised or certified.

**NO MERGE · NO DEPLOY · NO WORKER · NO PROVIDER SEND · NO REAL FUNDS · 0/6 P0 · HARD NO-GO.**
