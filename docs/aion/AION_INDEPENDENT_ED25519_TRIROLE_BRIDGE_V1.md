# AION — Independent Ed25519 Custody, Collector Co-Signature and Host P-256 Bridge V1

**Implementation boundary: PREPARE / no cryptographic verification, no real key material,
no owner Windows execution, no merge, no deployment and no installer approval.**

## Why this protocol exists
The last owner-authorized read-only CNG observation (#1107; real Windows
`am12`) enumerated five algorithms for the Microsoft Platform Crypto
Provider and reported:
- `ECDSA_P256: LISTED`;
- `ED25519: NOT_LISTED`;
- provider/buffer release successful;
- a SHA256 correlation receipt consistent with its reported nonce,
  but **unsigned and unauthenticated**.

A provider's algorithm advertisement is neither a real TPM key nor
an attestation of private-key non-exportability. It also says nothing
about Ed25519 support from a different provider or independent device.
The #1108 Draft architectural plan therefore deliberately separates
Ed25519 identity signing from P-256 host binding.

## Important improvement: three roles, not two interchangeable keys
The design now separates **three logical private-key security roles**:

| Role | Algorithm | Purpose | Current state |
|---|---|---|---|
| HUMAN_OWNER | **Ed25519** | Explicit owner approval of sensitive policy and enrollment | Independent custodian not chosen or verified |
| COLLECTOR | **Ed25519** | Separate, independently attributable collector/witness signature | Separate custodian not chosen or verified |
| HOST_BINDING | **ECDSA P-256 / SHA-256** | Optional association with a specific TPM-attested host | Algorithm listed; key/TPM origin not attested |

The HUMAN_OWNER and COLLECTOR **must never share a private key or
custodian trust domain**. A P-256 host signature may not satisfy either
Ed25519 role. A single owner signature may not implicitly fulfill the
collector witness. Likewise, signed software cannot prove TPM origin.

This is a contract decision, not a statement that we have provisioned
three keys. There are **zero new keys** from this implementation.

## External Ed25519 custodian choices to evaluate

- **Owner-held separate signing device**: the owner approval key should
  remain outside the Windows application and local collector's
  administrative trust domain. A device's advertised support for EdDSA
  or FIDO2 must be checked against **exact raw-message/format signing
  requirements**, public-key extraction, challenge semantics, policy
  confirmation, availability, recovery and real user-presence safeguards.
  **Do not assume a generic FIDO2 assertion equals an Ed25519 AION
  approval signature.**
- **Independent managed/remote signer**: require actual Ed25519
  capability, independent access control and owner authorization,
  signed/audited operation attribution, revocation, recovery,
  appropriate data transfer/legal terms and measurable availability.
  **No specific paid provider selected; no external API call made.**
- **Offline owner-controlled signing domain**: viable only once a
  reviewed isolation and secure key lifecycle are demonstrably
  independent of `am12`, with explicit recovery/rotation procedures.
  An ordinary key file on the same PC does not establish independent
  custody.

Collector Ed25519 must have a **different logical key and different
custodian identifier/domain** from owner. Its enrollment remains
PREPARE until real owner-signed approval under the existing #1096
trust-gate chain. Do not reuse a collector-signed event to authorize
collector enrollment or use a self-attested environment variable
as proof of HUMAN_OWNER identity.

## Reusable PREPARE-only machine-readable policy

`review_three_role_custody_design(proposal)` validates only **public
fingerprint placeholders**, role names, allowed custodian-boundary
categories, separately identified domains, policy/collector SHA256
placeholders, generation format and a **hypothetical** monthly cost
estimate between R$0 and R$200.

These values are **claims in an untrusted proposal**, not
cryptographic evidence that those keys exist or are independently
custodied. An accepted review result is at most
`THREE_ROLE_CUSTODY_DESIGN_CANDIDATE_UNTRUSTED` and every
key-creation/proof/installer/deploy flag remains false.

