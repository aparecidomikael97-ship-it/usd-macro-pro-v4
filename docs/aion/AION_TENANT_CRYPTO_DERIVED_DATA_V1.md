# AION Tenant Crypto + Derived Data Lifecycle V1

Status: **staging hardening only**.

This block does not activate subscriber production persistence, a production
KMS, automatic deletion, provider calls, trading, payments, deploys or external
actions.

## Objective

Close the remaining tenant-isolation gap identified by the independent review:

- logical tenant/path/ACL isolation alone is not enough for sensitive durable data;
- backups must follow the same confidentiality boundary as live data;
- derived indexes/caches must be treated as disposable projections, not sources
  of truth;
- deletion planning must include backups and derived copies.

## Cryptographic envelope

The existing `DurableTenantStore` remains the only tenant durable store. No
parallel persistence stack was introduced.

When encryption is configured it uses:

- AES-256-GCM from the pinned `cryptography` package;
- 32-byte AES keys;
- 96-bit fresh nonce per write;
- tenant + workspace + opaque key reference/version + durable revision/digest
  as authenticated associated data (AAD);
- key material supplied only through an injected resolver.

Key bytes are never written to:

- memory.json;
- backups;
- audit logs;
- return payloads;
- Checkpoint Mestre.

The repository still does not contain or call a production KMS. A future KMS or
Vault backend must satisfy the same resolver contract.

## Fail-closed rules

When `require_encryption=True`:

- plaintext legacy envelopes are rejected with `ENCRYPTION_REQUIRED`;
- missing key resolver fails;
- wrong AES key fails authentication;
- ciphertext tamper fails authentication;
- AAD/metadata tamper fails;
- tenant/workspace transplant fails before decryption;
- resolver scope mismatch fails;
- there is no fallback from failed decrypt to plaintext.

Legacy plaintext behavior remains available only for compatibility in existing
staging/unit paths and is explicitly not production-ready.

## Backup and restore

Encrypted stores back up the encrypted outer envelope, not decrypted memory.

Restore:

1. locates the tenant/workspace backup;
2. validates/decrypts it with the key referenced by that backup;
3. validates the inner durable-store digest/revision;
4. writes it through the current store;
5. re-encrypts it under the store's current active key handle/version.

Therefore an old v1 backup can be restored through a v2 store only while the v1
key is still resolvable.

## Rotation and crypto-shredding semantics

Key rotation is explicit and approval-gated.

The red-team uses a test-only in-memory key resolver to prove:

- live data can be re-encrypted from v1 to v2;
- old backup remains bound to v1;
- after test resolver retires v1, the old backup becomes unreadable;
- no file is silently deleted and no production key is touched.

Crypto-shredding is a defense-in-depth mechanism, **not** the sole proof of
deletion. The privacy plan still requires treatment of live data, backups,
derived projections, caches and minimal audit metadata.

## Derived index isolation

The Library Index is explicitly a disposable projection:

- `source_of_truth=false`;
- `disposable=true`;
- rebuild requires reviewed source documents;
- it has no provider/embedding/external persistence in this version.

A cross-tenant bug was found and fixed in this block: reindex replacement was
previously keyed by `document_id` alone. It is now keyed by:

`tenant_id + workspace_id + document_id`.

Two tenants may therefore use the same document id without clobbering each
other's projection.

New lifecycle contracts:

- purge one document projection in the exact trusted scope;
- purge all projections in one trusted tenant/workspace;
- cross-scope purge fails closed;
- rebuild from reviewed source documents;
- projection manifest with deterministic digest and source-of-truth=false.

## Deletion propagation plan

`tenant_deletion_plan` now explicitly includes:

- LIVE_TENANT_STORE
- TENANT_BACKUPS
- DERIVED_INDEXES
- CACHES
- TENANT_DATA_KEY
- MINIMAL_AUDIT_METADATA

It still does **not** execute deletion automatically.

The plan requires:

- fresh identity confirmation;
- explicit execution approval;
- backup reconciliation;
- derived projection purge;
- validation that retrieval no longer returns deleted content;
- key-retirement review;
- no deletion of a shared key;
- crypto-shredding only as an additional control.

## Security tests

The new red-team proves:

- live encrypted file contains no plaintext memory;
- encrypted backup contains no plaintext memory;
- audit metadata does not repeat plaintext payload;
- same plaintext produces different nonce/ciphertext;
- ciphertext tamper fails closed;
- wrong key fails closed;
- plaintext legacy file is refused in encryption-required mode;
- cross-tenant ciphertext transplant is refused;
- key-resolver scope mismatch is refused;
- encrypted backup/restore works;
- explicit v1 -> v2 rotation works;
- retirement of v1 in a test resolver makes old v1 backup unreadable;
- same document id coexists across tenants;
- document purge is scope-safe;
- foreign tenant cannot purge another tenant's projection;
- scope purge preserves other tenants;
- rebuild requires exact-scope source documents;
- deletion plan includes all required propagation surfaces.

## Still open before production

This block does not claim completion of:

- production KMS/HSM/Vault key custody;
- per-tenant production key provisioning/rotation ceremonies;
- automatic backup deletion;
- external provider retention/deletion;
- persistent vector database deletion semantics;
- OS/container isolation;
- legal/LGPD compliance certification.

Those remain separate gates.
