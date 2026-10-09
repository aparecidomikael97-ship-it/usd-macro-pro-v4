# AION CNG Zero-Flags Feasibility — CI-Only V1

## Reason
On 08/10/2026, an expressly owner-authorized native read-only #1101
diagnostic on am12 opened the Microsoft Platform Crypto Provider, but both
`ECDSA_P256` and `ED25519` queries with `NCRYPT_SILENT_FLAG=0x40`
returned `0x80090009 / NTE_BAD_FLAGS`. This was conclusively a *flag
status* from the provider, but not a proof of TPM absence or algorithm
incompatibility.

Microsoft's documented `NCryptIsAlgSupported` contract accepts
`dwFlags=0` OR `NCRYPT_SILENT_FLAG`. Crucially, only the latter
explicitly requests that the provider not show user interface.
https://learn.microsoft.com/en-us/windows/win32/api/ncrypt/nf-ncrypt-ncryptisalgsupported

## Risk decision: DO NOT DEPLOY TO USER WINDOWS

Calling NCryptIsAlgSupported with `dwFlags=0` is a DIFFERENT physical
interaction scope. It **may permit provider UI** or require UI in
circumstances that silent mode would have failed closed. We cannot guarantee
a noninteractive outcome on am12 from GitHub tests, API docs or a static
source review alone.

**As a result, this PR is not cleared for physical am12 execution.**
The permission to proceed with design/review does not waive the user's
requirement to prevent unwanted interactions.

### Narrow CI-only experimental implementation
- Fixed System32-only `ncrypt.dll` loader from #1100;
- fixed Microsoft Platform Crypto Provider;
- fixed two algorithm identifiers;
- exactly these three native calls:
  `NCryptOpenStorageProvider`, `NCryptIsAlgSupported` (`dwFlags=0`),
  `NCryptFreeObject`;
- no key enumeration/create/open/import/export/sign or PIN/UI automation;
- no registry, TPM/ACL/WFP, network, install, write or deployment action;
- fail-closed errors, 32-bit sanitized return codes, handle free;
- explicit *disposable GitHub Windows pull_request runner* guard (a
  convenience guard, NOT secure machine attestation: env vars are spoofable).

A GitHub-hosted ephemeral runner cannot establish safety for owner hardware
and can be unavailable for TPM queries. CI calls can time out; a timeout is
a resource limit, not a proof of silent UI.

### Unconditional output
- `zero_flags_may_allow_provider_ui=true`
- `ui_suppression_verified=false`
- `owner_pc_execution_authorized_by_code=false`
- `physical_host_safety_verified=false`
- all key custody/provisionability/TPM/physical/network/installer/build/deploy/
  safe_to_resume/security-state flags **false**.

Even when algorithm status = ADVERTISED in CI, the maximum state is
`ZERO_FLAGS_DISPOSABLE_CI_OBSERVATION_UNTRUSTED`.

## Next safe decision
Given the UI caveat, do not run `dwFlags=0` on am12 under the
original no-unwanted-interactions constraint. Options to review later:
1. Find a provider-specific, *documented UI-suppressed* read-only
   capability query which does NOT create, open or enumerate private keys.
2. Build/test an operating-system-enforced, independently audited
   noninteractive diagnostic environment with a bounded lifetime and
   no possible user UI; do not assume an unattended console is proof.
3. If such controls cannot be proven, keep the algorithm status
   unresolved and choose independent Ed25519 custody architecture.

Any new physical diagnostic involving changed interactions needs its
own narrowly documented permission. Any real key/enrollment/security-state
mutation always requires a separate explicit owner authorization.

Prior GitHub-only #1101 status `0x80090030 NTE_DEVICE_NOT_READY`
is on a disposable runner and MUST NOT be projected onto am12.

No owner Windows execution performed by this PR. Installer BLOCKED.
