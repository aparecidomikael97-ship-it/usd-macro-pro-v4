# AION — Dual Ed25519 Owner/Collector Public Signature Bridge V1

**Scope: CI-only experimental integration, no real HUMAN_OWNER/collector
signing keys and NO device, Windows, installer or production enrollment.**

## Completed upstream basis
- #1109 defines three independent conceptual roles and a canonical
  domain-separated public 256-bit challenge transcript.
- #1110 validates the RFC 8032 Ed25519 mathematical public-key
  verifier with official detached signature test vectors.
- #1107 single physical read-only `am12` algorithm enumeration found
  Platform Crypto Provider `ECDSA_P256=LISTED`,
  `ED25519=NOT_LISTED`. No TPM key or signing was attested.

## New bridge (this PR)
`verify_dual_ed25519_public_signatures_untrusted` independently:
1. Validates untrusted three-role proposal format using #1109,
   including claimed owner/collector/host public key SHA-256 fingerprints,
   distinct custodian identifiers, unverified custody status and
   simulated budget ceiling of R$200/month.
2. Recomputes the exact domain-separated #1109 challenge for a given
   caller-provided public 256-bit nonce. Binds it to the policy digest
   and generation, collector binary hash and three role fingerprints.
3. Re-hashes the **caller-supplied** owner/collector Ed25519 public
   keys and checks them against proposal fingerprints. These are not
   verified enrollment pins.
4. Independently verifies, using #1110 Ed25519 public-key API:
   - signature 1 covers the `HUMAN_OWNER_ED25519` intent digest;
   - signature 2 covers the `COLLECTOR_ED25519` intent digest.
   Each role is bound to a distinct algorithm/domain.
5. Rejects tampering, missing/wrong signature, public key swapping,
   role confusion, nonce/policy/generation/collector binary/host
   fingerprint mutation after signature, invalid shapes, duplicate keys,
   self-reported enrollment/TPM claims and custodian identifier reuse.
6. Emits only sanitized status, role digests and the public challenge
   hash, not raw signatures or public-key bytes.

The maximum output is
`DUAL_ED25519_SIGNATURES_MATHEMATICALLY_VALID_UNTRUSTED`.
This means exactly **both supplied signatures are mathematically
consistent with the supplied public keys and freshly recomputed role
intents**. It **DOES NOT** prove that those keys belong to the actual
HUMAN_OWNER or registered collector.

## CI-only key generation disclosure
To test the successful two-signature path (not merely reject invalid
signatures), the *test module only* creates two fresh **ephemeral**
Ed25519 key pairs using `cryptography.Ed25519PrivateKey.generate()`
within disposable GitHub Windows/Linux runner processes. Only their
public bytes are read; private material is never exported to a file,
logged, uploaded, registered, or used on the owner PC. The temporary
signatures cover **synthetic role-intent digests for tests**, not real
AION policy changes. No private-key API or signing function exists in
the production bridge module or #1110 public verifier.

The project retains no disposable test private keys. These simulated
keys are **NOT owner/collector keys** and cannot authorize changes.

## Why successful maths is still NOT an authorization
- Anyone can generate an Ed25519 pair and create a matching untrusted
  self-proposed fingerprint and valid signature; the proposal is not
  a durable enrollment authority.
- Distinct key fingerprints and custodian IDs do NOT prove separate
  real-world custodian identity or hardware isolation.
- The same nonce and signatures can be presented again and pass math:
  **this PR has no durable issued/spent nonce ledger**.
- Generation is an unsigned number in the proposed transcript until a
  protected durable policy counter is validated; **no antirollback**.
- A valid Ed25519 signature by owner and collector does NOT establish
  TPM P-256 origin, EK/AK trust chain, non-exportability, hardware
  antirollback or host attestation.
- The P-256 host role remains an **unverified design placeholder**,
  not a trusted software fallback or a silent replacement for the
  two required Ed25519 signatures.
- #1049 requires independent 12/12 physical sandbox proofs and
  #1087 requires independent 16/16 network deny verification.

## Future secure continuation — not implemented
Independent owner/collector public key **enrollment and trusted pinning**;
external custodian capability and custody evidence; owner-specific
signed approval; independent collector signing custody; validated
P-256 TPM attestation; atomic nonce issuance+consumption and durable
antirollback; revocation and rotation; independent physical sandbox,
firewall and trusted host anchor; verified release manifest and a
separately signed activation decision.

**Hard stops:** every actual owner identity, collector enrollment,
nonce replay, P-256 TPM key proof, #1049, #1087, key creation/enrollment,
collector launch, installer, build, deploy, `safe_to_resume` and
Windows security-state flag stays FALSE in all outputs.

## Source provenance
- RFC 8032: https://www.rfc-editor.org/rfc/rfc8032
- `cryptography` Ed25519 public verify:
  https://cryptography.io/en/latest/hazmat/primitives/asymmetric/ed25519/
- Microsoft RSA-only enterprise CA TPM key attestation:
  https://learn.microsoft.com/en-us/windows-server/identity/ad-ds/manage/component-updates/tpm-key-attestation

No physical `am12` action, key enrollment, platform modification,
merge to main, deploy, or production infrastructure expense.
All edits are Draft PR / disposable GitHub CI only.
