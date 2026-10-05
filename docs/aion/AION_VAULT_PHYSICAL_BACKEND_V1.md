# AION Physical Secret Backend V1

Status: **staging / Draft-only**.

## Objective

Close the gap between the metadata-only Vault and the existing Credential Proxy
with a real physical encrypted staging backend.

This is not a production KMS claim.

## Storage

- physical SQLite;
- AES-256-GCM;
- fresh nonce per secret version;
- AAD binds owner + tenant + workspace + secret id + secret version + key
  reference/version;
- key bytes come only from an injected resolver;
- key bytes are never serialized;
- secret values are never written in plaintext;
- audit events contain only identity/version/event metadata and digests.

## Lifecycle

Secret writes, rotations and revocations require exact
`explicit_owner_approval is True`.

Rotation:

- requires exact expected version;
- retires old version and writes the new version atomically;
- can re-encrypt under a new master-key version.

Revocation:

- marks the active version REVOKED;
- future resolution fails closed;
- does not silently delete audit metadata.

## Credential Proxy bridge

`credential_resolver("EXTERNAL_VAULT", locator_ref)` is suitable as the
existing Credential Proxy's injected resolver. The secret material is returned
only at that internal boundary, after the Credential Proxy's own tool/scope/
egress gates.

## Vault attestation

`verified_vault_backend_view` binds active Vault references to a physical
backend attestation with exact owner/tenant/workspace.

The attestation proves staging properties only:

- encrypted_at_rest=true;
- plaintext_persisted=false;
- rotation_supported=true;
- revocation_supported=true;
- backend_connected=true when integrity matches;
- production_kms_connected=false;
- production_ready=false.

## Guardrails

Draft only.
merge=false.
deploy=false.
real secret=false.
production KMS=false.
production backend=false.
automatic rotation=false.
automatic revocation=false.
provider/network=false.
Core Freeze=false.
worker arming=false.
real trading/payment=false.
