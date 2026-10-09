# AION NCrypt Silent Enumeration Sanitized Parser Diagnostics V1 — CI ONLY

Physical owner Windows `am12` was queried **once** in the owner-approved
#1104 CNG silent-readonly probe, 08/10/2026:
- NCryptOpenStorageProvider: 0x00000000 SUCCESS
- NCryptEnumAlgorithms(SIGNATURE_OPERATION, NCRYPT_SILENT_FLAG):
  0x00000000 SUCCESS
- NCryptFreeBuffer: 0x00000000 SUCCESS
- NCryptFreeObject: 0x00000000 SUCCESS
- Parser result: BLOCKED / SILENT_ENUM_INVALID_RESULT
- No key created/opened/enumerated/enrolled or host mutation.

The original parser rejected a provider record but collapsed malformed
class, algorithm name, operation flag, duplicate record and native decoding
exception into one generic reason. It did not retain an algorithm count
when a decoded record failed. There is **no justified claim** that a
specific failure subtype caused the real am12 result.

## Pure diagnostic improvement
Refines only the existing #1103 parser on a Draft branch:
- Adds `enumeration_failure_category` from fixed string set:
  `ALGORITHM_NAME_SHAPE_INVALID`, `SIGNATURE_CLASS_MISMATCH`,
  `SIGNATURE_OPERATION_MISMATCH`, `DUPLICATE_ALGORITHM_NAME`,
  `RECORD_TUPLE_INVALID`, `EXCESSIVE_OR_MALFORMED_RECORD_COUNT`,
  `NULL_ALGORITHM_ARRAY`,
  `NATIVE_POINTER_OR_DECODING_EXCEPTION`.
- Leaves the canonical broad fail-closed `state=BLOCKED`,
  `reason=SILENT_ENUM_INVALID_RESULT` unchanged for invalid records.
- Stores numeric record count only for bounded, non-null returned arrays.
- Does not return unknown provider algorithm names, raw pointers, raw
  decoded strings, TPM state, owner identity or private material.
- Does not relax type/class/operation/name/count validation.
- Keeps `NCRYPT_SILENT_FLAG` and exact fixed provider selection.
- CI test matrix for bad records, native errors and resource cleanup,
  plus the original #1103 and owner #1104 regression suites.

## Physical limit
NO second CNG query is performed on am12 in this PR. No real support
claim for ECDSA_P256 or ED25519 is possible until a separately owner-
authorized, reviewed, safe observation using this diagnostic version.

All physical attestation, TPM/key custody, nonexportability, owner trust
anchor, network deny, installer/build/deploy/launch flags remain FALSE.
No merge, deploy, real keys, Registry/Windows policy changes or costs.
