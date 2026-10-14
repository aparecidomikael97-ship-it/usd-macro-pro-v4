# AION A.56 — contained direct HUMAN_CLICK lab route, NOT physical owner proof

Issue #1274. This patch is layered on Draft A.55 #1273 at exact source SHA `9062443f498f49684498c2d1953861d8be40a7b2`.

## Bug / reproduction
- An importable `_execute_due_local_work_authorized` accepted `authorization_mode=HUMAN_CLICK` plus any nonempty caller-supplied digest, then reached the local Core handler and staged a `SUCCEEDED` action receipt.
- Test-only RED commit `308b6eed719db7a58c9897294783341f5e8a92b5`, workflow run 38497514236: four new tests plus existing executor regressions; 2 new adversarial FAIL, public confirmation controls PASS; no real network/provider calls.
- The observed vulnerability is misattributing an **unrouted internal invocation** to a human route. It is not a demonstration of a successful real external Worker or remote effect.

## Minimal change
- Add a **non-secret, in-process route sentinel** as an optional keyword-only parameter to the internal kernel. A forged direct `HUMAN_CLICK` call without the sentinel is BLOCKED before reading schedules, calling handler or issuing a receipt; no checkpoint modification or provider call.
- Pass the sentinel only in `execute_due_local_work(...confirmation=True)`. Keep public manual read/draft behavior and A51 autonomous mode hard-stops identical.
- Add tests for forged direct digest, forged principal/local witness, absence of manual confirmation, and control legitimate public manual read. Socket connections denied in the CI test runner.

## Important remaining OPEN P0
- This sentinel is **not** a credential, a signature, a source of independent authority, a trusted OS UI event, FIDO/TPM presence, or antirollback. Any in-process code able to import module internals could obtain it; any caller can still invoke the public `execute_due_local_work(...confirmation=True)` with a self-asserted bool. Thus **HUMAN_OWNER authenticity is NOT solved**. Production still requires an external owner/tenant/scope-bound authorization event and one-time verifiable consent at the UI/trusted host boundary. No claim of a physical human-click gate.
- Historical Quality/Security suites already red, witness & causal producer receipts missing, A12/A16 original ZIPs unavailable. 0/6 P0 homologated, first install 20/20 HARD NO-GO.
- No main merge, deploy, Worker enable, Render, TPM, owner enrollment, external effect or spending.

## CI status
Test-only RED was observed. GREEN results must be read from exact post-patch source HEAD; absent actual CI, do not claim passing tests.
