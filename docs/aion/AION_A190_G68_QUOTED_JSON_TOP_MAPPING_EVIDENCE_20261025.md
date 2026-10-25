# AtlasQuant / AION A190 — G68: quoted JSON chat redaction and top-level Mapping

**Date:** 2026-10-25. **LAB branch:** `lab/aion-a190-g68-json-chat-top-mapping-20261025`. **Draft PR:** [#1554](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/pull/1554), stacked on G67 Draft #1553, NOT main.

## Strict boundaries

Only synthetic fake markers and disposable local SQLite were exercised. No customers, actual credentials, financial services, Worker, provider SEND, deployment, merge, funds or new spending. This does not close any external P0 or prove exactly-once execution.

## First real RED — 9 of 12 failed before code changes

At test-only SHA **`1a78e44003a2773a78cc3ea9ca834a59cb49f643`**, `labs/a190/test_g68_quoted_chat_top_mapping_lab.py` was committed BEFORE patch and run on isolated Windows, yielding **12 tests; 3 PASS / 9 FAIL**:
- Four tests proved fake tokens in textual quoted JSON chat fields escaped the existing assignment regex, even though JSON syntax was valid.
- Five tests proved `dict(payload or {})` / `dict(result or {})` invoked a custom top-level Mapping's hostile `__getitem__` before the pre-BEGIN, budgeted G67 snapshot. The same Mapping could be read twice or behave inconsistently.
- Benign JSON, plain assignment masking and ordinary replay controls were GREEN before patch.

First patch: `aion_chat/privacy.py` SHA **`05c9885020bb439a2c4cb8aaa1f7cf0e0d637048`** used a quoted-member pattern retaining quotes/delimiters while masking values. `atlasquant_aion_execution_outbox.py` SHA **`48f9569879ea6d6296a12cedf903b5c1b36d7ddf`** removed implicit top-level dict conversion. Only Mapping/None admitted; the G67 walker creates a single bounded built-in snapshot BEFORE semantic event checks and confirmation redaction/BEGIN. The direct suite turned **12/12 GREEN**, with G67/G66/G65 immediate regressions GREEN.

Four added tests at `52065c21d0c7d9a4ed5713a2e1adcf3a752a520a` verified 4300-element top-level custom Mappings cannot bypass the G65 4096-node budget, in both enqueue/confirm, with **zero BEGIN**, and non-Mapping top-level values fail closed with TypeError (explicit compatibility narrowing). G68 became **16/16 GREEN**.

## Second real RED — escaped Unicode JSON keys and old regex corruption

Independent postpatch Codex read-only session `01a174c5-8c04-7cf0-8dfe-fa3b51ce6640` spotted (a) `{"refresh\\u005ftoken":"FAKE"}` is valid JSON decoding to a sensitive key yet literal quoted regex did not match, and (b) an ordinary valid JSON `{"public":"password=FAKE"}` could be malformed by the older unquoted assignment regex. These were not originally covered.

Tests for those cases and JSON arrays were committed BEFORE the second fix at SHA **`40698e09c28a59a9ebedb064cedd0347de74fb75`**, then executed against earlier G68 code: **19 tests; 17 PASS, 1 FAIL, 1 ERROR**. The escaped-key fake value was not masked; the public JSON assignment case failed to parse after redaction; the safe nested array control passed.

Two more tests were committed at `ecdce1f2cdf098d6013fd51453bb40b6c07c2a8a`, before the second fix, asserting fail-closed behavior on duplicate *logical* JSON keys (including Unicode-escaped aliases) and complete rollback of such invalid chat-message admission.

Second `privacy.py` correction SHA **`cba532e6cc3b5c847e3b4db04512da8b04e0c12b`**:
- When the **entire chat text** is valid JSON object/array, parse with a unique-key `object_pairs_hook`; any duplicate logical key raises `G68_DUPLICATE_CHAT_JSON_KEY_DENY`.
- Apply structural redaction to decoded keys and values. If anything is masked, serialize the already-redacted structure into valid JSON; otherwise return original text unchanged. This prevents the older regex from corrupting otherwise valid JSON text and catches Unicode-escaped sensitive key aliases.
- Incomplete/non-JSON text falls back to the existing specialized quoted-member and assignment/token-pattern rules. It remains heuristic masking, not universal DLP. User-entered invalid huge/deep JSON, arbitrarily encoded formats, malicious custom Python code and end-to-end product behavior are NOT certified.
- **G68 21/21 GREEN**, including duplicate-key rollback and Unicode escape, and inherited G67 14/G66 12 GREEN in direct tests.

## Current code+workflow test provenance

The G68 Windows isolated detached worktree: `C:\Users\apare\AtlasQuant-G68-JSON-LAB-20261025`. Workflow `.github/workflows/aion-a190-g68-json-chat-top-mapping-lab.yml` was amended to **21 G68 tests** and extra marker checks at source+workflow SHA **`fa1ebe5311a8cfdd73fa6ce244b1bf17248282b1`**, configured for **654 distinct G30–G68 synthetic focused cases per OS** (G51 combined inside G50).
- [GitHub Actions G68 UPDATED run #40231864079](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40231864079) was queued when the evidence report was drafted. **Do not claim CI cross-OS success before both jobs complete and their actual logs/marker counts are checked.**
- An earlier [G68 CI run #40231486506](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40231486506) ran a previous revision with only 16 new G68 tests. It MUST NOT be represented as validation of the 21-test updated source.
- **Full updated Windows local VERIFIED:** on exact code+workflow SHA **`fa1ebe5311a8cfdd73fa6ce244b1bf17248282b1`**, clean detached worktree G30–G68 ran **654/654 PASS**, exit 0. This supersedes the earlier G68 649-count local run. No canonical entire Security/Quality claim.

## Independent Codex sessions, local only

Installed Windows Codex CLI v0.164.0-alpha.11.1, `-s read-only --ephemeral`:
- Prepatch session `01a174c0-b936-71a3-a26c-37458f14b6ab` read G67 and independently located quoted-text JSON leakage and top-level Mapping implicit coercion, recommending tests first and value-only string masking.
- Postpatch session `01a174c5-8c04-7cf0-8dfe-fa3b51ce6640` read exact first CI source `d0658a8`, confirmed G68 fixes in source and identified escaped Unicode-sensitive JSON key and potential corruption of valid JSON by legacy regex; this directly informed second RED.
- A further **COMPLETED** post-second-fix Codex read-only session `01a174cb-3804-7872-b281-b88a35b0137a` inspected exact tested code+workflow SHA `fa1ebe5311a8cfdd73fa6ce244b1bf17248282b1`. It confirmed static behavior: full JSON parsing decodes Unicode-escaped field names; duplicate decoded keys raise the stable denial; changed JSON is serialized structurally to preserve syntax; unchanged JSON keeps original text; partial JSON/prose falls back to pattern redaction; top-level Mapping is snapshotted before BEGIN. The reviewer **did not execute tests, edit files, or use a network/provider**. Remaining *unverified* G69 targets: unbounded string-input parsing may allocate memory or cause recursion before outer admission byte budgets; quoted JSON-like text inside prose may contain escaped sensitive member names that the literal regex fallback misses; benign `token` keys and duplicate keys can be rejected/masked by policy even when not secrets.

## Unclosed architecture and privacy constraints

- Full JSON parsing/redaction of chat text may allocate memory before any output budget; very large/deep JSON messages can be expensive or trigger parser exceptions. No bounded sandbox against adversarial CPU/host execution was provided.
- A custom synchronous `Mapping.items()` or its iterator can block indefinitely or perform arbitrary side effects **inside Python**; a 4096-node counter limits successful yielded items, not the duration of a non-returning `next()`. External execution isolation would be required.
- The shared redactor changes behavior across chat/store. Previously saved content is not migrated/sanitized and historical local hashes are not externally anchored. Invalid JSON fallback remains pattern-based.
- No independent HUMAN_OWNER root identity, provider-signed receipts, H0 monotonic third-party custody, true first provider SEND uncertainty witness, physical SQLite compatibility gate closure, or canonical full Security/Quality certification.

**0/6 P0 HOMOLOGADOS · HARD NO-GO · UNCERTAIN · ZERO_AUTO_RESEND. No merge/deploy/Worker/real provider SEND.**
