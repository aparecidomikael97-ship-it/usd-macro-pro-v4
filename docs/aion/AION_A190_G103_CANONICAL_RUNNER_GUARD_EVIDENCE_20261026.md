# AION G103 — A184 copied canonical runner resolution and fail-closed guard

Date 2026-10-26. Parent G102 Draft #1593 candidate source 2862b9076a95efc225f915e243917fa00bb9e769, 28/28 synthetic enrollment-contract checks passed on both OS. G103 remains Draft LAB. 0/6 P0 homologated; HARD NO-GO.

## Reproduced CI harness problem

A184 run [40341019980](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40341019980) on the G102 code had candidate/base canonical Quality, Security and package-audit jobs fail BEFORE their selectors ran. The workflow copied scripts/run_a183_canonical_lab.py to RUNNER_TEMP, then launched that temporary copy. The copied file imports aion_a190_scoped_socketpair_guard, a sibling module still inside the checked-out repository scripts directory. This resulted in ModuleNotFoundError in both candidate and base jobs, unrelated to Quality source regressions or external acceptance. The real five A184 external RED still executed and failed.

## Narrow correction (no tests or security selectors changed)

The G103 source edit to scripts/run_a183_canonical_lab.py determines the sibling LAB socket-guard module from the script's actual directory (direct invocation), or from the checked-out repository scripts directory (isolated temporary copy used by A184). If neither exists, it raises A183_LAB_SOCKET_GUARD_MISSING_DENIED before tests; it does not silently run without the guard or load a third-party fallback.

Original test selector commands remain unchanged, as does the G100 scoped Windows asyncio self-pipe exception with external Python socket-connect denial. The G103-specific workflow copies the runner to RUNNER_TEMP and checks original 368 Security unittest selector in Windows and Ubuntu. It also launches the temporary runner from an empty unrelated worktree, requiring a denial if no guard module is available. The initial G103 CI had a Windows-only log-grep problem: expected Unix path slash though the Windows log uses backslash. The canonical Windows tests had already passed 368/368. G103 then corrected only that log assertion in workflow; no additional runtime change.

## Objective final CI

Corrected source SHA 68360743d23239ba1cd4f91ecf0d02c3ee781e5b.

[G103 focused run 40342547001](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40342547001):
- Windows Security unittest from the copied runner: 368/368 PASS.
- Ubuntu Security unittest from the copied runner: 368/368 PASS.
- Both OS negative detached-worktree checks correctly raised A183_LAB_SOCKET_GUARD_MISSING_DENIED.
- Both jobs SUCCESS; no runtime source, test selector or socket-denial relaxation.

[A184 full evidence run 40342547221](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40342547221) on the same corrected G103 source:
- Candidate original Quality on Ubuntu: 6449/6449 PASS, Ran 6449 tests in 88.176s, OK.
- Candidate original Security unittest Ubuntu: 368/368 PASS, OK.
- Candidate original Security pytest Ubuntu: 2825/2825 PASS.
- Candidate canonical dependency audit: No known vulnerabilities found, existing Bandit selector successful.
- Genuine external-red: five explicit tests FAIL on BOTH Ubuntu and Windows. These are not hidden by CI filtering or transformed to expected failures.

## External GO/NO-GO remains unchanged

A184 unmet tests require (1) a real independently monotonic custodian/checkpoint, (2) immutable externally authenticated original business enrollment, (3) externally pinned trust authority/root, (4) signed live SQLite snapshot/version tied to native VFS file identity and (5) write refusal after same-inode rollback. G102 is a synthetic admission contract, not an independent physical attestor. G103 corrects only the evidence runner. Neither authorizes live first-send, real funds, Worker, merge or deploy.

NO MERGE / NO DEPLOY / NO WORKER / NO REAL PROVIDER SEND / NO FUNDS. Six P0 = 0/6 HOMOLOGATED, HARD NO-GO.
