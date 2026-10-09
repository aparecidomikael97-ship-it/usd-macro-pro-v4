# AION V2 — persisted chat USER turn + authenticated host scope + owner-signed one-shot (REFERENCE)

**9 October 2026. Draft stacked on #1143 → #1142 → #1141 → #1140 and the AION V2 security chain. Production remains NO-GO.**

## Gap from #1143

#1143 composed mathematical Ed25519 owner approval, exact sealed-provider full-request digest, signed PREPARED witness heads and a single local SQLite claim, but **trusted the host to provide the original USER message hash and pending-turn correlation digest**. A caller could supply a plausible matching original hash even if the persisted chat turn had changed or been archived.

This Draft adds a new **reference-only** composition that reads the **existing actual AION scoped SQLite chat store** and invokes the existing signed full request reviewer *before* permitting #1143 to burn a local nonce.

## Code

`atlasquant_aion_v2_persisted_chat_owner_one_shot_reference.py`:

1. Takes existing `SQLiteChatStore`-compatible store, typed `Scope(owner_id,tenant_id,workspace_id)`, a host-provided access decision, exact persisted `conversation_id`/`message_id`, signed owner V2 transcript, original one-shot SQLite journal, and two signed journal witness READs.
2. Reuses **`review_signed_full_provider_request_v2`** (without weakening its checks), which invokes **`validate_product_binding`** and requires host `allowed=True`, authenticated ADMIN username matching the owner scope, presented session fingerprint and required permissions. It checks live scoped, nonarchived conversation and persisted pending USER message with exact source digest, metadata, no attachments and signed request digest, verifies mathematically the Ed25519 V2 transcript and actual fully resolved provider request SHA256. This is not independently verified network login/real HUMAN_OWNER physical presence.
3. Requires the exact signed transcript digest `signed_payload_sha256` from the stored-message reviewer to match the prepared #1133 journal intent. Independently rereads the **current** pending `USER` row, reconstructs `source_message_sha256` directly from stored text (never accepts caller-provided hash), and takes the request correlation digest from the persisted pending-turn metadata, rejecting any mismatch, wrong role, changed metadata or archived conversation.
4. Passes only those derived values to the existing #1143 composed owner PREPARED/double-witness reference. Checks signature math and exact sealed current provider POST SHA256, two distinct fixture signed witness READ envelopes over the same local prepared journal. Only a reference match is returned — all operational authority flags FALSE.
5. `consume_persisted_owner_local_reference_only` repeats both full signed chat review and independent pending-row read immediately before trying #1143's **local SQLite `BEGIN IMMEDIATE` once-only nonce burn**. Any mutation detected between reviews BLOCKS; a consumed nonce cannot be reused. There is **no provider invocation, real API token, real GET/POST, production access, or network permission**.

## Explicit security negative controls

- Host-supplied mock session or access object can claim `AUTHENTICATED/ADMIN`. The reference checks *consistency* with the owner scope but **cannot attest a real IdP, Windows login, authenticated token, session revocation or identity enrollment**. Forged owner pin+matching private signature mathematically passes, but custody and owner presence are false.
- An attacker with database update privileges can rewrite/restore an old matching chat row plus original signed heads and journal, and potentially win a race **after the last chat reread but before the local journal claim**. There is no cross-SQLite global transaction, protected monotonic server truth or distributed lock. All remote antirollback, independently authenticated session, cross-chat/journal atomicity and trusted original-store provenance flags remain FALSE.
- The pending USER content is real persisted data as retrieved by the existing scoped chat store; **not** a synthetic caller-supplied hash. However neither this chat DB nor the local dispatch journal is certified remotely protected in production.
- No reliable cost estimate/real ledger CAS/actual billing reconciliation/provider-side request idempotency or authoritative vendor receipts; a lost reply after a possible paid POST is UNKNOWN_OUTCOME and **MUST NOT** auto retry.
- Both witness public pins, owner key, freshness challenges and their signed heads are synthetic test fixtures and not enrolled with independent key custody. This does not deliver the FIDO2/Hello ceremony.

## Tests / run strategy

`tests/test_atlasquant_aion_v2_persisted_chat_owner_one_shot_reference.py` uses the actual `SQLiteChatStore`, `stage_pending_model_user_turn`, synthetic Ed25519 owner/primary/secondary keys, the original #1133 local journal, and the exact signed #1143 reference. Adversarial cases include owner/tenant/workspace substitution, other conversation/message, different role/username/permissions/anonymous session, forged owner pin, invalid signature/nonce, tampered pending message or metadata, changed model/prompt/request digest, missing witness, revoked session before claim, stale PREPARED heads after one burn, mutation between initial and last chat reads, post-crash replay and full-store rollback counterexamples. Tests trap any actual Requests/model invocation.

Windows and Linux GitHub-hosted CI also rerun #1143–#1133 reference tests and real HTTPS/TLS/loopback transport regressions and existing provider/V1 security suites.

**NO-GO:** no merge to main, no deploy, no real authentication enrollment/signing, keys, paid provider call, actual invoices, cloud/Worker provisioning or owner PC/TPM access. Frozen Core V1 and main untouched. Owner approval required for any real infrastructure, merger, payment or deployment; budget target remains R$200/month.
