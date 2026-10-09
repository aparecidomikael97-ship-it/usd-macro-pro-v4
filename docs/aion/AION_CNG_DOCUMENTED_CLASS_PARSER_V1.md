# AION CNG documented interface class acceptance — V1 (CI-only)

## Verified owner Windows outcome (08 October 2026)
One separately approved physical `am12` silent signature algorithm enumeration
was executed with #1105 pinned HEAD `a52338709af95f594676b0e2f910612ec74de7e2`.

Native NCryptOpenStorageProvider and NCryptEnumAlgorithms returned SUCCESS.
Five algorithm records were supplied. NCryptFreeBuffer and NCryptFreeObject
returned SUCCESS. The application parser rejected the list with
`SILENT_ENUM_INVALID_RESULT / SIGNATURE_CLASS_MISMATCH`.

**No specific returned class was disclosed or proven.** The rejection
does NOT prove ECDSA_P256/Ed25519 absence, TPM absence, or any actual
hardware key custody.

## Documentation-based candidate correction
Microsoft's `NCryptAlgorithmName` struct documents three possible
`dwClass` fields:
- `0x00000003` — NCRYPT_ASYMMETRIC_ENCRYPTION_INTERFACE
- `0x00000004` — NCRYPT_SECRET_AGREEMENT_INTERFACE
- `0x00000005` — NCRYPT_SIGNATURE_INTERFACE

Separately, `dwAlgOperations` is a bitmap; `0x00000010` represents
NCRYPT_SIGNATURE_OPERATION and may be combined with other operations.

Reference: https://learn.microsoft.com/en-us/windows/win32/api/ncrypt/ns-ncrypt-ncryptalgorithmname

The prior parser required **every** returned `dwClass == 5`. This was
more restrictive than the documented set and could reject a valid
algorithm that has both asymmetric encryption and signing capabilities.

New candidate permits only `dwClass in {3,4,5}`, still requiring
`dwAlgOperations & 0x10 != 0` on each record. All other hardening
remains (type check, bounded algorithm list ≤64, bounded allowed name
syntax, uniqueness, no unknown names emitted, fail-closed if malformed,
free algorithm buffer and provider handle). This does not unconditionally
declare any algorithm supported; only sanitized listed/not-listed
results from an eligible real observation would be possible.

## CI scope and evidence limitation
- Pure Python parser improvement; no new native APIs, provider, flag,
  registry, keys, hardware attestation or physical host changes.
- Original #1103 silent enum tests, #1104 owner opt-in tests, #1105
  parser category tests and new class/bit flag adversarial tests all
  run on ephemeral GitHub Windows/Linux CI.
- Original tests that treated class 3 as invalid were updated to use
  an actually undocumented class, 7.
- **No owner-PC probe is executed in this PR.** A further physical
  query requires new explicit owner authorization after CI passes.
- Allowing class 3 or 4 is a candidate interpretation based on
  documented structure. It **does not establish** which class caused
  am12's earlier rejection; no raw class value was stored.

## Maximum trust
`SILENT_SIGNATURE_ALGORITHMS_LISTED_UNTRUSTED`, with actual no-UI,
TPM custody, private-key provisionability/non-exportability, owner
identity, protected trust anchor, physical sandbox controls, network
denial, installer/build/deploy all unproven and unauthorized.

#1049 12/12 physical sandbox tests and #1087 16/16 physical network
deny surfaces remain incomplete; installer BLOCKED; no key enrollment,
merge to main, deploy or cost.
