# AION Projection + Cache Governance V1

Status: staging hardening only. This contract does not connect an embedding
provider, vector database, external cache, production persistence or external action.

## Retrieval projection rule

Any lexical, semantic, vector or embedding index is a **disposable projection**
of canonical AION state. It is never a source of truth.

A projection row binds:

- tenant + workspace;
- canonical source id;
- canonical source version;
- canonical content digest;
- canonical state;
- provenance references;
- truth state;
- inherited taint.

A retrieved chunk must be rebound to the **current canonical source** before it
is usable as evidence. If the canonical source is deleted, changes version,
changes digest, changes state, changes provenance or crosses scope, the hit is
blocked as stale.

Retrieval ranking never elevates confidence and retrieval never means validation.

## Rebuild/delete semantics

Projection rebuild accepts canonical records, not the previous projection.
Therefore stale residual chunks are not an authority source.

Deletion from a projection removes the source and every derived chunk. The
existing AION Library index is explicitly marked:

- projection_only=true
- canonical_source=false
- rebuildable=true
- retrieval_does_not_validate=true

and receives a scoped document-projection delete operation.

## Cache rule

The local cache key binds all of:

- tenant;
- workspace;
- policy version;
- canonical data version;
- cache class;
- query.

The cache is an optimization, not canonical state. Provider-side prompt caching
is explicitly not trusted as an AION isolation mechanism.

TTL is bounded by both the local maximum and the earliest source validity.
Expired source data cannot be cached.

The following classes are structurally non-cacheable:

- live market data;
- authority;
- credentials/secrets;
- payments;
- trading execution;
- sensitive personal data.

Secret-like values are also refused.

## Invalidation

A canonical source change/deletion invalidates only dependent entries for the
same tenant/workspace. Scope invalidation cannot flush or alter another tenant.

## Red-team proof

Tests cover:

- cross-tenant projection build;
- unresolved-taint source injection;
- chunk/source digest mismatch;
- version/digest drift after retrieval;
- canonical source deletion;
- complete chunk deletion from projection;
- existing Library index projection/deletion semantics;
- cross-scope projection deletion;
- cross-tenant cache key isolation;
- policy-version and data-version cache isolation;
- TTL capped by source validity;
- sensitive/live classes never cached;
- secret-like cache value rejected;
- source-event invalidation;
- scope invalidation preserving other tenants;
- provider prompt cache explicitly untrusted.

## Still separate

This does not yet implement:

- production embedding generation;
- a vector DB;
- provider-specific cache guarantees;
- tenant encryption keys;
- production LGPD deletion orchestration across backups.

Those remain later gates.
