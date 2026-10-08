# AION Native Windows Platform CNG KSP Read-Only Capability V1

**Only for GitHub CI and future separately authorized physical owner device
diagnostics. No key provisioning, installation, profile, ACL, TPM or system
security-state changes.**

## Reason
The currently reviewed collector identity chain uses Ed25519. A TPM and
Microsoft Platform Crypto Provider (KSP) are not proof that an Ed25519 signing
key can be created, protected or attested there.

## Strict native API inventory
- Loads **ncrypt.dll from System32-only** (LOAD_LIBRARY_SEARCH_SYSTEM32).
- Fixed provider: `Microsoft Platform Crypto Provider`.
- Native functions: `NCryptOpenStorageProvider` with flags zero;
  `NCryptIsAlgSupported` with `NCRYPT_SILENT_FLAG` for only
  `ECDSA_P256` and `ED25519`; `NCryptFreeObject` for handle cleanup.
- No `NCryptCreatePersistedKey`, `NCryptOpenKey`, `NCryptEnumKeys`,
  `NCryptFinalizeKey`, `NCryptExportKey`, `NCryptSetProperty`,
  `NCryptSignHash` or private-key access.
- A fresh 256-bit nonce correlates observation only; it does not certify
  device, TPM ownership or authenticity.
- Only 0/ERROR_SUCCESS maps to `ADVERTISED`; 0x80090029
  (NTE_NOT_SUPPORTED) maps to `NOT_SUPPORTED`; all other errors
  map to `INCONCLUSIVE` and BLOCKED.
- If the provider cannot be opened, cannot query both algorithms or handle
  release is unconfirmed, returns BLOCKED.
- Outputs only fixed algorithm labels/status and non-privileged challenge
  binding; never user identifiers, TPM state, key names, raw key material
  or private registry content.

## Maximum semantic result
`PLATFORM_KSP_ALGORITHM_ADVERTISEMENT_UNTRUSTED`

Even if the provider **advertises** `ED25519`, that does not prove key
creation, key attributes, non-exportability, hardware-protected custody,
TPM attestation, collection process independence, key presence, owner identity
or authority to enroll anything. If it reports `NOT_SUPPORTED`, do not
claim that all providers/Windows builds lack Ed25519; only this provider
and this particular query returned NTE_NOT_SUPPORTED.

A GitHub-hosted Windows runner is not the owner's Windows computer.
Its presence/absence of the provider cannot establish owner TPM capabilities.

## All authority flags remain false
Native provider identity attested, TPM present/ownership verified,
TPM-backed key custody, P-256 or Ed25519 key provisionability,
nonexportability, private key created/opened/enrolled, protected anchor,
antirollback, independent physical #1049 12/12, network #1087 16/16,
collector resume, installer/build/deploy, and host system mutation.

## Reviewed Microsoft API contracts
- https://learn.microsoft.com/en-us/windows/win32/api/ncrypt/nf-ncrypt-ncryptopenstorageprovider
- https://learn.microsoft.com/en-us/windows/win32/api/ncrypt/nf-ncrypt-ncryptisalgsupported
- https://learn.microsoft.com/en-us/windows/win32/api/ncrypt/nf-ncrypt-ncryptfreeobject
- https://learn.microsoft.com/en-us/windows/win32/seccertenroll/cng-key-storage-providers

## Future owner device step
Do not execute the probe on am12 or any owner computer without **explicit
owner authorization for this exact native provider query**. Separate approval
is mandatory for creating any keys, inspecting protected key containers,
changing HKLM, hardware attestation, ACL, firewall, sandbox or installer.
