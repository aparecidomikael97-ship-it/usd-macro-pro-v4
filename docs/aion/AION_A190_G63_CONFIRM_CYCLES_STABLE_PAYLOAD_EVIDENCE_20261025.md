# AtlasQuant / AION A190 — G63 cyclic confirmation and serialized payload consistency

**Data:** 2026-10-25. **Branch LAB:** `lab/aion-a190-g63-confirm-cycle-stable-payload-20261025`; **PR Draft #1549** [link](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/pull/1549), stacked on G62 Draft #1548, not main.

## Technical scope

The G62 preflight used an active-ancestor cycle check only in `ExecutionOutbox.enqueue`. The synthetic direct `_confirm` path still ran `redact(dict(result or {}))` with NO cycle check before BEGIN. A cyclic result raised `RecursionError` or, when nested under a secret field, could be discarded without a stable explicit rejection.

Enqueue had a second local integrity gap: arbitrary custom Python objects can be converted with `json.dumps(default=str)` twice, first to derive `payload_digest` and then to persist the full decision after a semantic reservation INSERT. Different values across serializations permitted digest mismatch or a fake sensitive token in persisted decision JSON. This is an internal synthetic-data integrity/privacy issue, **not** evidence of external provider execution.

## RED first, before any runtime edits

The suite `labs/a190/test_g63_confirm_cycle_volatile_payload_lab.py` was created on its own branch at SHA **`67f04fad3fa756fe45dec1cec2ab330bcc9ea353`** before any motor patch, then executed against G62 source in a clean disposable Windows SQLite worktree.
- **10 tests, 4 PASS / 4 FAIL / 2 ERROR**.
- ERROR 01–02: cyclic confirmation dict and tuple/list raised uncontrolled RecursionError rather than a stable denial; FAIL 03: a cyclic value under password avoided the requested cycle refusal.
- FAIL 06–08: two serialization passes over a changing `__str__` allowed payload/digest mismatch, raw fake-token or Bearer pattern to appear in the decision persisted to local SQLite.
- Controls 04, 05, 09 and 10 (legitimate result with tuple redaction, shared acyclic containers, stable custom-string replay and tenant semantic collision) already passed.

## Narrow G63 code correction

At motor patch SHA **`7f76a33a307f0dfd0fb5bea56f94e4ca30064037`**:
1. `_confirm` extracts a local result mapping and calls `_assert_acyclic_payload_lab` **before** the first `redact` and before `BEGIN`. Only `G62_CYCLIC_PAYLOAD_DENY` becomes `ValueError(G63_CYCLIC_RESULT_DENY)`; unrelated serialization exceptions retain their original class/message. There is no write or synthetic ledger confirmation for cyclic result data.
2. In `enqueue`, after `encoded = _canonical(decision)` **and before** `INSERT INTO action_decisions`, the actual encoded JSON is parsed and its `payload` checked for redaction idempotence and exact `_digest(payload)` equality with the earlier payload digest/semantic reservation. Mismatch denies with `G63_STAGED_PAYLOAD_PRIVACY_DENY` or `G63_STAGED_PAYLOAD_DRIFT_DENY`; no migration/rewrite, no provider calls.
3. Existing G31/G62 `_rollback_preserving_original` handles any exception after the uncommitted semantic reservation. The G63 correction does not loosen hard no-retry or introduce an additional confirmation/sending path.

The initial G63 suite became **10/10 GREEN**; direct G62 10, G61 9 and G55 11 also GREEN.

## Adversarial expansion and full focused regression

Additional tests were versioned before the final code+workflow snapshot at `073ce19ece6204205e056b33d37721afd3b9b29f` and isolated path fixture fix `ed3b667bc6729a16bcfec1d9ef03b071e1f1cfcc`. New cases:
- Stable custom string emits a fake token on both calls. Even though the digest matches, the redaction-idempotence check denies staging, no persisted fake secret.
- Drift denial followed by fault-injected **FAILED rollback** preserves the primary G63 RuntimeError, chains secondary OSError, detaches/quarantines handles, denies new requests and leaves no committed decision/outbox/reservation/effect after explicit fresh SQLite reopen.
- Direct `_confirm` result containing a self-referential list is denied with the same cycle marker and no new ledger writes.

**G63 13/13 GREEN.**

At exact source+two-OS workflow commit SHA **`4d118bc38fc0a71f36da016287b178563a55a12a`**, Windows isolated worktree `C:\Users\apare\AtlasQuant-G63-Stability-LAB-20261025` ran all focused G30–G63 tests (G51 consolidated in G50), yielding **572/572 PASS, exit code 0, checkout clean**. No canonical full Quality/Security claim.

[GitHub Actions G63 matrix #40222767593](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40222767593) was QUEUED at the evidence's initial creation. Its Ubuntu and Windows job logs and actual test totals must be inspected before claiming cross-OS success. The evidence report is a **documentation-only** commit after the runtime-tested SHA.

## Independent Codex review

Windows Codex CLI 0.164.0-alpha.11.1, `-s read-only --ephemeral`, session `01a1745c-94cc-7213-9ff5-986eae3891a8`, read actual G62 source before G63 changes. It independently located both failure paths, recommended checking cycles before result redaction and the **actual encoded decision payload** before SQL insertion; it neither modified files nor ran tests. A separate postpatch read-only Codex review was requested, session `01a17462-0904-74c1-9449-5727b86ac6b1`; do not claim its final findings until output is received.

## Strict operational boundaries

- Local `_canonical` / SHA-256 consistency is not an independently anchored receipt or tamper-resistant custodian. A hostile process that can rewrite all SQLite records and hashes or IDs on the same host is not defeated.
- Sensitive patterns recognized by the current redactor are not universal DLP. Custom Python objects may have arbitrary `__str__` side effects; raw metadata keys, custom Mapping types and extremely deep structures require separate tests and privacy policy.
- No trusted origin of business event identifiers; different declared IDs may refer to the same real economic obligation. Historical files with prior tuple leak/invalid JSON can still fail closed without automatic migration.
- No independent HUMAN_OWNER identity root, authenticated provider receipt, first external SEND exactly-once, immutable H0 custody, physical restart/power-loss guarantee or canonical full Security/Quality and native SQLite P0 evidence.

**0/6 P0 HOMOLOGADOS — HARD NO-GO — UNCERTAIN — ZERO_AUTO_RESEND.** No merge to main, deployment, Global Worker, external provider SEND, real customer data/credentials, funds, or new spending.
