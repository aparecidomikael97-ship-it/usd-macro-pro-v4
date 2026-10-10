# AION P0 — Owner + staged chat compatibility and cross-device handoff, 2026-10-10

**State: ISOLATED REVIEW CANDIDATE — not production enrollment, device pairing or installer authorization.**

## Provenance and overlap inspection

- Frozen `main` baseline: `5744b2b7b17c84331e6f27c569064993ff587782`.
- This branch is from **UI Draft #1200 exact HEAD** `97b0a845cdb8a74b0a5429dd06dd4d3e08e96875`; all previously green Chromium/SQLite safety code preserved.
- Original owner-facing pure-contract files imported unchanged from **Draft #1015 exact HEAD** `e14f01b03b072c4bc20694e488c1c399ab8c97d1`, then one minimal `continuity_handoff` privacy hardening and test/doc changes. #1015 remains untouched/unmerged.
- Security/source/witness Draft #1191 HEAD `7d4af5e45b8e80ca43e65171d28255510b76b3b1` remains **outside** this code candidate: it includes 246 path changes, external witness 20/20 BLOCKED and intentional operational readiness failure.
- Against the same `main`, original Owner #1015 changed 4 files, UI #1200 changed 32 files, security #1191 changed 246 files, **zero overlapping paths among all three sets**. This is a *syntactic* collision check, not a proof of semantic integration or source ownership.
- No changes to frozen Core V1, `main`, #1015, #1191, #1200, Worker, Render or external providers. Native first-install remains HARD NO-GO.

## Actual reviewed contracts and facts

1. `atlasquant_access_control.authenticate` creates a synthetic but structurally real `ADMIN` session with expected permissions and `credential_fingerprint`; `session_is_current` checks role and fingerprint against registry. Owner `owner_binding` and chat `validate_product_binding` use compatible `allowed=True / mode=AUTHENTICATED / role=ADMIN / session` fields.
2. **HUMAN_OWNER is not created by ADMIN login.** Owner binding additionally requires an *externally verified* assertion from a trusted host; no public enrollment/custody has occurred. The tests inject a synthetic assertion solely to exercise the contract and cannot confer owner authority.
3. Chat `Scope(owner,tenant,workspace)` is injected and its owner is checked against session username. **Neither Owner contract nor chat structural binding independently proves the authenticated user's membership in an arbitrary tenant/workspace.** That must be established in trusted host resource membership registry before injection. Cross-tenant tests of an in-memory mock cannot certify the external trust source.
4. Real Chromium in #1200 shows historical `UNKNOWN`, 2→2 replay and current-attempt ACK resolution. That CI does NOT prove cross-device sync, device trust or real Windows desktop action.
5. Owner V1 `continuity_handoff` previously forwarded arbitrary nested/value metadata if a field was not an **exact banned key**. Example `context={"notes":{"accessToken":"SYNTHETIC_SECRET"}}` was outside its forbidden-key list and its return always reported `secrets_transferred=False`. This was a false negative risk for private content/credentials crossing to a second device despite lack of actual transport.
6. Handoff now **fails closed on any unknown field or non-enumerated value**. Only fixed `mode`, fixed generic `topic` category and numeric bounded `slide` are accepted. String blobs, nested structures, tokens under renamed keys, invalid types and other arbitrary context are rejected. This can reduce flexibility until a trusted post-reauth server-side fetch exists, intentionally so.

## Hosted regression gates, not an install certificate

An isolated Windows/Linux exact-head CI matrix executes:
- the pre-existing #1015 owner contract tests;
- new cross-stack tests using **real synthetic password-hash login**, compatibility with chat binding, malicious/stale/open-mode denial, strict handoff negative cases and external command plans without actual execution;
- explicit side-effect markers ensuring the contract contains no socket/provider/subprocess/microphone/Worker or deploy actions.

All test identities, credentials and contexts are synthetic. No real network/service/device actions are authorized or executed. Other main-targeted Quality, Chat History, UI Turn Notice, Core/Release workflows will execute on the PR's combined branch. Global Quality may check out a PR merge ref; do not conflate its log with exact source-HEAD tests.

## Remaining NO-GO

- Independent HUMAN_OWNER identity + collector key enrollment, revocation, proof of possession, credential/device binding;
- authenticated tenant/workspace membership and safe cross-device rehydration from the scoped durable store after target login, not arbitrary handoff text;
- independent monotonic witness/antirollback and real trustworthy current head, production source admissions, FinOps/LGPD;
- installer build manifest, signature verification, sandbox physical Windows, consent/rollback and action-level approvals;
- production voice/hotword/local app launch and secure IPC not implemented, not permitted by this contract.

A passed negative contract test is not `OWNER_ENROLLED`, `WORKER_READY`, `DEVICE_ATTESTED` or `INSTALL_AUTHORIZED`. **First installation HARD NO-GO.**
