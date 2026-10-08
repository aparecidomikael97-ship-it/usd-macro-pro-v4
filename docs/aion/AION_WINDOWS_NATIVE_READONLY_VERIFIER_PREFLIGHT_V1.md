# AION Windows Native Read-Only Verifier Preflight V1

**Scope:** GitHub-hosted ephemeral Windows runner only; stacked on #1062  
**Mode:** IMPLEMENTATION SAFE / Draft / CI-only / READ-ONLY WINDOWS APIs  
**Date:** 2026-10-08

## Objective

Bridge the gap between #1062's SQLite scratch-disk CAS verification and
real **Windows native observation capability**, while refusing to call
those observations trusted installation evidence or HUMAN_OWNER attestation.

The preflight does not target the owner's workstation or installed AION.
All native measurements are performed only on an ephemeral, hosted Windows
GitHub Actions runner with no production secrets, installer artifacts or
permissions. No application is installed or run.

## Actual Windows read-only APIs, narrow scope

1. **Current CI-process token user SID** via `GetCurrentProcess`,
   `OpenProcessToken(TOKEN_QUERY)`, `GetTokenInformation(TokenUser)`,
   `ConvertSidToStringSidW`; token handle closed after observation.
2. **Owner SID and DACL description** of the existing `RUNNER_TEMP`
   directory via `GetNamedSecurityInfoW` and
   `ConvertSecurityDescriptorToStringSecurityDescriptorW`.
   Security descriptor allocations are released with `LocalFree`.
3. **Presence and hash of the CI Python interpreter binary**, not an AION
   package, app binary, or signed installation manifest.
4. **OS uptime counter** via `GetTickCount64` on the runner. This is
   NOT a signed boot epoch and cannot prove a previous/recent reboot.
5. **Visibility of HKCU Run**, optionally the value name
   `AtlasQuantAION`, using read-only `winreg.OpenKey(KEY_READ)`.
   No registry value data, launch command, path or host identity is returned,
   and no startup entry is created or modified.

Every raw SID, full security descriptor/SDDL, path and user identity stays in
the test process and is never published by these contracts. Only
domain-separated SHA-256 digests, booleans, sanitized statuses and a
synthetic challenge/policy/source binding appear in the observation.
These digests are pseudonymous/correlatable and must **not** be logged
or treated as anonymization. Never use unsalted SID hashes as broad
public identifiers.

## Review gate

The review recomputes the observation envelope digest, checks exact
challenge, policy and source identifiers, verifies Windows CI scope, validates
mandatory digest and native measurement shape, and rejects any attempt
to assert trusted owner identity, installed AION, physical boot transition,
running/healthy AION, production write, startup correctness or trusted
independent attestation.

It yields at most:
`READY_FOR_NATIVE_WINDOWS_READONLY_SECURITY_REVIEW`.

That status means these **read-only CI API probes** and the proof-envelope
contracts can be reviewed. It says nothing about an owner-PC installation
being safe or ready.

## Adversarial checks

- Wrong/missing challenge, source, policy or hashed evidence.
- Owner-token SID or scratch ACL tampering.
- Forged native/platform scope or Windows owner device claims.
- Inconsistent or absent process-image readback.
- Invalid uptime or its misuse as boot proof.
- Startup/ACL presence improperly promoted to full proof.
- Runtime health/installed state falsely marked trusted.
- Direct invocation outside the restricted PR-triggered Windows test runner.

CI uses a single Windows job and imports only Windows-native and Python
standard-library libraries for this preflight. No production credentials
or owner authorization are used.

## Hard boundary — facts NOT verified

- Real HUMAN_OWNER Windows SID or FIDO2/Windows Hello identity.
- AION package signer/Authenticode, binary, app version, installed files.
- Effective ACL access for actual installed target.
- Installer transaction journal or committed terminal receipt.
- Startup entry target, owner run context or service state on an owner PC.
- Authenticated process challenge, local voice/hotword, health, runtime.
- Corroborated boot identity or an actual before/after reboot.
- Physical restart power-loss durability, real installer or repair.

## Next PC-dependent stage

A separately approved Windows device/test VM consumer must use owner-bound,
platform-authenticated identity, signed packages, canonical-path and
reparse-point-safe file measurement, trusted ACL effective-permission checks,
trusted boot epoch and challenge handling, independent attestor provenance,
tamper-evident durable receipts, and explicit authorization before any
filesystem, Registry, startup or service mutation.

**NO:** merge, deploy, Worker activation, installation, ACL/Registry
mutation, startup edit, process launch, reboot or real device writes.
