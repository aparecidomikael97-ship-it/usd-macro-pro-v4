# AION CNG Status-Code Diagnostic V2 — PREPARE / CI ONLY

## Why this was added
The owner-authorized native read-only CNG query on am12 with pinned #1100
source (08/10/2026) returned:
- Microsoft Platform Crypto Provider: opened = true, released = true
- ECDSA_P256: INCONCLUSIVE
- ED25519: INCONCLUSIVE
- result BLOCKED / ALGORITHM_QUERY_INCONCLUSIVE
- No key opened/created/enrolled; no Windows trust mutation.

The original #1100 status normalization recognized only SUCCESS and
NTE_NOT_SUPPORTED; every other SECURITY_STATUS was collapsed. That result
cannot identify whether flags, handles, parameters, provider initialization
or another native error caused the inconclusive report.

## Scoped refinement
Keep the same three read-only native APIs from #1100:
NCryptOpenStorageProvider, NCryptIsAlgSupported (ECDSA_P256 / ED25519,
NCRYPT_SILENT_FLAG), NCryptFreeObject. Use exactly the existing System32-only
ncrypt.dll loader. No reconfiguration, no extra query or key action.

New result includes sanitized, bounded **32-bit numeric status codes**
in 0xXXXXXXXX hexadecimal, with recognized reasons:
- NTE_BAD_FLAGS: 0x80090009
- NTE_INVALID_HANDLE: 0x80090026
- NTE_INVALID_PARAMETER: 0x80090027
- NTE_SILENT_CONTEXT: 0x80090022
- NTE_UI_REQUIRED: 0x8009002E
- NTE_NOT_SUPPORTED: 0x80090029
- NTE_PERM: 0x80090010
- NTE_BAD_ALGID: 0x80090008
- NTE_FAIL: 0x80090020
- NTE_INTERNAL_ERROR: 0x8009002D
- Any other code: UNKNOWN_NATIVE_STATUS / INCONCLUSIVE.

Normalizes signed and unsigned SECURITY_STATUS; malformed types fail closed.
Even an advertised algorithm leaves TPM/key custody/antirollback/physical
attestation/installer/build/deploy and resume false. Handle release must be
confirmed before any successful diagnostic output.

## Verification boundary
No new physical query was run on the HUMAN_OWNER computer for this V2.
The proposed code uses synthetic errors in CI and an optional one-time native
read-only query on **disposable Windows GitHub runner only**. The GitHub runner
cannot establish owner-device capabilities.

A future physical V2 query on am12 needs **separate explicit authorization**
because it returns a more detailed native error code and is new source.

Microsoft docs:
https://learn.microsoft.com/en-us/windows/win32/api/ncrypt/nf-ncrypt-ncryptisalgsupported
https://learn.microsoft.com/pt-br/windows/win32/com/com-error-codes-4

No key generation, registry writes, ACL/TPM policy changes, deployment,
installation, merge to main, or spend.
