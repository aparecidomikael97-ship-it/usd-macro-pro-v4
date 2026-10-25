# AtlasQuant / AION — G47–G50 Codex security hardening audit trail

Date: 2026-10-24 (MT local; GitHub commits may show 2026-10-25 UTC).

## Scope, trust boundaries and branch chain

This is evidence for **four STACKED DRAFT LAB** PRs, not main and not homologation:
1. G47 [PR #1534](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/pull/1534): required reauthentication and reference bound into deterministic Outbox key.
2. G48 [PR #1535](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/pull/1535), stacked on G47: refuse corrupted same-key `IDEMPOTENT` reuse and malformed reauthorization even without optional G44 strict mode.
3. G49 [PR #1536](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/pull/1536), stacked on G48: refuse adapter `send` getter that reenters and changes local phase/owner/lease/attempts before call. Existing G41 strict fence error precedence restored at `0144bd82c6f62f3eeb7fd992f69401d8e9713418`.
4. G50 [PR #1538](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/pull/1538), stacked on G49: refuse post-send local overwrite after an in-process synthetic callback confirms the attempt and then returns/raises.

**No merge to main, deploy, Worker, provider API, customer record, real financial operation, production key, external authenticating issuer, paid service or automatic resend.**

## Genuine Codex involvement and falsifiable RED/GREEN

Codex CLI v0.163.0-alpha.11.2, model gpt-6.1-sol, on authorized Windows `am12` with `-s read-only --ephemeral`:
- Session `01a17079-91f7-7123-bbe5-25aea92439b9` inspected actual G47 and identified poisoned idempotent reuse, nonboolean reauthorization acceptance, and possible adapter getter callback reentry. It did NOT edit, send, or run tests.
- Session `01a17081-0bbb-7e11-a54c-484a039b342d` independently reviewed actual G49; confirmed getter-state rejection logic and identified distinct post-send callback overwrite if optional G41 fencing is disabled. It noticed a G41 historical error-code mismatch; corrected in G49 before advancing. It did NOT edit, send, or run tests.

RED was reproduced **before** each respective patch with the following test files committed prior to fix:
- G47 `labs/a190/test_g47_reauth_integrity_lab.py`, 3 passed / 9 failed initially at `ba3b0cfdbca241ffcc3c39410654c77ea10deed2`; expanded to 18/18 passing Windows after fix.
- G48 `labs/a190/test_g48_idempotent_reauth_admission_lab.py`, 3 passed / 8 failed at `f16fb99aa4c0f31889a1ab3017494f81b44485f2`; 11/11 after fix.
- G49 `labs/a190/test_g49_getter_reentry_fence_lab.py`, 2 passed / 5 failed at `1817f7ff284917efacb393525b58b0a6de343486`; 7/7 after fix.
- G50 `labs/a190/test_g50_send_callback_immutability_lab.py`, 2 passed / 2 failed at `736bfa398a9dd5579268d15645e6085d933a34c6`; 4/4 after fix at `756e521bf525c319eec015f80de10d9236e9da32`.

All synthetic adapter effects were in-process only, and SQLite files were disposable. Local G50 expanded Windows run passed **233/233**, comprising G50 (4), G49 (7), G48 (11), G47 (18), G46 (10), G45 (7), G44 (39), G43 (32), G42 (28), G41 (18), G40 (36), G30 (23). The checkout was clean at the last tested code revision.

## Verified GitHub Actions runs (exact tested SHA matters)

- [G47 #40147199202](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40147199202): Windows/Ubuntu both SUCCESS, 106 focused distinct tests per OS = 212 executions, exact tested commit `bb78e787bf6f3ed3da482c77b95189242c0dc557`.
- [G48 #40147380501](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40147380501): Windows/Ubuntu both SUCCESS, 117 distinct tests per OS = 234 executions, exact tested commit `a5c0c94edac8aab37b1bc5e20e1908613f1412ea`.
- [G49 inherited run #40148020433](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40148020433): Windows/Ubuntu both SUCCESS, 160 focused tests per OS = 320 executions, on G50 tested code/workflow commit `83b027d83ac2e44b7830a9ec3d0407c538ebbc78`.
- [G50 #40148020447](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40148020447): Ubuntu job `121033438346` and Windows job `121033438578` **both SUCCESS**, 233 focused tests per OS = **466 executions**, exact code+workflow commit `83b027d83ac2e44b7830a9ec3d0407c538ebbc78`. This evidence-only document is a LATER commit and is NOT the tested SHA.

**Do not add execution counts across stacked runs and call them unique tests.** G47–G50 totals include inherited overlap.

## Still RED / not proven

The fixes establish LOCAL contract checking only; no independent physical owner authenticator, actual provider receipt signature, independent host-proof monotonic store, rollback resistance, atomic first-send authority, externally verified no-double-execution, or physically realistic power-loss recovery has been proven. An adversarial second connection can act after a local `get` but before SQL UPDATE; **residual TOCTOU remains** until independent fencing/atomic CAS and an external authority contract are validated. Post-send fake evidence-verifier reentry, original remote provider uncertainty, WAL/SHM tampering and ambiguous historical migrations need separate targeted gates. Local hashes and synthetic signatures are not external authenticity.

Previous A184 canonical Security/dependency audit was RED, including known advisories in `pypdf` and `Pillow`; none of these path-focused G47–G50 green runs constitutes a fresh full Security/audit PASS.

**0/6 P0 HOMOLOGATED. HARD NO-GO. UNCERTAIN. ZERO_AUTO_RESEND.**
