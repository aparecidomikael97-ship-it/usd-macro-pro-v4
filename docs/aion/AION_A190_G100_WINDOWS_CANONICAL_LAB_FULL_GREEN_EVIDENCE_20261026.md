# AION G100 — Windows asyncio self-pipe and unchanged canonical Quality/Security (LAB)

Date: 2026-10-26. Parent G99 Draft #1590 exact tested source 749fa5a21831cb231930f1ce63b50dc2342660e9. Original G98 Draft #1589 has 175/175 Windows B2B PASS and 0 Windows SQLite errors in canonical Quality, but 15 remaining Quality assertion failures. Six P0 still 0/6 homologated; HARD NO-GO.

## Observed root of 14 inherited Windows Quality failures

G98 Windows Quality [run 40330695734](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40330695734): 6,449 cases; **15 FAIL, 0 ERROR**. Fourteen UI/admin/runtime failures shared the same stack: Streamlit AppTest initializes Windows asyncio ProactorEventLoop, which uses a local socket.socketpair() self-pipe. On Windows 3.12 stdlib's fallback creates a synchronous TCP loopback connection to 127.0.0.1 as part of socketpair. Original A183 harness monkeypatched all socket.socket.connect to raise AssertionError("LAB network forbidden"), so the internal event loop failed before any UI test application actually ran. Unix native socketpair does not require this fallback. The fifteenth G98 failure was the unrelated exact-60-minute scanner boundary; G99 fixed it via strict age < 60.0 and deterministic test: [G99 12/12 on both OS 40336582530](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40336582530).

## Narrow LAB-only implementation (tested source 7d0efc5067dfec81d58bb109580ee966ecd5b225)

- Added scripts/aion_a190_scoped_socketpair_guard.py, a Python test harness context manager.
- Modified only scripts/run_a183_canonical_lab.py to run unchanged canonical Quality/Security selectors within that context rather than a blanket socket mock.
- On Windows the guard retains an explicit denial for any remote address, arbitrary loopback, socket.connect_ex and socket.create_connection. Only the same-thread/same-ContextVar synchronous IPv4 127.0.0.1 connect made within the **actual stdlib socketpair function** is allowed for asyncio's internal self-pipe. All other Python socket connects still raise LAB network forbidden.
- On Ubuntu the original all-connects-denied semantics remain unchanged. The Python test harness is not an OS-level firewall: subprocesses do not inherit its mock. No production code or normal runtime network/security policy changed.
- Five synthetic regression cases prove external IPv4 denial, arbitrary loopback denial, connect_ex and create_connection denial, actual local socketpair roundtrip and asyncio event loop lifecycle. No user data, provider integration, keys or financial actions.

## Objective GitHub Actions evidence

[G100 run 40337504265](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40337504265), all three jobs SUCCESS on exact source 7d0efc5067dfec81d58bb109580ee966ecd5b225:

- Focused contract: Ubuntu **5/5 PASS** (job 121622918570), Windows **5/5 PASS** (job 121622918927). All five denial/internal socketpair markers present in both.
- Windows original canonical Quality: **6,449/6,449 PASS**, Ran 6449 tests in 170.358s, OK (job 121622919497).
- Windows original canonical Security unittest: **368/368 PASS**, Ran 368 tests in 5.651s, OK (same job).
- Windows original canonical Security pytest: **2,824 PASS, 1 SKIPPED** in 54.22s; no pytest failures (same job). The Windows skip was also present in historical G93 before G90/G100 (1 failed, 2823 passed, 1 skipped). **Do not call this 2,825/2,825 passed**, or mark the existing skip as passed.
- Exact original selectors are derived from existing .github/workflows/quality-tests.yml and .github/workflows/aion-core-security-gate.yml. Windows checkout SHA256 is affected by CRLF normalization and not compared against the Ubuntu byte SHA; selectors were not edited.

Full Windows canonical Quality trend using the exact 6,449 test selector (no waiver):

| Milestone | Windows errors | Windows failures |
| --- | ---: | ---: |
| G91 original G90 dependency stack | 109 | 15 |
| G95 after G94 native durable close | 68 | 15 |
| G97 after G96 nonce native close | 1 | 15 |
| G98 test-owned close | 0 | 15 |
| G100 after G99 conservative scanner and scoped Windows asyncio LAB fixture | **0** | **0** |

## Limitations / release gates

This validates the current Python LAB test harness and the selected unchanged Quality/Security tests, not all possible sockets, external egress via subprocess or deployment/runtime. G90's known-vulnerabilities audit became zero on the pinned dependency set in both Windows and Ubuntu, but new vulnerabilities may appear.

Still NO independent root of trust, immutable externally authenticated original business intent, independent monotonic witness/checkpoint, actual SQLite native VFS fd/inode attestation, rollback-proof native write admission or real first provider SEND reconciliation. Five genuine A184 external-red requirements persist. Six P0 = 0/6 HOMOLOGATED; HARD NO-GO.

**NO MERGE · NO DEPLOY · NO WORKER · NO REAL SEND · NO FUNDS.**
