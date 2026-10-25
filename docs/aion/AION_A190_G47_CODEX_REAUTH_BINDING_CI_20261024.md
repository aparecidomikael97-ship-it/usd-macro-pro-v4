# AtlasQuant AION A190 G47 — Reauthorization integrity LAB evidence (2026-10-24)

## Scope

**PR Draft #1534**, stacked on G46 Draft #1533, never merged to main, no deploy, no Worker, no real provider, external action, spending, credentials or customer records. Candidate modifies opt-in LAB path of Outbox identity and G44 structural verifier. It is **not** external authorization, HUMAN_OWNER proof or P0 certification.

## Independent Codex sessions actually executed

On the authorized Windows `am12` isolated checkout, installed `codex.exe` v0.163.0-alpha.11.2, model `gpt-6.1-sol`, with `-s read-only --ephemeral`:

1. Session `01a17074-9fb0-7382-8046-874efd48b7ac` (exit 0, ~37.82 s): confirmed `requires_reauth` and `reauth_ref` were absent from both producer key material and G44 validation. `_authorization_gate` tests `requires_reauth is True`; altering the persisted JSON to false/other values or replacing reference without changing idempotency material was not detected by G44. Codex recommended exact bool/string normalization, conditional key material and fail-closed legacy behavior. This was **static read-only review**, not a Codex patch.
2. Session `01a17078-4221-7622-985a-be5d88041191` (exit 0, ~44.11 s): independently reviewed patched G47. Confirmed ordinary false/empty key remains identical and true/reference changes the key; warned of no actual trusted reauthentication issuer, insufficient legacy true/ref backwards compatibility, and a **coherent local DB+key rewrite** bypassing unkeyed local hash integrity. Suggested separate tests with pre-G47 fixture, callback matrix and full coherent rewrite. No Codex file writes or tests.

## RED then GREEN with disposable SQLite

First commit (12 tests before protection): **`ba3b0cfdbca241ffcc3c39410654c77ea10deed2`**.
- Windows **12 tests: 3 passed, 9 failed (expected RED)**; reproduced downgrade, substituted `reauth_ref`, non-boolean truthiness, changed reauth contract under same idempotency key and attempted bypass of strict claim.

Producer/auditor fixes:
- `atlasquant_aion_execution_outbox.py`, SHA commit `954656c2d7ee5acc5485051da760213bef013391`: exact bool and string enforcement, false + nonempty ref denied, **required** reauth/reference added to deterministic key material. Ordinary `False, ""` key material remains byte-for-byte unchanged; no silent migration.
- `atlasquant_aion_outbox_binding_lab.py`, SHA commit `c52b75488eb1d55b739f2ed36c1e37cd9ca0b5a5`: strict decision JSON reauth contract and version-matched key-material admission.
- Expanded to 18 G47 tests with explicit denial classifications, missing/noncanonical fields, double downgrade and idempotent alias safety, at `d1ee7c0498a9112eb2b1fb59b01d61854dd24434`.

**Verified Windows exact code SHA `d1ee7c0498a9112eb2b1fb59b01d61854dd24434`:**
- New G47 18/18, inherited G46 10/10, G45 7/7, G44 39/39, G43 32/32 = **106/106**.
- Wider local G30–G39 wildcard: **225/225**, and G40–G47 wildcard **188/188** = **413/413 distinct synthetic tests** across both wildcard batches, no reported failure (no external effect).
- No uncommitted code left in the isolated checkout during review.

## GitHub CI exact SHA

**Exact tested code/workflow SHA `aa9e58e9dfc29523838730ffc37e35dcbef00d4e`.** [G47 targeted two-OS Actions #40147093599](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40147093599) **SUCCESS**: Ubuntu and Windows **106/106 each**, **212 executions total**, covering G47 (18) plus G43-G46 (88). This evidence document is committed **after** that SHA and does not modify the tested code.

**A184 canonical run #40147093689 is separately RED**: candidate/base security-audit jobs failed, base canonical security-unittest and Quality failed, external RED and adversarial BASE RED by design, and other jobs can still be running. A G47 focused green check is **not** a successful canonical Security or complete system certification. Do not silently discount dependency vulnerabilities observed earlier (48 findings in pypdf/Pillow, subject to new specific log verification).

## Security gates not resolved

- Old persisted `requires_reauth=True` rows have legacy nonbound idempotency keys; new strict admission rejects them and requires **human-supervised review/reapproval**; no silent rekey or automatic first send. Previously downgraded rows that resemble ordinary historical rows may be undetectable locally.
- A full local DB rewrite can recompute unsigned hashes consistently; local structural OK != authentic HUMAN_OWNER identity, external authorization, or irreversible receipt/witness.
- `strict_binding_integrity_lab` is explicitly opt-in, cannot be misrepresented as universally deployed.
- Real source-bound, expiring, one-use reauth proof, provider confirmation and independent antirollback custody are still RED. No real external calls were performed.
- Fail-closed operational policy: **0/6 P0 homologated · HARD NO-GO · UNCERTAIN · ZERO_AUTO_RESEND.**
