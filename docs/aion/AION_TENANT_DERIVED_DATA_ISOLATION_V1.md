# AION Tenant Derived-Data Isolation V1

Status: staging hardening only. This contract does not claim production
encryption, key custody, legal deletion completion, provider retention control,
or external persistence activation.

## Objective

Close the tenant-isolation gap outside the canonical database.

The boundary explicitly covers:

- cache;
- search/index projections;
- backups;
- logs;
- traces.

A tenant boundary is tenant_id + workspace_id. Every derived artifact receives a
scope digest and a dedicated namespace.

## Cache

Cache keys are invalid unless they bind all of:

- scope digest;
- purpose;
- source digest;
- policy version;
- data version;
- producer/model/tool version;
- optional query digest.

This prevents a cached result from silently surviving a policy, source-data or
producer-behavior change.

## Index

Indexes are declared:

- canonical_source=false;
- rebuildable_projection=true;
- disposable_projection=true.

The Library index is now bound to one tenant/workspace scope. It refuses an
attempt to mix rows from another scope, and a foreign-scope reader is blocked
rather than receiving a misleading empty result.

The canonical source remains reviewed source/provenance, never the index.

## Derived registry

The control-plane registry contains metadata only. It never stores artifact
payload contents.

For each artifact it records:

- tenant/workspace scope;
- namespace;
- source digest;
- policy/data/producer versions;
- retention metadata;
- state.

A registry digest detects metadata tampering.

## Deletion/retention

A tenant deletion request creates an idempotent tombstone targeting derived
artifacts.

Deletion cannot be described as complete while targeted derived artifacts are
pending.

Backups with an active retention window enter:

ERASURE_PENDING_RETENTION

and block a completion claim until the retention window has expired and a purge
evidence reference is provided.

Even after all derived artifacts are reconciled, this control-plane still keeps:

canonical_delete_executed=false
deletion_complete_claimed=false

because canonical deletion is a separate authenticated runtime operation.

## Privacy contract

The tenant privacy plan now explicitly requires:

- cache purge;
- index purge/rebuild;
- log/trace reconciliation;
- backup retention reconciliation;
- fresh identity confirmation;
- explicit execution approval.

## Red-team proof

Tests cover:

- same payload in two tenants => different namespace/cache key;
- same tenant, different workspace => different boundary;
- policy/data/producer version changes => different cache key;
- missing version binding rejected;
- index is rebuildable/noncanonical;
- every derived class uses a scoped namespace;
- foreign-tenant registry blocked;
- registry metadata tamper detected;
- stale policy invalidates artifact resolution;
- deletion tombstone targets all derived classes;
- backup retention blocks completion;
- post-retention derived purge can confirm without falsely claiming canonical deletion;
- tombstone replay is idempotent;
- no production encryption/KMS claim;
- Library index refuses scope mixing;
- tenant privacy plan exposes derived purge and backup reconciliation requirements.

## Explicit remaining production gate

This block intentionally does not invent cryptography.

Before production multi-tenant persistence, a separate gate still must prove:

- encryption at rest in the selected production store;
- tenant-specific key isolation or equivalent KMS envelope design;
- key rotation;
- backup encryption;
- restore with correct tenant key;
- revocation/crypto-erasure semantics where legally and operationally appropriate.

Until that proof exists:

tenant_key_management_implemented=false
production_encryption_claimed=false
