# AION owner-approved Windows silent CNG algorithm observation V1

## Scope and authorization
On 08 October 2026, the owner expressly authorized an
**on-device, read-only, silent signature-algorithm capability probe**
after #1103 validation. Approval does NOT extend to OS settings, key
provisioning, private-key enumeration, TPM configuration, Windows Hello,
HKLM/WFP/ACL changes, unattended UI, build/install/deploy or merge.

The previously authorized #1101 physical probe on am12 returned
NTE_BAD_FLAGS (0x80090009) for both ECDSA_P256 and ED25519 when
NCryptIsAlgSupported was called with NCRYPT_SILENT_FLAG. The #1102
alternative dwFlags=0 is NOT suitable for the agreed no-UI constraint.

## Why new wrapper
#1103 is deliberately guarded to disposable GitHub pull-request CI and
must NOT be made runnable on owner Windows by spoofing GitHub environment
variables. This branch refactors its fixed native implementation into an
internal shared core, retaining the original CI-only guard unchanged,
and adds an independent explicit owner-scope gate. Owner approval must
also be checked outside the program at the device connector boundary;
a Python boolean is NOT proof of HUMAN_OWNER identity.

## Only physical APIs allowed
Using fixed System32-only ncrypt.dll:
1. NCryptOpenStorageProvider('Microsoft Platform Crypto Provider', 0)
2. NCryptEnumAlgorithms(NCRYPT_SIGNATURE_OPERATION=0x10,
   NCRYPT_SILENT_FLAG=0x40)
3. NCryptFreeBuffer (if list allocated)
4. NCryptFreeObject (provider handle cleanup)

Never call NCryptEnumKeys, CreatePersistedKey, OpenKey, SignHash,
FinalizeKey, SetProperty, EnumStorageProviders or a zero-flags retry.
No user-supplied provider, flags, algorithm name or disk path.

Algorithm names are validated, max 64, output contains only two target
labels: ECDSA_P256 and ED25519 as LISTED/NOT_LISTED/NOT_QUERIED.
Enumerated *algorithm names* are not proof of key provisionability,
TPM-protected private keys, physical TPM status, nonexportability, host
identity, or signed trust anchor.

The NCRYPT_SILENT_FLAG requests the provider not display UI. The code
cannot physically prove a vendor/provider complied. If the request fails
with NTE_BAD_FLAGS or NTE_SILENT_CONTEXT, return BLOCKED: no retry without
silence, no PIN, no UI automation.

## Execution plan
1. Preserve pinned HEAD and exact file blobs in GitHub.
2. Run both earlier #1103 test matrix and new owner-scoped synthetic
   tests on ephemeral Windows and Linux CI runners, plus no OS mutation
   guard. Do not execute owner wrapper physically in CI.
3. Verify remote device **am12** online and confirm selected ID.
4. Execute pinned exact sources via PowerShell here-string to
   `python -I -B -S -` with ephemeral 256-bit challenge. No script written.
5. Emit sanitized state, reason, return-code hex, target name statuses,
   count and cleanup flags only. No raw private material, no system
   identifiers. Check process has finished, and stop if anomalous.
6. Register what was and was not proven. Do NOT enroll root or resume
   installer.

## Security result ceiling
`SILENT_SIGNATURE_ALGORITHMS_LISTED_UNTRUSTED`, even if the provider
responds positively. All proof/authorization flags remain False:
actual_no_ui_physically_verified,
owner_pc_execution_authorized_by_code, key presence or custody,
TPM presence and nonexportability, physical attestation,
network denial, installer/build/deploy/safe_to_resume.

Reference:
https://learn.microsoft.com/en-us/windows/win32/api/ncrypt/nf-ncrypt-ncryptenumalgorithms
https://learn.microsoft.com/en-us/windows/win32/api/ncrypt/nf-ncrypt-ncryptfreebuffer

No merge or production deploy is included here. The AION installer
remains blocked until separate, complete physical certification.
