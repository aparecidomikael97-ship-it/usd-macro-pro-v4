# AION Windows Trust Anchor — Crypto Provider Compatibility V1

**Draft. Design review only. No real key, trust anchor, deployment, or
physical Windows change.**

## Verified physical finding, 8 October 2026
The owner-authorized exact-source read-only #1098 diagnostic on device am12
returned `BLOCKED / HOST_ANCHOR_ABSENT` at the fixed prospective HKLM
AION anchor. This observation covers **that one key only**, not whether the
system has TPM, Windows Hello, Secure Boot or other protection. No real
key or root exists at that path based on the observation. This document
does not assert a successful independent physical certification.

## Architecture gap
The currently drafted #1093/#1095/#1096 identity and collector signing
contracts use **Ed25519**.

Microsoft's Platform Crypto Provider is a CNG key-storage provider using
TPM-protected key operations. CNG support for a specific algorithm MUST be
checked per provider and on actual hardware: the existence of a TPM,
Windows Hello, or Platform Crypto Provider is **NOT PROOF** that an Ed25519
private key is native, nonexportable, TPM protected or attested. Do not
silently substitute RSA/ECDSA for an Ed25519 signing contract.

Microsoft documentation references:
- https://learn.microsoft.com/en-us/windows/security/hardware-security/tpm/how-windows-uses-the-tpm
- https://learn.microsoft.com/en-us/windows/win32/seccertenroll/cng-key-storage-providers
- https://learn.microsoft.com/en-us/windows/win32/api/winreg/nf-winreg-reggetkeysecurity

## REVIEW-ONLY options

### Option A — independent Ed25519 signing custodian
Owner registry and collector keep the #1093/#1096 Ed25519 verification
contracts. The physical Ed25519 private key must be enrolled and
secured by a trusted mechanism **separate from the collector process**,
with independently verifiable provenance, owner/witness consent, antirollback
and revocation. This option **does not** claim that the key is TPM-protected.
Still requires an explicit HUMAN_OWNER approval and trusted host anchor.

### Option B — Windows TPM P-256 host-binding + separate Ed25519 collector
A hardware-bound ECDSA P-256 key can be considered for **host-device
binding** after native provider and key-attestation proof. That key
cannot be confused with the collector Ed25519 root. A separate
cross-algorithm, domain-separated challenge binding between the independent
Ed25519 collector signature and TPM host signature must be designed,
security reviewed, implemented, negatively tested and attested. Neither
the bridge nor the production keys exist in this PR.

### Prohibited shortcut
`DIRECT_TPM_ED25519_UNVERIFIED` is always rejected, not because every
possible future provider must lack Ed25519, but because there is **no
verified proof of this capability** in the current AION architecture.

## Physical and operational gates still required
1. Owner-approved, reviewed custody model with independent witness
   and clear owner authentication; no implicit approval.
2. Independent read-only physical provider capabilities and algorithm
   enumeration on authorized Windows, with provenance recorded.
3. Native TPM key-attestation proof where hardware claim is needed,
   non-exportability and signer identity validated, not a checkbox.
4. Independently protected anchor against user-mode/admin tampering
   and offline rollback; HKLM ACL and readback alone cannot prove this.
5. Exact #1097 protected policy binding, protected epoch and recovery design.
6. #1049 12/12 physical sandbox measurements and #1087 16/16 network
   denial surfaces, all under a separate authorized physical test plan.

## Code execution / truth ceiling
Pure Python evaluation of a canonical proposal and the #1098 **untrusted**
anchor observation. No registry, disk, network, privilege, TPM, CNG, key
signing, OS mutation or installer operations.

Maximum state:
`CRYPTO_ARCHITECTURE_REVIEW_CANDIDATE_UNTRUSTED`

Never true: TPM/Ed25519 compatibility verified; key custody attested;
actual root enrolled; protected host anchor verified; physical attestation;
safe-to-resume; installer/build/deploy authorized; Windows security-state
modified. The proposal is NOT a usable installation procedure.

No script should create AION keys or register a new trusted authority
without a future, separate, explicit owner approval.
