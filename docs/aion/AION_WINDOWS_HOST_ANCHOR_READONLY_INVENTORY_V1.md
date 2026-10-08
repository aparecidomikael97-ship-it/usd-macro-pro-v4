# AION Windows Host Anchor Read-Only Inventory V1

**Scope: CI and future explicitly authorized read-only Windows diagnostics.**
This is a native Windows registry readback probe, NOT an enrolled root, not a
protected host policy implementation, not an installation step, and not proof
of trust against a malicious local administrator.

## Why this block matters
#1097 checks that host-policy snapshots match a cryptographic root,
a policy digest and exact epoch claimed to be protected. However, those
values are still function arguments; if an attacker supplies both policy and
those arguments, it can fabricate a coherent result.

We now implement a read-only, fixed-HKLM observation of a *prospective*
machine-scoped anchor. The key is not installed/provisioned in CI or
on the HUMAN_OWNER computer in this block.

## Future Windows read-only scope
- HKEY_LOCAL_MACHINE only, fixed path:
  SOFTWARE\\AtlasQuant\\AION\\TrustedHostPolicyV1
- 64-bit registry view only: KEY_READ | KEY_WOW64_64KEY.
- Five exact values and types:
  1. AnchorSchema: REG_SZ = AION_HOST_COLLECTOR_TRUST_ANCHOR_V1
  2. PolicyAuthorityPublicKey: REG_BINARY, 32 bytes.
  3. OwnerRegistryRootPublicKey: REG_BINARY, 32 bytes, distinct signer role.
  4. PolicySnapshotDigest: REG_SZ = sha256: + 64 lowercase hex.
  5. PolicyEpoch: REG_QWORD, positive bounded integer.
- Missing, inaccessible, extra or malformed values fail closed.
- No HKCU fallback, no caller-controlled path, no auto-create, no registry
  write/delete, no enrollment, no install, no service, no network.
- Sanitized output: observation digest, policy epoch and challenge binding;
  no usernames, SIDs, registry bytes, public keys or personal paths.
- 256-bit challenge correlates only the readback; it does not authenticate
  the registry or prove a hardware-backed nonce.

## Honesty contract / critical caveat
A well-formed registry key can be attacker-created or downgraded. Reading
HKLM with KEY_READ is not evidence that the key is protected against
admins, rollback, malicious elevated services or offline disk tampering.

This module **intentionally never asserts trust** and does not connect an
observed key to #1097 as a privileged trust anchor.

Maximum result, even if values are present and well-formed:
READ_ONLY_ANCHOR_SHAPE_OBSERVED_UNTRUSTED

Always false:
host_anchor_is_protected, registry_acl_verified,
independent_host_policy_origin_verified, hardware_antirollback_verified,
tpm_binding_verified, owner_identity_verified, physical_attestation_verified,
network_deny_verified, safe_to_resume, collector_launch_authorized,
installer_authorized, build_authorized, deploy_authorized,
trust_store_modified, system_registry_modified.

The Windows GitHub-hosted CI runner executes only a negative/sanitized
read-only probe. No requirement is made that a registry key exists.
Linux uses synthetic registry fakes for adversarial checking and skips
the native HKLM test.

## Next physical gates
Before a future real enrollment, require separate owner-approved
read-only inspection of Windows ACL/access control and provenance,
a trusted anchor source independent of the collector, TPM/Windows Hello
key custody or alternate documented protected root with real antirollback,
HUMAN_OWNER authentication, physical network-denial tests, and
independent collector measurements. Read-only registry observation is NOT
sufficient to permit any of those operations.

No physical PC action in this PR; no costs, merge, deploy, worker,
Render or production key modifications.