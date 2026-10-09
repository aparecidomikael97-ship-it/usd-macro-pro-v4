# AION Windows — Dual-Root Custody and Host Binding Architecture V1

**Status: PREPARE / architecture review only. This is NOT hardware attestation,
real key custody, authorization to install, or approval for real provisioning.**

## Observed owner device input, 08 October 2026
Physical HUMAN_OWNER-approved read-only observation on Windows `am12`,
pinned Draft PR #1107 HEAD `e2846ffa1f996895b803274db6b1678a53bac801`:

- The `Microsoft Platform Crypto Provider` opened successfully.
- `NCryptEnumAlgorithms(NCRYPT_SIGNATURE_OPERATION, NCRYPT_SILENT_FLAG)`
  succeeded and returned 5 validated algorithm names.
- `ECDSA_P256 = LISTED` and `ED25519 = NOT_LISTED` **for this KSP**.
- Both allocated result buffer and provider handle were released.
- An unsigned, nonce-correlated SHA-256 observation receipt was self-
  consistent, NOT independently signed or physically attested.
- No key created, opened, enumerated, enrolled, used for signing or
  shown to be TPM-backed. No protected HKLM anchor provisioned.
- No user device modifications, install, merge or deploy.

## Chosen design to review: two independent roles, NEVER an algorithm switch

**Owner/collector identity — Ed25519**, kept **external to the Platform
Crypto Provider**, by a **separately secured independent custodian**.
This is the existing Ed25519 trust-contract role. Its custody (hardware,
remote or other) is NOT YET SELECTED OR VERIFIED. Require independent
public-key pinning, key rotation/revocation, provenance, separation of
duties and independent verifier.

**Host/device binding — ECDSA P-256**, as a *separate optional binding
role* subject to hardware origin and key non-exportability proof.
A listing of `ECDSA_P256` from the Platform KSP is *not proof of a TPM
P-256 private key, key generation/provisionability, attestable device
identity, policy isolation or anti-rollback*. No key exists from this
work.

**Never silently convert Ed25519 approvals to ECDSA or RSA.**
A real cross-binding verifier would require ALL independent signatures,
role-specific keys, domain separation, owner policy identity, an
independently attested host-binding key, collector hash, fresh nonce,
monotonic policy generation and revocation checks. When any check fails,
the result remains BLOCKED; optional P-256 cannot become an authority
substitute for required HUMAN_OWNER Ed25519 decisions.

## Documented Microsoft attestation limitation

Microsoft documents the Platform Crypto Provider's TPM-backed key
protection capabilities, but also explains why the provider name alone
does not prove a key is TPM protected. The enterprise CA TPM-key-
attestation workflow documented for certificate requests works with
**RSA only**; it is NOT a ready P-256 attestation mechanism.

No claims of `TPM_P256_ATTESTED` may be issued by inferring P-256
support from a provider name, a successful algorithm enumeration,
an ECDSA signature, the unsigned challenge receipt, or an RSA-only
certificate-template path.

Research a separate **cryptographically independently verifiable,
P-256-capable TPM attestation design** and test its actual platform,
EK/AK, policy and verifier support *before* approving any provisioning.
If impossible at the time, retain Ed25519 independent custody and
leave the P-256 host binding **UNVERIFIED/UNAVAILABLE**. A potential
future RSA attestation key is an additional role with its own threat
model and owner approval; it is never a silent replacement for P-256
or Ed25519.

Official reference:
- https://learn.microsoft.com/en-us/windows/security/hardware-security/tpm/how-windows-uses-the-tpm
- https://learn.microsoft.com/en-us/windows/win32/seccertenroll/cng-key-storage-providers
- https://learn.microsoft.com/en-us/windows-server/identity/ad-ds/manage/component-updates/tpm-key-attestation

## Candidate canonical challenge transcript — NOT AN ACTUAL SIGNATURE

`build_unsigned_dual_root_transcript_draft()` produces deterministic
canonical JSON for exactly:
- owner Ed25519 **public** key fingerprint,
- host P-256 **public** key fingerprint,
- collector binary SHA-256, owner policy SHA-256,
- caller-supplied 256-bit public challenge nonce,
- policy generation integer in a bounded range,
- domain-bound protocol schema/purpose.

The resulting SHA-256 digest is **untrusted, unsigned and replayable**.
It must not be accepted as Ed25519 verification, device signature,
TPM attestation, nonce uniqueness, trust anchor proof or install permit.
The draft values are public-key *fingerprint placeholders*; the code
contains no cryptographic private key, sign API, native OS calls,
counter storage or hardware probing.

Before implementing a real protocol, require pinned public-key formats,
curve and signature encoding validation, independent signature
verification libraries and test vectors, owner-approved secure challenge
issuance and spent-nonce ledger, atomic durable monotonic generation,
revocation and rollback resistance, verified collector measurement
against a reviewed release manifest, authenticated device attestation,
and hardened credential/custodian lifecycle.

## Required physical go/no-go stages, all separate

1. PREPARE: architectural contract, threat model and CI synthetic
   adversarial tests — THIS PR ONLY.
2. REVIEW: independent Ed25519 key custodian, no actual key creation.
3. DESIGN: independently verifiable P-256-capable TPM attestation
   method, no assumptions from Windows algorithm list.
4. EXPLICIT HUMAN_OWNER APPROVAL: separate operation list for
   enrolling/creating real keys and changing machine policy.
5. PHYSICAL WITNESS: independently validate host KSP, key properties,
   non-exportability, signature challenge, custodian independence,
   nonce replay and durable antirollback — results attributable to
   a specific machine with independent evidence.
6. FULL SAFETY CERTIFICATION: separately complete #1049 physical
   sandbox **12/12** requirements and #1087 network deny **16/16**
   surfaces; do not count synthetic CI results as physical proofs.
7. OWNER SIGNED RELEASE/ENROLLMENT DECISION: explicit, separately
   scoped action signed and verified, never implicit from `vamos lá`.
8. Only then consider installer build/deploy with a new owner approval,
   release manifest, trusted root, isolated rollback and audit receipts.

## Current hard denial
Both plan outputs permanently assert:
- no actual Ed25519 signing/verification or private-key custody,
- no P-256 key creation or TPM attestation/non-exportability,
- no P-256 challenge signature, EK/AK chain, software-provider
  substitution acceptance or RSA-to-P256 attestation leap,
- no runtime cross-binding implementation or independent authority,
- no durable nonce ledger, protected host anchor, antirollback,
- no 12/12 physical sandbox, no 16/16 physical network deny,
- no key enrollment, collector launch, installer, build, deploy,
  `safe_to_resume` or OS security changes.

Infrastructure spend: **0**. Branch is Draft. **No owner-PC query,
key creation, machine mutation, merge or deploy in this work.**
