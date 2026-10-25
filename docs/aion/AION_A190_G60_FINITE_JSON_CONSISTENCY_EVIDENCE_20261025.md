# AtlasQuant / AION A190 — G60 finite JSON admission and history consistency

**Data:** 2026-10-25. **Branch:** `lab/aion-a190-g60-finite-json-admission-20261025`; **PR Draft:** [#1546](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/pull/1546), stacked on G59 #1545, not on main.

## Why G60 was necessary

G59 validated deterministic historical identity and duplicate-key JSON, but its `_canonical` used Python `json.dumps` with default `allow_nan=True`. A synthetic staging payload containing float `NaN`, `Infinity`, `-Infinity` (including nested arrays) was accepted, serialized and hashed even though strict G58 historical reading rejected literal `NaN`/Infinity. That discrepancy can make a previously admitted tenant history block future legitimate semantic event staging. Separately, historical `json.loads(parse_constant=...)` did **not** reject valid JSON numeric exponent overflow like `1e999` in an unbound auxiliary field; Python turned it into `inf`.

This is a **local format and safety-consistency issue**, not evidence of a real provider effect or a certified financial operation.

## Real read-only Codex review, independent of tests

Windows Codex CLI v0.164.0-alpha.11.1, read-only and ephemeral, session `01a17434-4fca-7580-b193-a56f9719dacd`, inspected `_canonical`, `enqueue`, `redact` and the G58/G59 historical parser, and the relevant historic tests. It confirmed the two causes and recommended `json.dumps(allow_nan=False)`, plus `parse_float` guarded by `math.isfinite`. It **did not modify files, run tests, contact providers or access network/GitHub**. Other risks include `default=str` stringification of unusual objects and fields removed by redaction; NOT resolved here.

## Falsifiable RED committed before patch

File `labs/a190/test_g60_finite_json_contract_lab.py` committed first at SHA **`8f2870b423b3524751f4a6884e3da14a0fba90da`**. Against unchanged G59 source, executed in a Windows isolated disposable SQLite worktree:
- **11 tests, 5 PASS / 6 FAIL**; four cases accepted nonfinite floating-point values into new payload staging and two accepted historic exponent overflow in JSON.
- Negative controls passed: valid finite floats still stage, string literals `"NaN"` remain ordinary strings, historic literal NaN already rejected, unrelated foreign tenant corrupted history not read.
- All comparisons used a different second semantic event for historical overflow so that G58's existing same-event guard could not mask an actual parser gap.

## Minimal code patch, not production promotion

At source SHA **`da02e00ea2b260283c1c7e0537ebc013743b7a97`**:
1. `_canonical` now uses `allow_nan=False`, preserving UTF-8, sort, compact separators and existing `default=str`. `enqueue` turns attempted nonfinite payload digest serialization into explicit `ValueError(G60_NONFINITE_PAYLOAD_DENY)`, **before BEGIN**, so there is no partial outbox/decision/semantic reservation.
2. G58/G59 historic decision JSON parsing uses `parse_float` to accept ordinary finite floats and reject float overflow with `math.isfinite`. Existing `parse_constant` and strict duplicate-key hooks remain. Rejection propagates as `G58_HISTORICAL_JSON_UNTRUSTED_DENY`, with transaction rollback and no backfill/repair.
3. No real SEND/RETRY path changed or enabled.

The same G60 suite **11/11 GREEN** postpatch. Critical inherited G59 12, G58 16, G57 10 and G39 28 all GREEN.

## Local full regression and CI provenance

- Two-OS CI workflow `.github/workflows/aion-a190-g60-finite-json-lab.yml` added at exact commit SHA **`e9413aa0a9f79778282eaf15c3a12ef44ee051c2`**.
- Windows isolated worktree `C:\Users\apare\AtlasQuant-G60-Finite-LAB-20261025`, at same SHA: G30–G60 (G51 combined in G50), **540/540 GREEN**, exit code 0, git status clean.
- **GitHub Actions G60 verified:** [run #40219164861](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40219164861), exact tested source/workflow SHA **`e9413aa0a9f79778282eaf15c3a12ef44ee051c2`**. Ubuntu job `121246770554` **SUCCESS 540/540**; Windows job `121246770076` **SUCCESS 540/540**. Read the logs and verified all eight G60 protection markers on both systems. Total **1,080 executions of 540 distinct focused synthetic cases**. The evidence report is a subsequent documentation-only commit, not the tested source SHA.

## Codex independent post-patch review and next tests

A **second** installed Codex CLI read-only/ephemeral session `01a17439-cc33-7033-b1bc-31caf1bcbf0d` reviewed the actual patch on clean `e9413aa0a9f79778282eaf15c3a12ef44ee051c2`, **without editing or executing tests**. It did not identify obvious regressions in finite floats, normal strings or existing BEGIN/COMMIT/rollback-quarantine boundaries. Two **OPEN** edge cases remain:
1. `enqueue` labels *any* `ValueError` during `_digest(safe_payload)` as `G60_NONFINITE_PAYLOAD_DENY`. Because `_canonical(default=str)` supports arbitrary objects, a custom `__str__` that raises ValueError could be misclassified. Explicit classification/admission test is needed.
2. The historical overflow tests verify fail-closed under a *healthy* rollback; they do not inject rollback failure into this exact G60 path. Need future G61 LAB with primary exception preserved, store quarantined/detached, ledger/reservations intact and no auto retry. Neither gap closes P0 or H0.

## Unproven critical requirements

- The historical parser is fail-closed. Previously admitted nonstandard JSON that contains NaN/Infinity (or exponent overflow) can block later semantic staging until a separately audited migration/decision is made. G60 does not rewrite or certify old files.
- Non-standard objects stringified by `default=str`, values removed by redaction, and full hostile-host rewrite of source+hash+historical receipts require separate scrutiny.
- Identifiers declared by a caller can still differ for the same real obligation; no authenticated provider-issued event/receipt, trusted HUMAN_OWNER, independent monotonic custody, power-loss H0, cross-request true exactly-once execution or canonical full Security/Quality certification.
- These tests are synthetic disposable SQLite, not a demonstration of external effects or resilience to physical rollback.

**0/6 P0 HOMOLOGATED · HARD NO-GO · UNCERTAIN · ZERO_AUTO_RESEND. No merge/deploy/Worker/provider SEND/customer data/financial effect/secrets/cost.**
