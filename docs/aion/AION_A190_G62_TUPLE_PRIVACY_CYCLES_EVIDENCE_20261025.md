# AtlasQuant / AION A190 — G62 tuple privacy, cyclic payloads and post-reservation transaction integrity

**Date:** 2026-10-25. **Branch:** `lab/aion-a190-g62-tuple-redaction-cycles-rollback-20261025`. **PR Draft:** [#1548](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/pull/1548), stacked on G61 #1547, **not main**.

## Real risk and constraints

The existing `aion_chat.privacy.redact` recursively covered `dict` and `list`, but not `tuple`. Python's `json.dumps` nonetheless serialized tuples into JSON arrays. Thus a tuple containing `{"password":"FAKE_MARKER"}` and embedded faux-token strings could persist sensitive-looking content in `action_decisions.data` without redaction.

The G61 finite-payload check traversed tuples without ancestor cycle detection; a `tuple→list→tuple` cycle caused `RecursionError`. A self-referential dict caused `RecursionError` inside `redact`. Both occurred before SQLite BEGIN, but did not provide a stable bounded denial. No real customer information, secrets, suppliers or financial actions were used.

## Independent Codex review, prepatch

Codex CLI Windows v0.164.0-alpha.11.1, read-only/ephemeral session `01a17451-7d0d-7611-85b4-b5a4432e467e` inspected privacy, enqueue, finite helper and G61 tests. It **did not modify files, execute tests or use the network**. Findings: tuple redaction bypass, cycle check needed before the **first** redaction (there is an early semantic-validation call), and untested second `__str__` failing after semantic reservation INSERT. Suggested an active-ancestor set for cycle detection rather than a global seen set, preserving repeated acyclic references.

## Falsifiable RED committed and executed before patch

`labs/a190/test_g62_tuple_privacy_cycles_transaction_lab.py` was created FIRST at test-only SHA **`09c47670ada875a60153d446a048dc7b2eaa3b1d`** and executed on disposable SQLite in isolated Windows worktree:
- **9 tests: 5 PASS, 2 FAIL, 2 ERROR**.
- FAIL 01/02: raw faux-password and faux-token marker stored unredacted in JSON and in redaction output.
- ERROR 04/05: tuple/list indirect cycle and dict self-cycle raised `RecursionError` instead of `G62_CYCLIC_PAYLOAD_DENY`.
- Controls 03/06/07/08/09 already passed, including valid shared acyclic references, normal idempotency, and post-reservation rollback or failed rollback quarantine. They are existing protection evidence, not repairs attributed to G62.

## Restricted correction + intermediate test

1. `aion_chat/privacy.py` SHA `bcf61a211bb7ea487cb20263314bb89875e79721`: redaction now processes `(list,tuple)` recursively and normalizes to JSON-compatible list, so nested credential keys/strings are masked before hashing/persistence. JSON tuples were already represented as arrays, but raw tuple-nested data was previously not redacted. Beware historical legacy same-intent digest mismatches: **no migration or silent repair**.
2. `atlasquant_aion_execution_outbox.py` SHA `4d7d9671affe71f2fb641b18dbbd2fe0960dca7d`: `_assert_acyclic_payload_lab` scans dict/list/tuple with an active identity set, before main redaction and before BEGIN, emitting `G62_CYCLIC_PAYLOAD_DENY`. Repeated noncyclic shared objects remain valid.
3. First postpatch rerun **8/9 PASS, 1 ERROR**. The remaining case exposed **another earlier** `redact(raw_payload)` in `enqueue` semantic binding validation. This was a real ordering defect in the first attempted fix, not test noise.
4. SHA `509e330d4038270b1c46b9690a1021157aa243d9` moved the cycle check before **every** redaction, reusing `safe_payload` for semantic presence validation. **9/9 GREEN**, direct G61/G60/G31 also GREEN.
5. Test-strengthening SHA `0fa51b93003fcda27278f7ae39c3fc993c32677d`: added cycle hidden under sensitive-key `password`, and instrumented the second `__str__` to prove `semantic_reservations_lab` had **one uncommitted row** at moment of exception (`db.in_transaction=True`). After healthy rollback, action_decisions/outbox/reservation/effects all empty. With injected failed rollback, primary ValueError survived, secondary OSError chained, store handles detached/failed, new admission refused and a separate SQLite reopen confirmed no committed effect. **G62 10/10 GREEN**. The transaction rollback logic itself was not changed.

## Windows complete regression and cross-OS CI provenance

- Code+workflow SHA **`79f22e586c3b044361420890eb8dc689c501019e`**, isolated Windows checkout `C:\Users\apare\AtlasQuant-G62-Privacy-LAB-20261025`: **G30–G62 559/559 PASS**, exit 0, clean checkout (G51 cases consolidated in G50).
- GitHub Actions [G62 run #40221864032](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40221864032) was started at this SHA; Ubuntu job `121254959201` **SUCCESS** when the report was created; Windows job `121254959443` was queued. **Do not claim full cross-OS success without a completed Windows job and actual log markers.** This report is a subsequent documentation-only commit, not the source-tested SHA.
- No claim of canonical full Quality/Security clearance.

## Independent post-patch Codex review — explicit remaining risks

A **second** Codex CLI review (`-s read-only --ephemeral`, session `01a17457-549a-7100-b5ce-447ab13105c7`) examined exact tested source/workflow SHA `79f22e586c3b044361420890eb8dc689c501019e` against G61. **No tests were executed or files changed by Codex.** Its findings:
- Verified: `enqueue` order is cycle scan → one redaction → semantic presence check → finiteness → digest → BEGIN. Guard traverses mapping keys and values and tuples with active ancestors, retaining shared DAGs. The existing G62 tests actually observed an uncommitted semantic reservation during the second `__str__`, and no intermediate COMMIT.
- **Important scope limitation:** `_confirm` still calls `redact(dict(result or {}))` **without a cycle preflight**. G62's cycle-safe claim applies to **`enqueue` only**; confirmation-result cycles remain a future G63 RED/test target.
- **Unproven/high-value next tests:** custom objects with volatile `__str__` that changes digest vs stored data or reveals secrets; custom mappings/bytes/set and sensitive *dict keys* outside the redaction contract; deep acyclic nested input triggering Python recursion limits (especially below secret-key entries). No DLP or compatibility guarantee inferred.
- The after-reservation failure tests cover partial state with a semantic reservation but before decision/outbox INSERT; they do **not** test interruption after all three INSERTs, physical crash or hostile rollback.

## Residual safety limits

- This is **pattern redaction**, not universal DLP. An opaque Python object can have `__str__` emit a secret; `default=str` is still used. Extreme nesting/recursive limits, mutation during traversal, generator/set/custom Mapping behavior and durable legacy compatibility are not certified.
- Payloads staged before tuple redaction correction may retain historical unredacted values or digest mismatch; old records are not migrated, deleted, sanitized or repaired by this PR. The G59 strict history scanner can fail closed.
- Neither local synthetic signatures/hashes nor 559 tests establish authentic HUMAN_OWNER, real provider receipts, physical H0 restart/rollback resistance, remote exactly-once SEND, trusted custodian or the native SQLite P0 gates.

**0/6 P0 HOMOLOGATED — HARD NO-GO — UNCERTAIN — ZERO_AUTO_RESEND.** No merge, deploy, Worker, external SEND, credentials, customer data, funds, production effect or new spend.
