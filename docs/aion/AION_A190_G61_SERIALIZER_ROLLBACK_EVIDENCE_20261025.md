# AtlasQuant / AION A190 — G61 error classification and historical rollback failure

**Data:** 2026-10-25. **Branch:** `lab/aion-a190-g61-json-error-classification-rollback-20261025`. **Draft PR:** [#1547](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/pull/1547), stacked on Draft G60 #1546, NOT main.

## Narrow objective

G60 added `allow_nan=False` to numeric serialization, but its `enqueue` caught **all** `ValueError` during `_digest(safe_payload)` and translated them into `G60_NONFINITE_PAYLOAD_DENY`. A user-supplied non-standard object with `__str__` raising a different ValueError (via existing `json.dumps(default=str)`) lost its actual diagnostic. G61 retains fail-closed behavior but reports the **correct original exception**. Separately, it verifies G60's historic JSON exponent-overflow denial while SQLite rollback itself fails, preserving the primary error and quarantining the store.

These are **isolated local synthetic SQLite** checks, not receipt authority, operational recoverability or real supplier execution.

## Real Codex review before patch

Installed Windows Codex CLI v0.164.0-alpha.11.1, `-s read-only --ephemeral`, session `01a17447-dc8a-7e11-9644-fb16aa8100f4`, inspected actual G60 source, G31 rollback proxy and G60 suite. It confirmed the blanket ValueError misclassification and recommended recursive finite-only validation before digest instead of translating any exception. It also confirmed static composition of G60 parse overflow and G31 rollback quarantine. **Codex did not execute tests, edit files or contact providers/network.**

## Falsifiable actual RED before correction

`labs/a190/test_g61_serializer_rollback_faults_lab.py` was versioned **before runtime patch** at SHA `48f3c7529f55497b4e76ab3a9a3af5ff66a03337`, isolated Windows disposable SQLite:
- **9 tests executed; 7 PASS / 2 FAIL**, specifically tests 01–02 whose expected original serializer ValueError was instead mislabeled `G60_NONFINITE_PAYLOAD_DENY`.
- True NaN and nested Inf cases already rejected. G60 historical `1e999` rejection composed correctly with both healthy and **failed** rollback using G31 `FaultDB`: original `G58_HISTORICAL_JSON_UNTRUSTED_DENY` persisted, failed rollback was chained as secondary OSError, store handles detached, health failed, fresh enqueue refused with StorageUnavailableError, new disk reopen contained only original synthetic row/lock. There is NO provider or automatic retry.

## Narrow runtime fix and GREEN

At SHA `757f90bf704bf66dfd8c92107cc68b37ecfd63ee`:
- `_assert_finite_payload_lab` traverses already-redacted mappings (keys and values), lists and tuples and raises **only** for nonfinite float, with `G60_NONFINITE_PAYLOAD_DENY`.
- `enqueue` invokes this checker BEFORE BEGIN, then executes `_digest(safe_payload)` without blanket `except ValueError`. Custom serializer failures retain their original class/message. G60 `_canonical(...allow_nan=False)` remains a backstop and strict historical `parse_float` remains unchanged.
- No application changes to `_rollback_preserving_original`, COMMIT/BEGIN, provider or execution logic.

**G61 9/9 GREEN** after patch. G60 11/11, G59 12/12, G56 8/8, G31 18/18 also GREEN in direct critical regressions.

## Complete run provenance and CI

New `.github/workflows/aion-a190-g61-serializer-rollback-lab.yml` committed at exact code+CI SHA **`5fe5ee537df41cb073607e5414b5a3cc092522b5`**, two OS matrix.
- Isolated Windows worktree `C:\Users\apare\AtlasQuant-G61-Fault-LAB-20261025`: **G30–G61 549/549 PASS**, exit 0, git worktree clean on SHA `5fe5ee537df41cb073607e5414b5a3cc092522b5` (G51 combined inside G50).
- **GitHub Actions MULTI-OS VERIFIED:** [#40220903209](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40220903209) at exact source+workflow SHA **`5fe5ee537df41cb073607e5414b5a3cc092522b5`**: Ubuntu job `121252053802` **SUCCESS 549/549**, Windows job `121252053553` **SUCCESS 549/549**. Both raw logs inspected; five G61 markers confirmed each, totals **1,098 executions of 549 distinct synthetic tests**. The report commits followed this code-tested SHA.
- Documentation-only commits after tested SHA are NOT substituted for runtime test provenance.

## Independent Codex postpatch audit — confirmed versus unproven

A SECOND real Codex CLI session `01a1744c-f4c6-76a1-babc-2e6c022696c8`, read-only/ephemeral, inspected diff `589a137` (G60 documentation tip) to `5fe5ee5` (G61 code+workflow) and related tests. **No file changes, tests or network actions were performed by Codex.**

**Confirmed by static inspection, unresolved in G61:**
- A cyclic list↔tuple can reach `_assert_finite_payload_lab` after shallow `redact` leaves tuples untraversed. Without cycle detection, this can surface `RecursionError` before BEGIN rather than a specific cyclic JSON refusal. A synthetic negative test is still needed.
- `aion_chat.privacy.redact` recursively handles lists and dicts but **not tuples**. Payload data nested in a tuple can bypass expected redaction. The G61 infinite-float tuple test does not prove sensitive data redaction. Require a separate privacy contract + RED/GREEN in G62.
- Rollback fault G61 covers historical parse overflow *before* new reservations are written, not an exception thrown after the new semantic reservation but before transaction COMMIT. Add post-reservation serialization-fault injection test; do not infer broad crash safety.
- A volatile custom object's string conversion can vary across digest and stored data; this is a hypothesis pending tests, not a verified exploit. No cross-host antirollback/trust is established.

The test labeled foreign tenant in G61 test 08 only covers ordinary foreign tenant staging; it does **not** deliberately poison other-tenant history. Earlier G60 foreign tenant negative controls do cover overflow locality.

## Explicit open issues

- Recursion/cyclic container input remains a separate JSON/redaction issue; no universal arbitrary-object validation or external identity proof is claimed. Existing `default=str` stringifies unsupported values.
- Rollback fault handling is validated only under test-injected SQLite proxy; no power-loss test, trusted monotonic external checkpoint, no issuer-signed provider receipt and no independent exactly-once SEND witness.
- All 6 critical P0 remain unhomologated; historical full Security/Quality and compatibility native SQLite gates remain separately blocked.

**0/6 P0 HOMOLOGATED · HARD NO-GO · UNCERTAIN · ZERO_AUTO_RESEND. No merge, deploy, real SEND, Worker, customer data, credential, fund or paid resource.**
