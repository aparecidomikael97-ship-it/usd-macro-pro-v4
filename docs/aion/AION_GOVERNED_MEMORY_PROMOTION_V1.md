# AION Governed Memory Promotion V1

Status: staging hardening only. This contract does not grant action authority,
enable providers, or activate production persistence.

## Problem closed

Previously the layered memory fabric already preserved origin, truth state,
history and scope, and quarantine already prevented automatic authority.
However, a low-level `remember(...)` call could still store a
`truth_state=CONFIRMED` sentence without proving a formal promotion workflow.

This contract separates **stored context** from **promoted canonical memory**.

## State machine

Governed memory follows:

`PROPOSED -> VERIFIED -> PROMOTED`

with terminal governance states `REJECTED` and `SUPERSEDED`.

An entry may exist in layered memory without being promoted. Legacy/direct
entries are explicitly tagged `promotion_state=UNGOVERNED` and are returned
with `promoted=false` / `used_as_current_fact=false`.

## Provenance

Every proposal binds:

- trusted owner/tenant/workspace;
- content digest;
- source type;
- provenance reference;
- evidence references;
- domain/persona/layer/category;
- stable governance proposal id.

Scope comes only from trusted context.

## Taint propagation

External material begins tainted. Examples:

- `UNTRUSTED_EXTERNAL_SOURCE`
- `MODEL_GENERATED`
- `TOOL_DERIVED`
- `IMPORTED_MEMORY`

Verification must explicitly resolve taint. Until then the content cannot be
promoted.

## Independent verification

Verification requires:

- verifier kind from an approved class: CODE, SOURCE_REQUERY, HUMAN or
  INDEPENDENT_MODEL;
- explicit verifier id;
- exact bound verification references;
- exact content digest;
- verifier result marked independent.

A model cannot self-certify its own output by merely returning VERIFIED.

## Promotion

Promotion requires simultaneously:

- proposal state VERIFIED;
- same trusted scope;
- no unresolved taint;
- confirmed truth state;
- provenance + content digest;
- verification refs + verification digest;
- explicit human review approval and reviewer identity.

The promotion proof is hashed and written into the layered-memory row.

A `PROMOTED` layered-memory row is rejected by the fabric unless the governed
proof fields are present and taint is empty.

## Authority

Promoted memory still has:

- action_authorized=false;
- may_expand_permissions=false;
- authority=NONE.

Memory never authenticates identity, grants a role, approves a payment,
authorizes trading, or bypasses execution policy.

## Checkpoint Mestre

`memory_governance` is persisted as a top-level checkpoint section and its
digest is covered by `checkpoint_integrity_report`. Tampering with a proposal
therefore produces MISMATCH and write-safe behavior remains fail-closed.

## Red-team proof

Tests cover:

- external and model-generated taint;
- secret-like content rejection;
- content digest mismatch;
- non-independent/self verification;
- verification reference mismatch;
- verifier digest mismatch;
- human-review requirement;
- cross-tenant promotion attempt;
- full PROPOSED -> VERIFIED -> PROMOTED path;
- legacy confirmed memory remaining UNGOVERNED;
- forged PROMOTED row rejected without proof;
- hostile pasted identity/authority claim unable to promote through
  self-verification;
- supersession preserving history;
- Checkpoint Mestre governance digest tamper detection;
- upgrade of old checkpoint without fabricating any promoted memory.

## Still separate

This block does not yet implement:

- production vector-index deletion/rebuild semantics;
- tenant-specific encryption keys;
- provider-side retention guarantees;
- independent external source fetchers;
- production human-signature/FIDO review.

Those remain later gates.
