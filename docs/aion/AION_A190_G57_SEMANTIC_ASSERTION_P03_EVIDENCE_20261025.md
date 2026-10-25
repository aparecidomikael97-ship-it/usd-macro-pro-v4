# AtlasQuant / AION A190 — G57: business-event assertion required to reserve semantic intent

**Date:** 2026-10-25 (Cuiabá). **Branch:** `lab/aion-a190-g57-semantic-id-assertion-required-20261025`; **Draft PR #1543** stacked on G56 #1542, **not main**.

## Narrow local correction, not P0-3 certification

Prior G39 strict semantic reservation was **opt-in**. The caller could present `payload.business_event_id` but omit `semantic_event_id_lab`; `enqueue` would create separate scoped Outbox/Decision rows for multiple request IDs without writing any tenant-level semantic lock. Existing G38 test 02 and G39 test 11 deliberately recorded this as a security **RED**, despite themselves passing.

G57 code candidate at `da86833b41093c724314c5b31a5c2e4ef9b6d19b` checks key **presence**: when `business_event_id` exists but there is no asserted `semantic_event_id_lab`, it raises `G57_SEMANTIC_ASSERTION_REQUIRED` **before BEGIN IMMEDIATE**. The positive binding still requires equality and uses G39's existing tenant-wide atomic semantic lock. Ordinary payloads with no `business_event_id` retain legacy staging. The behavior change is intentionally fail-closed: integrations previously declaring a business ID but not supplying the matching semantic assertion will now be rejected. No production rollout authorized.

## Independently identified flaw; Codex boundary

Windows Codex CLI v0.164.0-alpha.11.1, session `01a17409-131c-7f70-ae11-7fd542d2e18c` with `-s read-only --ephemeral`, inspected the existing G56 source and G38/G39 tests. The review confirmed the `if semantic_event` bypass and recommended checking payload key presence, retaining no-event legacy payload compatibility and explicitly documenting existing historical lock gaps. It neither modified files nor ran tests.

A second Codex request after patch (session `01a17410-71d3-7cb0-8d87-37bc75e58a12`) **did not inspect files**, because that prompt prohibited all tools. Its suggestions were hypotheses only; **do not count it as a successful independent patch audit**.

## Falsifiable test evidence — test committed before patch

- New `labs/a190/test_g57_semantic_assertion_required_lab.py` committed FIRST at `128d3916ddb62d5996d8fd58e5f004217f6bcc86`.
- Actual Windows prepatch run against G56: **9 cases, 8 failing assertions**, including subtests for invalid empty/null/false IDs; actual gap = two unreserved rows from different request IDs despite same declared business event.
- After minimal motor patch: unchanged 9 tests **9/9 PASS**.
- One additional diagnostic negative-control (G57 test 10, commit `cd9a8f74adf8e0921c699d0ebc378d02fd36aff2`) simulates removing a prior semantic lock. A new alias can again acquire a lock with the same declared event; this test **passes while describing a known RED gap**, not a repaired historical guarantee. New suite **10/10 PASS**.

## Historical regression upgrades, explicitly audited

- G38: 8 old expectations errored with new fail-closed guard; positive fixtures now assert the declared semantic ID; known request/workspace alias RED becomes denied, and unique business events are used when testing three independent staging calls. G38 **24/24 PASS**.
- G39: 3 legacy intentional bypass cases errored; updated to require refusal when event field is present without assertion, while a payload **without** business-event ID remains valid for legacy replay. G39 **28/28 PASS**, including G39's deliberate RED showing two distinct fabricated declared IDs may still represent one underlying real event.
- G44: initial fixture declared `business_event_id` without assertion (39 setup errors). Fixture now binds the same event. G44 **39/39 PASS**, existing structural binding checks retained.
- G37: signed authority/witness fixture similarly declared an event without assertion; fixed only its synthetic staging input. Historical tests expecting multiple local aliases now demand one local row and one idempotent witness reservation; signed-issuer compromise and host+custody rollback **RED observations remain**. G37 **34/34 PASS**.
- All historical test updates preserve their prior git history and do **not** turn simulated external proof into trusted authority.

## Final complete local regression at exact SHA

At code/test/workflow commit **`68050ce96cc1bf2d1d77be1f40982daf10521bb2`**, isolated Windows worktree `C:\Users\apare\AtlasQuant-G57-Semantic-LAB-20261025` ran G30–G57, excluding G51 as its tests are included in G50. **501/501 PASS, exit code 0, clean git status**. This is 501 focused synthetic cases, not 501 certified P0 obligations.

GitHub Actions [G57 run #40216066277](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40216066277) was **QUEUED when last checked**, with two-OS test matrix of 501 cases per OS. The workflow was last updated at this exact SHA to include G37 fixtures and tests as trigger inputs. **Do not claim Ubuntu CI success unless real jobs conclude**. The report is added *after* the locally tested commit; it changes documentation only.

## Explicit unsolved P0-3 gates

1. A historical Outbox row with a missing/unbackfilled semantic lock can still coexist with a new strict reservation of the same declared event; G57 test 10 reproduces the limitation. A fail-closed historical inspection or externally anchored migration proof is needed before operational use.
2. Two different caller-declared event IDs can represent the same real economic obligation; tenant uniqueness of strings is not provenance or exactly-once provider execution.
3. Omitting **both** the payload field and assertion preserves legacy staging. Any future effect-bearing production entrypoint must establish mandatory, trusted business event identity; not established here.
4. No trusted HUMAN_OWNER root, provider-issued signed receipt, independently pinned immutable custodian, H0 power loss/rollback recovery, cross-provider idempotency or canonical A184 Security/dependency green evidence. No authorizations to merge or deploy.

**0/6 P0 HOMOLOGATED — HARD NO-GO — UNCERTAIN — ZERO_AUTO_RESEND.** No main merge, deploy, Global Worker, provider sends, customer data, payments, secrets, installation or spending.
