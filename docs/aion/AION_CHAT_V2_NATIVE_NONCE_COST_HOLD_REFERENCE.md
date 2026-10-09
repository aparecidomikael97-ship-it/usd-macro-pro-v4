# AION V2 — native nonce and signed maximum-cost HOLD (local reference)

**Date:** 2026-10-09. **Parent:** Draft #1125, atop #1124/#1123/#1122/#1121/#1120/#1119. **Safety: NO-GO** for any live paid model, installer, deployment or real owner-key action.

## Why

Draft #1122 has SQLite nonce/budget reservation for signed **V1** mathematical consent. Draft #1125 introduced a separate, stronger V2 signature covering the **entire resolved provider request** (resolved model, endpoint, output token maximum, timeout, exact final prompt, signed cost cap, scope and pending user message). A V1 ledger hold cannot be used as V2 authority, and V1 signatures cannot be silently upgraded.

This separate **reference V2** uses `review_signed_full_provider_request_v2` inside a new `ReferenceV2NonceCostLedger.hold_reference_only`. It does not trust a boolean claiming verification, does not call any provider, and does not modify the chat's user row. It recomputes V2 signature validity and full-request preview/matching every time before the SQLite write. Its own output is never authority.

## Reference properties and tests

- A distinct pair of `reference_v2_config` and `reference_v2_holds` tables stores V2-only exact policy configuration and signed intent hash plus **full provider request digest**. Presence of V1 or unexpected tables in the same DB file is a hard error: **no silent migration or reset**.
- `BEGIN IMMEDIATE` serializes local reference nonces and cap usage, WAL + synchronous FULL. Every reference hold debits the **full signed maximum** in integer USD microunits; lower synthetic quote is only a preflight constraint.
- Unique nonce, unique signed transcript and one hold per scoped pending USER message. Repeated identical signature returns `REFERENCE_ALREADY_HELD_UNTRUSTED` without another hold. Nonce reused for different intent, distinct nonce for same message, lowered policy, changed period/budget/key fingerprint and exceeded cap block.
- The stored V2 request digest, nonce, period, scope and signed-cap sums are checked on snapshots; test-induced corrupt values fail closed. Partial SQL failures rollback. Concurrent exact requests serialize.
- Valid V2 signatures are STILL `FULL_REQUEST_SIGNATURE_MATH_VALID_UNTRUSTED`. The public key, config, policy generation, reference month and synthetic quote are caller-supplied fixture values, not independently attested.

## Boundaries that MUST NOT be confused

**SQLite is not an independent witness.** Replacing both Chat DB and V2 ledger with a saved snapshot can reinstate a spent nonce. Startup check is not antirollback. A privileged local operator could substitute the V2 file or alter config consistently. There is no TPM NV / independent remote monotonic witness, nor protected clock. This is a *reference database*, not a production quota engine.

**Not a real spending system:** no current market/provider pricing authentication, tokenized invoice reconciliation, FX, billing, reservation settlement, global budget aggregation, multi-host concurrency, owner identity proof, owner/collector key enrollment, public trust anchor, one-shot external request claim, uncertain paid-outcome resolution or durable assistant answer persistence. The Chat store and reference ledger are **not cross-database transactional**: a mutation of the pending USER message between mathematical check and reservation is not prevented by these two separate stores. No request approval `True` can be derived from this module.

**Recovery/restore gate:** Future production ledger must compare authenticated, independently durable monotonic head/epoch from a witness outside restorable host storage, verifying full chain and key/policy generation before any dispatch or recovery. Witness offline, damaged, lower state, revoked pin, unknown prior HTTP outcome or rolled-back disk snapshot => deny call and require reviewed recovery; never reconstruct spend by trusting only this SQLite file.

**No automatic rollover/release/refund.** Reference month is fixed; never reset in-place. No V1 import under this contract. Any true migration from V1 requires a separate consent, verified baseline/witness and rollback-safe procedure. Review #1117 before authorizing physical actions.

## Checks

CI on GitHub-hosted Windows and Ubuntu tests V2-native hold, retries, cross-intent nonce rejection, duplicate message, signed max cap and budget, changed model/tokens/timeout, tampered signature and pin, reopen/config mismatch, V1 DB refusal, corruption and SQL rollback, concurrent holds and zero network. Runs inherited signed V2, V1, provider and pending-message suites.

**Still false:** `trusted_human_owner_consent`, `independent_witness_protected`, `hardware_antirollback_verified`, `real_budget_reserved`, `real_billing_authorized`, `model_invocation_authorized`, `provider_called`, `installer_authorized`, `safe_to_resume`.

**NO MERGE / NO DEPLOY / NO REAL API / NO BILLING / NO KEYS / NO HOST / NO INSTALL.**
