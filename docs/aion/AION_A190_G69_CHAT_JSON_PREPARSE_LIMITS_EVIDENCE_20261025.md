# AtlasQuant / AION A190 — G69 JSON preparse limits and incomplete escaped chat members

**Date:** 2026-10-25. **LAB branch:** `lab/aion-a190-g69-chat-json-preparse-limits-20261025`. **Draft PR:** [#1555](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/pull/1555) stacked on [G68 #1554](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/pull/1554), **not main**.

## Safety and scope

All strings/faux secrets and transactions here are synthetic on disposable SQLite. No real credentials, provider SEND, Worker, financial effect, customer data, merge, deploy or new spend. This is **not** operational P0 certification, DLP universality or external trust.

## Confirmed RED FIRST — initial 16 tests

File `labs/a190/test_g69_chat_json_preparse_limits_lab.py` was committed ALONE at test-only SHA **`ca6d12a0694e8d4910b40f25341af1c353a37eac`** BEFORE runtime edits and executed against G68:
- **16 cases, 8 PASS / 8 FAIL** on disposable Windows SQLite.
- Full JSON texts with **262145 UTF-8 bytes** (including multibyte characters) were accepted without a stable explicit preparse bound.
- Balanced **65 nested arrays** were accepted without a preparse depth guard.
- Huge JSON-looking input passed synthetic Outbox admission and chat append rather than failing with the specified dedicated errors.
- Names such as `refresh\\u005ftoken` in partial JSON embedded in ordinary prose were not recognized by literal fallback regex, leaving fake values.
- Controls for **262144 bytes accepted, 64 nesting levels allowed**, brackets inside quoted JSON values, safe public text, plain assignments and the G68 duplicate-key rejection were already GREEN.

## First LAB correction and independent Codex

Source `aion_chat/privacy.py` SHA **`b5fdee7b7f441042037ac04c56a9c87738758ff5`**:
1. Gate JSON-looking full chat text before `json.loads` using **262144 encoded UTF-8 input-byte maximum** and a lexical bracket-depth scanner (64 nested containers, quote/backslash aware). Failure markers: `G69_CHAT_JSON_INPUT_BYTES_DENY` and `G69_CHAT_JSON_NESTING_DENY`; isolated surrogate `G67_INVALID_UNICODE_DENY`.
2. Replace literal-member fallback with decoding of a captured quoted key using JSON semantics. Exact sensitive keys (including Unicode escapes) have **only their quoted string values** replaced, preserving other prose and member delimiters. Unrecognized public member names remain untouched. Does not attempt a universal parser for arbitrary text.
3. Outbox invokes redaction before BEGIN, so oversize input causes zero begin/reservation. `SQLiteChatStore.append_message` starts BEGIN first and is expected to rollback after a denial; the test verifies zero persisted messages and unchanged message count. These are intentionally distinct guarantees.
4. Original G69 tests **16/16 GREEN**, G68 **21/21** and G67 **14/14** direct inherited regressions GREEN.

Independent actual Codex CLI Windows read-only/ephemeral **prepatch** session `01a174d1-c7de-7e02-af07-286471b55a09` independently located input resource exhaustion and escaped partial-member leaks and recommended test-before-patch, strict UTF-8 bytes and lexical depth. **Codex neither edited files nor executed tests/network/provider.**

## Second genuine RED FIRST — malformed JSON bypass

An independent Codex CLI read-only **postpatch** session `01a174d5-f467-7a00-9cc5-e00471b4bf50` observed two omissions:
- Unclosed brackets such as **2000 opening `[` then `0`** left a nonempty stack, which suppressed the 64-depth denial and passed the input to `json.loads` where an uncontrolled recursion exception was possible.
- Quoted escaped sensitive keys in partial prose with an **unfinished quoted value** were left visible because the regex required the final closing quote.
- It also flagged scope limits: peak parsing memory is not 256KiB, direct cyclic native `Mapping` is not governed by this string gate, and plain prose strings remain outside the JSON input size policy. These are **OPEN**, not G69 fixes.

Three adversarial tests were committed **BEFORE second fix** at test-only SHA **`6ab9e683a397a7bfa04c1e807b6403c63c251412`**. Running them against first patch gave **19 total, 16 PASS / 3 FAIL**. This is actual RED, not a speculative finding:
- Malformed deep JSON was not explicitly denied before parsing.
- Incomplete escaped-name credential-bearing prose retained faux secret.
- Such incomplete prose also leaked its faux secret into a synthetic chat message.

Second `privacy.py` patch SHA **`282e787c0a26e55aeb6ca44f1b78c7b3e1afb8ae`**:
- Tightens depth refusal to include unclosed but internally consistent deep bracket streams, rather than depending on an empty final stack. A mismatched plain-text bracket sequence can still use fallback; no complete JSON-syntax validity claim.
- Avoids `lstrip()` copy before preparse by scanning for first non-whitespace character.
- Adds a specific partial-member fallback when quoted key is complete and matched as sensitive, but quoted value was interrupted at end of prose, masking the tail without inventing a closing quote.
- **G69 19/19 GREEN**, inherited G68 21/21 and G67 14/14 GREEN on isolated Windows.
- No edits to provider handling, semantic send/confirm trust, rollback primitives, history migration or autonomous actions.

## Exact code and CI provenance

Code+workflow SHA **`2fa24c4c63d131c8e6b0f8f822d11beaae808b97`** versioned `.github/workflows/aion-a190-g69-chat-json-limits-lab.yml` requiring **19 G69 cases** and 15 observable G69 protection/compatibility markers. Synthetic focused G30–G69 suite (G51 absorbed in G50): **673 distinct cases per OS**.

Actual detached isolated Windows worktree `C:\Users\apare\AtlasQuant-G69-Parse-LAB-20261025` at exact SHA `2fa24c4`: **673/673 PASS**, exit code 0, clean checkout.

[GitHub Actions run G69 v2 #40233180908](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40233180908) started at same SHA but both OS jobs were still QUEUED when report was initially written. **Do not claim Ubuntu/Windows CI success until both jobs and all markers are verified.** Documentation commits after tested code SHA cannot substitute for code CI.

Separate dependency-limited chat Golden Path remains NOT verified (preexisting absent `pandas` on local Windows); do not infer full canonical Quality/Security approval from this focused suite.

## Third RED-first (postpatch Codex) and corrected final source SHA

A second independent Codex CLI read-only/ephemeral audit `01a174da-d974-73e0-8eb0-c06a5257a195` inspected the tested v2 code `2fa24c4`, **without edits, executing tests, network or supplier calls**. It found:
- A 2000-`[` input followed by `0}` set `unbalanced=True`, evading the previous preparse depth denial even though it could overwhelm `json.loads`.
- A Unicode-escaped sensitive key followed by a quoted value ending with one orphan backslash bypassed the unfinished-value fallback regex.
- Earlier full-JSON 64/65 limits and the prior 19/19 cases remained valid; their coverage did not prove these additional cases.

Three new tests were committed **BEFORE the third engine patch** at **`564a84d3778f1200974edbc2e53400271a83cfb3`**: actual Windows isolated run had **22 total, 20 PASS / 2 FAIL**. Tests check malformed mismatched very deep candidate, unfinished escaped quoted value ending in a backslash, and a normal 75-bracket prose string that should remain untouched.

Third `aion_chat/privacy.py` patch SHA **`d0261375be3668ded15605db320d74859150fba4`**:
- Rejects deeply unclosed/mismatched JSON-looking input with **more than 128 bracket nesting levels**, even when its bracket sequence was flagged `unbalanced`, before `json.loads`. A modest-depth malformed plain bracket text (75) keeps legacy fallback; **64 remains the maximum for balanced/consistent JSON input**. This intentional distinction avoids treating all malformed bracket-containing prose as valid JSON.
- The specialized unfinished quoted member regex now admits a single trailing backslash at end-of-prose, masking the faux-secret before persistence.
- All **22/22 G69 GREEN**, G68 **21/21**, G67 **14/14** in immediate Windows regression. No changes to external actions, transaction authority or COMMIT/rollback.

The final **code+workflow SHA `61d6e3895ef9b31d14d59a3d8c1ff58508863b9f`** updates workflow `.github/workflows/aion-a190-g69-chat-json-limits-lab.yml` to require **22 G69 tests and 18 markers**, **676 focused distinct synthetic cases per OS**. The previous G69 CI #40233180908 (673 cases) cannot certify this final change.

[Latest G69 v3 Actions run #40233604212](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40233604212) was QUEUED at this document amendment; **do not claim cross-OS success without inspecting completed job statuses and logs**. The local final Windows focused regression was still underway when this document was updated.

## Open limits and non-conflation

- These are **input and nesting budgets for JSON-like chat strings**, not bounds on peak memory or CPU while running Python, regexes, parsing and producing redacted copies.
- Plain prose not starting with a JSON object/array remains outside the 262144-byte gate; enormous malformed content and very wide valid JSON within this bound are not globally node-budgeted by this shared redactor.
- Direct recursive `redact` of arbitrary native Mapping/list/tuple has no shared chat/store cycle/node budget; Outbox uses a separate G67 bounded preflight, which should not be conflated with universal redactor safety.
- Member-field recognition is pattern-based. Base64/obfuscation or arbitrary escaped truncated values are not guaranteed covered. Earlier stored content is not retroactively cleaned.
- No independent HUMAN_OWNER authentication, provider-signed external receipts, immutable monotonic H0 off-host custody, physical SQLite compatibility P0 clearance, true real first-send exactly-once or canonical Security/Quality approval.

**0/6 P0 HOMOLOGADOS · HARD NO-GO · UNCERTAIN · ZERO_AUTO_RESEND.** No main merge/deploy, Worker or external SEND.
