# AION — Silent NCryptEnumAlgorithms Signature Capability CI V1

**Scope:** CI-only native/disposable Windows investigation; *no user PC
execution under this PR*, no keys or trust enrollment, no merge/deploy.

## Provenance of the issue
Owner-approved read-only CNG diagnostic on am12 in #1101:
`NCryptOpenStorageProvider` succeeded; both
`NCryptIsAlgSupported(ECDSA_P256)` and
`NCryptIsAlgSupported(ED25519)` returned
`NTE_BAD_FLAGS 0x80090009` with
`NCRYPT_SILENT_FLAG`. The provider handle was released and no private
keys accessed. No claim of TPM hardware absence or algorithm incompatibility.

#1102 tested alternate `dwFlags=0` on disposable CI; it cannot establish
no unintended UI on owner Windows. Do not run that variant on am12.

## Documented alternative
The Microsoft API `NCryptEnumAlgorithms` enumerates names of supported
algorithms, not existing keys, and documents `NCRYPT_SILENT_FLAG` to
request the provider suppress UI. It has distinct supported parameters:
- provider handle from `NCryptOpenStorageProvider`;
- operation mask `NCRYPT_SIGNATURE_OPERATION (0x10)`;
- count and list outputs;
- `NCRYPT_SILENT_FLAG (0x40)`;
- the returned allocated array must be released via
  `NCryptFreeBuffer`; provider handle via `NCryptFreeObject`.

**Neither a flag contract nor a green unit test prove a third-party
provider will obey the silent request on real hardware.** Continue to
require independent physical UI isolation review before user-PC execution.

MS primary sources:
- https://learn.microsoft.com/en-us/windows/win32/api/ncrypt/nf-ncrypt-ncryptenumalgorithms
- https://learn.microsoft.com/en-us/windows/win32/api/ncrypt/ns-ncrypt-ncryptalgorithmname
- https://learn.microsoft.com/en-us/windows/win32/api/ncrypt/nf-ncrypt-ncryptfreebuffer

## Hard limits
- Fixed System32-only `ncrypt.dll` and fixed
  `Microsoft Platform Crypto Provider`;
- no caller-supplied DLL, path, provider, class, algorithm or flags;
- `NCryptEnumAlgorithms` is used instead of `NCryptEnumKeys`;
  no keys created, opened, queried, enumerated, signed, exported;
- no fallback to `dwFlags=0` after `NTE_BAD_FLAGS`;
- class = NCRYPT_SIGNATURE_OPERATION only, count <= 64,
  bounded ASCII algorithm names, no unknown names in output;
- requested suppress UI with documented `NCRYPT_SILENT_FLAG`,
  fail-closed on NTE_BAD_FLAGS / NTE_SILENT_CONTEXT / all other errors;
- check buffer + provider handle cleanup before candidate observation;
- a malformed returned provider structure in Python ctypes could still
  crash a CI runner; this is not proof of arbitrary vendor memory safety;
- ephemeral Windows GitHub pull_request runner only, on PR workflow.
  Environment variables are NOT secure physical machine attestation;
- Linux synthetic fake CNG unit tests and Windows native tests;
- no file/registry write, network, TPM modification, privilege elevation,
  trust-anchor provisioning, deployment or installer action.

## Semantic ceiling
`SILENT_SIGNATURE_ALGORITHMS_LISTED_UNTRUSTED` only means the provider
listed algorithm names within the narrow diagnostic. No TPM, owner, key
custody, non-exportability, key provisionability, antirollback or physical
isolation is proven by that observation. A `NOT_LISTED` result is
specific to this provider enumeration, not a global Windows absence claim.

The output always keeps these false:
`actual_no_ui_physically_verified`,
`owner_pc_execution_authorized_by_code`,
`independently_attested_provider_identity`,
`tpm_presence_verified`,
`tpm_ed25519_key_custody_verified`,
`p256_tpm_key_custody_verified`,
`private_key_created/opened/enumerated/enrolled`,
`host_security_state_modified`,
`physical_attestation_verified`, `network_deny_verified`,
`installer_authorized`, `build_authorized`,
`deploy_authorized`, `safe_to_resume`.

#1049 12/12 independently measured physical sandbox gates and #1087 16/16
network deny surfaces remain incomplete. Installer BLOCKED.
