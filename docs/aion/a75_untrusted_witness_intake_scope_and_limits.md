# A75 — F1/T1 source witness intake: strict syntax, ZERO operational authority

2026-10-14. **LAB-ONLY / DRAFT / HARD NO-GO.**

## Independently queried GitHub identifiers (snapshot, NOT F1/T1)
- GitHub numeric repository ID **1366962269**; numeric owner ID **328188988**; full name `aparecidomikael97-ship-it/usd-macro-pro-v4`
- Branch `atlasquant-runtime`, observed HEAD `b43056d8df0cf3e39ae1575f997086175f5696d5` (observed at one GET; must be read again before future decisions)
- Path `dados/aion/checkpoint_master.json`, Git blob on that HEAD `f8f6ed149720308a00482c09b07bfeb268bc5bef`, size 42343 bytes
- GitHub reported `protected=false` for `atlasquant-runtime` (also for `main`). No GitHub branch safety has been changed. GitHub GET and self-hash do NOT constitute an independent witness.

## Purpose of A75
The pure Python `inspect_untrusted_witness_claim` function checks whether a caller-supplied witness-shaped envelope is **syntactically consistent** with a caller-supplied expected tuple/HEAD observation/locally-known high-water. All inputs are UNTRUSTED. It can report mismatches but **ALWAYS returns BLOCKED**, even if all fields are correctly typed, all identifiers match, and a caller claims a signature/issuer. It does NOT verify any cryptographic signature, create/use/revoke keys, contact GitHub, query a real witness, persist or consume nonces, read trusted clock, or open permission paths.

Rejects: missing/extra/forged trust flags; bad repo/owner IDs (including bool-as-int); wrong tenant/workspace/branch/path; SHA/Blob mismatch; bad timestamp/TTL/nonce; missing or inconsistent predecessor; counter gaps, negative, boolean, unbounded, locally detected replay/rollback. Correct formatting reports `local_format_consistent=True` ONLY, never trust.

Security boundaries: `claim_signature_verified=False`, `external_custody_verified=False`, `fresh_github_head_independently_verified=False`, `monotonic_high_water_independently_verified=False`, `replay_prevented_independently=False`, `source_authenticity_verified=False`, `independent_witness_verified=False`, `external_activation_allowed=False`, `worker_execution_allowed=False`. No caller-supplied expected scope or high-water becomes authoritative.

## What A75 does NOT solve
There is **no** external custody, externally approved signer/trust anchor, real signed proof, monotic high-water, authenticated current-head readback, fork/rollback-resistant witness, expiry tied to trusted clock, nonce atomic consumption, cross-tenant enrollment, owner biometrics/H0 or independent producer receipt. A single GitHub branch query / content SHA / signature on mutable local state is insufficient. `atlasquant_aion_authority_verifier.py` with a local trust-root registry and a local SQLite nonce registry does NOT become F1/T1 by reuse alone.

## Required implementation beyond A75 (explicit approval first)
1. Choose separate custodial account/provider/admin boundaries and immutable public-key enrollment out of the mutable runtime; verify costs/terms, outage/fallback, PII.
2. Outside source observer GET verified repository numeric ID/owner+branch head at commit, tree and checkpoint blob; record issuance window and link to fresh nonce.
3. Atomic external monotonic high-water per tenant+workspace+resource+epoch, with durable append-only receipt and independent readback; reject restore/fork/replay.
4. Cryptographically verify out-of-band pinned signing key and exact canonical envelope; independently re-GET source at execution boundary and handle TOCTOU.
5. Wire witness to the pre-CAS/Worker gate ONLY after red-team/CI, hardware owner F2, external producer and original historical A12/A16. Never open positive path based on the LAB intake schema itself.

No account signup, payments, TPM, Worker, config changes, merges, production data updates, deploy or original tests modified. Legacy Quality/Security remain RED, no A75 full-suite claim until run on exact SHA.

## A80 LAB amendment — signature encoding is NOT cryptographic validity

The A75 diagnostic originally accepted any bounded nonempty `signature_b64` text as locally format-consistent, even `NOT_A_VERIFIED_CRYPTOGRAPHIC_SIGNATURE` (not Base64). A80 now requires **canonical standard RFC4648 Base64** with strict ASCII decoding, no whitespace, valid padding/pad bits, nonempty decoded bytes and a bounded encoded text field. Invalid text adds the diagnostic blocker `WITNESS_SIGNATURE_BASE64_INVALID`; every output remains `BLOCKED`.

The A75 fixture's signature field is now the canonical Base64 encoding of 64 **zero bytes**. It is a deliberately **unsigned synthetic placeholder**, not produced by any signing key, and neither the field's 64 decoded bytes nor its encoding says anything about actual algorithm, key custody, issuer enrollment, freshness, owner identity, trusted time, replay prevention or external monotonicity. No signature verification, key, network, runtime authorization, Worker or external actor was added. The existing 12 tests remain and four additional A80 adversarial cases were added to the same test module. This is a diagnostic truthfulness correction, **not F1/T1 implementation**.
