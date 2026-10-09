# AION Owner CNG Read-Only Challenge Correlation Receipt V1

**DRAFT / CI ONLY. No further owner-device probe in this PR.**

## Finding
The owner-specific read-only CNG wrapper in Draft #1104 accepted a
fresh 256-bit challenge nonce but previously only validated its shape.
The challenge did not appear in a verifiable output. The physical
diagnostics from #1105 remain honest observations of the connected
Windows `am12` but **do not gain an authenticated receipt retroactively**.

The last physical observation (on #1105 HEAD
`a52338709af95f594676b0e2f910612ec74de7e2`) found five native
signature-algorithm records, normal CNG open/enum/free results, and
`SIGNATURE_CLASS_MISMATCH` from the strict Python decoder. The
documented class correction in #1106 has Windows/Linux CI green, but
**has not been re-run physically** and remains unproven on am12.

## New correlation envelope for future runs
After the existing single, explicitly owner-approved CNG
`NCryptEnumAlgorithms` read-only call returns its **sanitized** report,
the owner wrapper computes:

1. Canonical ASCII JSON of the sanitized observation
   (sorted keys, compact separators; no raw provider records);
2. `sanitized_observation_sha256`;
3. `challenge_binding_sha256 = SHA256(domain-separator || 32-byte
   nonce || raw-observation-SHA256)`;
4. A self-described, explicitly **unsigned** correlation receipt,
   including the nonce (public correlation value), two digests,
   exact diagnostic scope and permanent no-trust flags.

A pure, offline verifier recomputes both SHA256 values, enforces
the exact receipt schema, nonce format and permanent denial flags.
It does not call Windows, CNG, TPM or any network service.

A verifiable digest only establishes **self-consistency** of a supplied
record. It is NOT a cryptographic owner signature; any party with
write access to the report can replace both the report and digest.
There is no external nonce registry, trusted timestamp, independent
witness, TPM quote, hardware attestation, device identity, replay
prevention or durable audit seal. The nonce is not secret and the
receipt is not an authorization artifact.

## Guaranteed denial semantics
Even if the underlying native CNG API lists `ECDSA_P256` or
`ED25519`, the receipt will retain `receipt_signed=false`,
`independently_witnessed=false`,
`owner_identity_attested=false`,
`physical_device_attested=false`,
`trusted_host_anchor_verified=false`,
`replay_prevention_verified=false`,
`installer_authorized=false`, `safe_to_resume=false`.
The original observation also keeps every
private-key/physical/network/install/build/deploy flag false.

The new maximum receipt-verification state is
`CORRELATION_RECOMPUTED_UNTRUSTED`; no release, enrollment,
merge or deploy permission is generated from the digest.

## Limits of this PR
- Only pure-Python output formatting and offline verification in the
  already owner-scoped wrapper; no new native CNG calls, flags, algorithms,
  DLLs, registry paths or Windows privileges.
- Original silent operation `NCRYPT_SIGNATURE_OPERATION` and
  `NCRYPT_SILENT_FLAG` retained; no `dwFlags=0` fallback.
- 14 new adversarial synthetic tests and prior #1103/#1104/#1105/#1106
  regressions on disposable Windows/Linux GitHub CI.
- **No new execution on owner am12.** The latest `vamos lá` was
  treated as approval to advance safe repository development only.
  Before one more physical read-only probe with new pinned source, a
  separate explicit owner authorization is required.
- No key creation/open/enumeration/enrollment, no ACL/TPM/registry/
  Windows security-state changes, no network services, no local script
  installation, no spend.
- AION installer and physical #1049 sandbox / #1087 network proof
  gates remain BLOCKED.
