# AION V16-A.48 — direct Global Worker CAS writer fail-closed without an independent source witness

**Parent:** A.47 Draft #1260 at exact SHA `ead5b9e8d05f15903725269e147bd19352eec599`; isolated child Draft. Main/Core V1/AM12 and external services unchanged.

## Real bypass around A47 application-layer check

A.47 blocks the normal `run_global_worker_once` path before the first lease CAS, yet `_persist_runtime_checkpoint_cas` was still a separately callable Python function in `atlasquant_aion_global_worker.py`. Its docstring described it as "used only by an already-authorized global tick", but **did not enforce** that precondition. A direct invocation using a locally valid checkpoint, GitHub runtime repo/branch/path/token config and a nonempty expected SHA reached the actual `requests.put` site without independent source ownership, monotonic latest-head antirollback witness, or HUMAN_OWNER trust enrollment. Passing a fabricated `independent_witness.status=VERIFIED` marker in the same checkpoint did not change the risk. An arbitrary config object's `branch` property could run before any trust check.

This is a **real reachability flaw** demonstrated with mocked HTTP, not a claim of a real external write or an exploited production incident.

## Evidence-first RED

The first A48 commit `1cd93540fc346cbd61dbed52379daeea408e83f6` added **three actual direct-call Worker regression tests** to `test_atlasquant_aion_global_worker.py` and a mandatory named step to the security workflow; it made no runtime change. [Security Gate run 38468149820](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/38468149820) recorded **3/3 intentional RED**:
1. Direct writer reached the `requests.put` mock given locally valid checkpoint and local SHA.
2. Direct writer reached the `requests.put` mock with an entirely fabricated local witness marker.
3. Direct writer evaluated a hostile `config.branch` property before authorization and raised the test sentinel.

Both `requests.put` and any readback were patched in these tests; **zero real GitHub writes or external network calls** were made.

## In-place fail-closed fix

`_persist_runtime_checkpoint_cas` now returns `BLOCKED/INDEPENDENT_SOURCE_WITNESS_NOT_ENROLLED` **as its first operation**. It reports `saved=false`, `verified=false`, `write_accepted=false`, `write_outcome=NOT_ATTEMPTED`, `reconciliation_required=false`, `automatic_retry_allowed=false`, external witness/source/owner verified flags all false, `network_called=false`, `external_action_executed=false`. It does not access config/checkpoint properties, compute a new digest, generate a write receipt, contact GitHub, or invoke a producer. This prevents direct imports/callers of the helper from bypassing the A47 productive Worker entrypoint restriction.

The former positive CAS implementation remains physically below the hard stop, **unreachable**. A future re-enablement requires a separate, real owner-approved external witness/source-binding admission and security review; there is no env flag, mock signer, fake provider receipt or local test bypass.

## Honest historical test handling

The three new denial methods are pinned in an independently mandatory Security Gate step; the root Quality suite already runs the original Worker test module (and a safety-bridge inheritance may duplicate these tests). Original positive tests expecting GitHub mock `PUT`, post-CAS readback, simulated positive Worker execution/receipt remain unchanged and may now fail. **Keep every historical result visible**; do not convert old tests to PASS/xfail/skip or emulate positive production sends. The existing 23 Outbox + 8 Saga Quality errors remain historical, and 17 former positive Worker contract fails from A47 remain until an isolated inert pure simulation facility or real external trust root has been independently reviewed.

## P0 status

This patch does not enroll an independent issuer, prove source/repo/path/tenant/owner membership, provide monotonic latest-head and antirollback witness, authenticate HUMAN_OWNER/Windows, show producer causal COMMITTED_EFFECT or terminal NO_EFFECT_FENCED, recover the original A12 37 + A16 8 ZIP tests, or authorize any production operations. **0/6 P0 homologated; 20/20 first-install gates HARD NO-GO.** No merge, deploy, Worker/Render, keys/accounts/TPM, Windows AM12 operation, credential, spending, or external effects.
