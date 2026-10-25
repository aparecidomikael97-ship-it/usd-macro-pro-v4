# AtlasQuant / AION A190 — G67 stable Mapping snapshot, shared chat redactor and UTF-8

**Data:** 2026-10-25. **Branch LAB:** `lab/aion-a190-g67-redact-snapshot-unicode-20261025`. **PR Draft:** [#1553](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/pull/1553), stacked on G66 Draft #1552, **not main**.

## Technical intent — falsifiable local protection, never external certification

G66 redacted more sensitive field names but left five specific LAB issues:
- Values of `refresh_token` and `private_key`, including camelCase aliases, could remain in the JSON stored locally.
- Shared `aion_chat.privacy.redact` received non-string mapping keys without the Outbox's own G66 preflight and raised an incidental TypeError. The shared chat append flow calls redaction after BEGIN, so the error must have correct rollback behavior.
- G66 iterated a custom nested `Mapping.items()` in its preflight and a second time in redaction. An adversarial custom Mapping returned a different synthetic key/value on the second visit.
- An unpaired Unicode surrogate produced an incidental UnicodeEncodeError instead of a stable denial.
- Plain chat text of the form `refresh_token=FAKE...` and `private_key: FAKE...` was not masked by the string-assignment rule.

All test markers are **fake**, the SQLite database is disposable and **no financial provider, Worker or customer data** was involved.

## RED-first evidence, two independently versioned rounds

1. **Test-only SHA `4223f492877356de815d6d031734530c25da46a2`**, file `labs/a190/test_g67_redactor_snapshot_unicode_lab.py`, before runtime changes: **12 tests; 4 PASS, 6 FAIL, 2 ERROR**. Cases #01/#02 exposed unmasked field names, #03/#04 confirmed double `Mapping.items()` traversal, #05/#06 TypeError in redactor/shared chat, and #07/#08 lacked explicit Unicode surrogate denial.
2. G67 runtime correction initially committed at `aion_chat/privacy.py` SHA **`5d23bde632960f12c38ba110bd7a926d1ee0cb1a`** and `atlasquant_aion_execution_outbox.py` SHA **`867d03b9e532d0d178a2982d933bf946e422ca38`**. Same 12 synthetic tests **12/12 PASS**; G66 12, G65 19, G64 16, G63 13 also PASS in direct regressions.
3. **Expanded test-only SHA `1963b4c7d6b4e0757b250f568c658e1e212e4c6a`** added plain-text/chat content controls before touching text pattern: **14 tests; 12 PASS, 2 FAIL**. Both #13/#14 confirmed `refresh_token=...` / `private_key: ...` fake values remained visible in the shared string redactor and persisted chat messages.
4. `aion_chat/privacy.py` subsequent SHA **`14a31229a6621066d34c2e0b6e1b02804028d15f`** expanded textual assignment patterns. **G67 14/14 PASS**, inherited G66/G65/G64 controls also PASS.

## Narrow code behavior and local transaction evidence

- For Mapping values, `_assert_acyclic_payload_lab` now constructs a **stable built-in dict/list/tuple copy** while enforcing the existing 4096 expanded-visit limit, maximum depth 64, active-ancestor cycle checks and G65/G66 sensitive/nonstring-key denial. The subsequent redact/serialization consumes **that snapshot**, not a second iteration over custom `Mapping.items()`. For a shared DAG, occurrences are expanded/counted individually; no atomic snapshot of arbitrary caller-controlled Python execution is claimed.
- Shared `redact` now masks `refresh_token`, `refreshToken`, `private_key`, `privateKey` and `authorization ` values as appropriate. Non-string mapping keys raise explicit `G67_NONSTRING_REDACT_KEY_DENY`. Outbox retains **`G66_NONSTRING_JSON_KEY_DENY` before BEGIN**. The chat/store `append_message` negative control asserts a failed synthetic message after BEGIN rolls back without partial persistence and keeps storage healthy.
- Encoded surrogate text is explicitly refused `G67_INVALID_UNICODE_DENY` at UTF-8 boundary before Outbox BEGIN. Previously accepted valid multibyte UTF-8, finite and normal text remain in inherited G65/G66 regressions.
- The changes do not send, replay or repair any external action. No automatic revalidation/migration of old privacy-sensitive records.

## Independent Codex review (real, read-only, two rounds)

Codex CLI Windows v0.164.0-alpha.11.1, `-s read-only --ephemeral`:
- Prepatch session `01a174b2-6582-7ec2-90f3-df548dd81ba1` inspected G66 and independently found the two-pass Mapping issue, aliases and shared-chat behavior, recommending a budgeted structural snapshot before redaction. **No files edited/tests run/network used**.
- Postpatch session `01a174b8-9210-7a43-958f-e02065d6217c` inspected code/workflow SHA `5882d35fd78e55ed64c98036afe657da54c4c96e` and verified the guard precedence, stable snapshot use, field/text aliases, surrogate deny and unchanged transaction ordering **by static inspection only**. Codex did not run tests and its review is not cross-OS evidence.
- **Unresolved, possible G68 RED:** custom `Mapping.items()` can itself block or perform arbitrary side effects; the top-level `dict(payload or {})` materializes before nested validation. The snapshot is per occurrence, not atomic over the entire hostile object graph. Chat strings containing *quoted JSON syntax* like `{"refresh_token":"FAKE"}` may escape the assignment regex due to a closing quote before the colon. Additional source patterns, invisible Unicode key variants, historical replay compatibility and input memory budget are not certified. The `_assert_acyclic_payload_lab` return annotation still says `-> None` although it now returns a snapshot — cosmetic static typing debt, not new runtime validation.

## Focused regression provenance, actual local execution

Code/workflow SHA **`5882d35fd78e55ed64c98036afe657da54c4c96e`**:
- Windows detached clean worktree `C:\Users\apare\AtlasQuant-G67-Snapshot-LAB-20261025`: synthetic focused suite **G30–G67 633/633 PASS**, exit 0, Git checkout clean. G51 cases are consolidated within G50.
- New `.github/workflows/aion-a190-g67-redactor-snapshot-lab.yml` configured for Ubuntu and Windows, **633 focused synthetic cases per OS**.
- [GitHub Actions G67 run #40230359407](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40230359407) was queued at initial evidence entry. **Do not claim completed cross-OS results until BOTH jobs are successful and actual test counts/markers verified.** Documentation commits after tested SHA are not runtime-code retests.

## Critical remaining HARD NO-GO

No genuine HUMAN_OWNER authentication, provider-signed receipt, first unknown-result external SEND deduplication, independent monotonic H0 custody, physical host rollback resistance, native SQLite compatibility P0 clearance or canonical complete Security/Quality proof has been furnished by these tests. Fail-closed synthetic admission is not operational homologation.

**0/6 P0 HOMOLOGADOS · HARD NO-GO · UNCERTAIN · ZERO_AUTO_RESEND. No main merge/deploy/Worker/real supplier SEND/customer data/financial effect/credentials/paid resources.**