`build_unsigned_three_role_challenge(proposal,nonce)` generates
domain-separated role-intent **message digests** for the two Ed25519
roles and the optional P-256 host role from one canonical JSON
transcript. It contains policy generation, collector and policy
digest placeholders, independent public key fingerprints and a public
256-bit nonce. **It signs nothing**, does not check any signature or
TPM attestation, and does not implement a nonce-spent ledger.
A repeat with the same nonce yields the same digest: not replay-safe.

## Future verifier contract — separate from this PR
A production bridge must fail closed until ALL of the following
requirements are established **by a separately reviewed and
cryptographically independent verifier**, not self-reported booleans:

1. Pin owner Ed25519 public key from a trusted enrollment chain;
   prove the owner signature covers the exact approved purpose.
2. Pin an independently enrolled collector Ed25519 public key from
   a distinct trust domain; verify its signature with an independent
   verifier and reviewed collector binary measurement.
3. Pin a P-256 public key and verify ECDSA signature encoding and
   nonce-specific challenge (not an Ed25519 or RSA substitute).
4. Independently prove that the particular P-256 private key is TPM
   backed and non-exportable, with verifiable EK/AK identity,
   manufacturer trust chain and policy binding.
5. Verify policy and collector digests, per-role signature domains,
   anti-downgrade rules, explicit activation action and key rotation
   / compromise / revocation state.
6. Atomic durable issuance and consumption of challenge nonces;
   monotonic policy generation with rollback protection.
7. Independent protected host policy anchor and full `#1049`
   **12/12 physical sandbox** plus `#1087` **16/16 physical
   network deny** witnesses.
8. Fresh HUMAN_OWNER signed decision **specific** to key creation,
   enrollment or installation; a conversational `vamos lá` is
   not a replacement for critical signed decisions.

**Microsoft enterprise CA TPM key attestation documents RSA-only
support. It cannot be used as unexamined evidence for P-256 TPM origin.**
Either design and independently validate an appropriate P-256 capable
attestation mechanism, or leave optional host binding *unverified*.
A credential provider named "Platform" is not an attestation by itself.

## Security assumptions we REFUSE to turn into facts
- A SHA256 hash is not a digital signature.
- Possession of an unsigned metadata object does not authenticate
  owner, collector, machine or attestation authority.
- Distinct public key fingerprints do not prove distinct private key
  operators. Proposal identifiers are unverified claims.
- Estimated R$0–200/month is an internal architecture guard and
  **not a live quoted price or proof of spend**.
- A provider name, algorithm LISTED and an ECDSA signature cannot
  prove TPM non-exportability, EK binding or anti-rollback.
- Synthetic tests and disposable CI runners cannot certify owner PC
  sandbox/network isolation.

## Required future owner approval gates
**No work in this PR uses the physical device.** Following an
independently verified provider/custody choice, a separate exact
proposal will specify: provider/device, creation/enrollment operation,
key scope, UI/human-presence requirements, non-exportability controls,
cost ceiling, recovery/revocation plan, audit evidence, exit criteria,
no-change rollback, and a dedicated HUMAN_OWNER approval.
Do not create keys or change TPM/Windows/ACL/registry/WFP, even for
"testing", without this explicit new approval.

## Sources
- RFC 8032 Ed25519/EdDSA definitions and signature-context guidance:
  https://www.rfc-editor.org/rfc/rfc8032
- NIST SP 800-57 Part 1 Rev. 5 key lifecycle and custody principles:
  https://csrc.nist.gov/pubs/sp/800/57/pt1/r5/final
- NIST SP 800-57 Part 3 Rev. 1 key purpose separation:
  https://csrc.nist.gov/pubs/sp/800/57/pt3/r1/final
- Microsoft enterprise CA TPM key attestation (RSA-only):
  https://learn.microsoft.com/en-us/windows-server/identity/ad-ds/manage/component-updates/tpm-key-attestation

**Final state for this PR: Draft, CI-only, key creation/attestation,
collector launch, installer/build/deploy, and safe-to-resume BLOCKED.**
