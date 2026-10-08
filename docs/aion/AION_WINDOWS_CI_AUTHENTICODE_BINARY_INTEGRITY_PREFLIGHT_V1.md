# AION Windows — CI Authenticode + Binary Integrity Preflight V1

**Stage:** IMPLEMENTATION SAFE / Draft / PR-CI only / no owner device  
**Base:** #1063 Native Windows Read-Only Verifier Preflight  
**Date:** 2026-10-08

## Objective

Exercise Windows Authenticode evidence retrieval for an *existing signed
Windows system executable* on a disposable GitHub-hosted Windows runner,
together with an inert tampered-file negative control. This advances native
verifier capability and **does not mean AION has a valid binary or publisher
signature**.

The script inspects a fixed Windows OS PowerShell executable via
`Get-AuthenticodeSignature -LiteralPath` and
`Get-FileHash -Algorithm SHA256`. On Microsoft Windows, the command may
select a Windows catalog signature rather than an embedded signature.
It is the operating system trust assessment on that CI runner, not a
production issuer certification or a pinned AION publisher.

Official behavior:
https://learn.microsoft.com/powershell/module/microsoft.powershell.security/get-authenticodesignature

## Signed test baseline and negative control

1. Read the fixed CI Windows PowerShell executable; require `MZ` PE
   header and minimum size.
2. Query Authenticode signature status and SHA-256 binary hash.
3. Collect only the SHA-256 of the signing certificate DER bytes (if present).
   No full certificate, account, publisher subject, user SID, file path or
   Windows hostname is returned as evidence.
4. Place a **copy only** under a unique directory in `RUNNER_TEMP`;
   flip exactly one byte outside the MZ header. NEVER execute the copy.
5. Re-query Authenticode status and binary hash on the modified copy.
6. The baseline must report `Valid`; the modified copy must **not** report
   `Valid`; their binary hashes must differ, sizes must remain equal.
7. Write a sanitized fixture JSON only to the disposable runner scratch
   directory. Cleanup occurs even if tests fail.

The runner copies/writes the modified test file and JSON scratch fixture;
the script does not write the original system executable, installed AION,
registry, ACL, service, startup entry, production store or owner workstation.

**Important:** Windows Authenticode status alone does not validate an
AION-specific publisher identity. Revocation/network policy cannot be
independently asserted merely by calling this PowerShell cmdlet; no claim
is made that no network retrieval is possible. Future production verifier
must explicitly enforce offline or approved network revocation policy.

## Fail-closed review contract

Python classification requires:
- an exact, allowlisted test-fixture schema; no extra raw identifiers;
- exact challenge, policy and source digests;
- `EPHEMERAL_WINDOWS_GITHUB_PR_RUNNER` scope;
- `CI_SIGNED_WINDOWS_SYSTEM_POWERSHELL` artifact role;
- fixed SHA-256 formats, PE header and byte counts;
- real signature status `Valid` for the OS baseline;
- tampered copy signature status other than `Valid`;
- proof that the one-byte modification changed the file hash;
- no promotion to actual AION examination, trusted owner identity, actual
  installation, signed release verification or physical health.

Maximum preflight result:
`CI_SIGNED_OS_BINARY_AND_TAMPER_CLASSIFIED_UNTRUSTED`.

The word `UNTRUSTED` is mandatory: the signature and hash measurements are
fed back through a CI-generated fixture, not signed by an independent
device attestor. The OS trust decision is not an AION publisher-pin policy.

## Future AION release policy shape

The second API drafts a future policy requiring independent inputs:

- installation ID and expected AION binary SHA-256;
- independently approved/pinned AION signer certificate SHA-256;
- trusted publisher-policy digest and release-manifest digest;
- owner-device binding and fresh owner-challenge digest;
- canonical path / anti-reparse-point policy digest;
- certificate revocation policy digest;
- independently reviewed native verifier binary-manifest digest.

This API is purely a *contract-shape builder*. Supplying these digests is
not evidence that the user approved them, and a self-supplied certificate
pin is not trust. It always emits FALSE for signer/owner trust, physical
binary measurement, authorization, deploy and Worker.

Future consumer must separately establish approved key origin, chain policy,
proper signature verification for the **exact AION bytes** at a fixed
canonical path, independent owner identity and auditable publication.

## CI security boundaries

- Pull-request-triggered Windows hosted runner; scoped read-only repo token.
- No production secrets, no installer outputs, no owner credential access.
- The modified scratch .exe is not run.
- No merge, deploy, service creation, AION launch, Registry/ACL/startup
  modification, device restart, installation authorization or token
  consumption.
- CI cross-checks test module, PowerShell fixture script, and the
  no-production-effects policy; the scratch directory is deleted.

## Next milestone

Implement a **signed AION development artifact provenance gate** without
issuing production trust. Any real AION installer or desktop machine
verification requires a separate explicit authorization and genuine
publisher-key governance.

Maximum project stage:
`READY_FOR_AION_SIGNED_RELEASE_PROVENANCE_CONSUMER_DESIGN`, not physical
AION readiness or safe-to-install status.
