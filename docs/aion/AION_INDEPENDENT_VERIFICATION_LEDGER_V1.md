# AION Independent Verification Ledger V1

Status: staging hardening only. This contract does not grant authority, execute
external actions, enable providers, or activate production persistence.

## Objective

Close the architectural gap where a component could claim that a verification
was "independent" without a tamper-evident record binding:

- the original generator;
- the independent verifier;
- the claim digest;
- the evidence refs;
- the trusted owner/tenant/workspace;
- the verification result.

## Ledger contract

Every verification event is append-only and contains:

- monotonically increasing sequence;
- immutable entry_id;
- previous_hash;
- entry_hash;
- claim_id and claim_digest;
- generator_id;
- verifier kind and verifier_id;
- evidence refs;
- trusted scope;
- result state;
- result digest;
- blockers and reason.

The ledger itself has a tip_hash and digest. Deletion, insertion, reordering,
rewriting or tip replacement is detected.

## Independence

Approved verifier classes are:

- CODE
- SOURCE_REQUERY
- HUMAN
- INDEPENDENT_MODEL

The generator principal and verifier principal must be different.

A verifier result must bind exactly:

- verifier_id;
- claim digest;
- evidence refs;
- independent=true.

Failure or exception is recorded as INCONCLUSIVE, never silently accepted.

## Memory promotion binding

Governed memory keeps the old low-level verification helper for compatibility,
but it is now non-promotable by itself.

Canonical memory promotion requires:

1. PROPOSED memory;
2. independent ledger verification;
3. exact ledger entry id + entry hash bound into the memory proposal;
4. same trusted scope;
5. no unresolved taint;
6. human review approval.

If the verification ledger is missing, tampered, cross-tenant, bound to another
claim, or has a different entry hash, promotion fails closed.

## Checkpoint Mestre

The verification ledger is a top-level Checkpoint Mestre component.
checkpoint_integrity_report verifies the ledger hash-chain and digest.

A tampered verification ledger therefore makes the checkpoint MISMATCH.

## Red-team proof

The test suite covers:

- empty genesis ledger integrity;
- multi-entry hash chaining;
- generator == verifier blocked;
- non-independent result -> INCONCLUSIVE;
- claim digest mismatch;
- evidence-ref mismatch;
- verifier exception -> INCONCLUSIVE audit event;
- content rewrite detected;
- entry deletion detected;
- reordering detected;
- tip rewrite detected;
- digest rewrite detected;
- append to tampered ledger refused;
- cross-tenant lookup blocked;
- wrong-claim lookup blocked;
- rejected result never returned as VERIFIED;
- Checkpoint Mestre tamper detection;
- normalizer never silently heals a broken chain;
- legacy unledgered memory verification cannot promote;
- full ledger-bound memory promotion succeeds only after human review.

## Explicit non-goals

This is not a distributed transparency log and does not claim external
immutability against a fully compromised host. Production-grade remote
attestation/WORM storage/key custody remain later deployment gates.

The ledger still never authorizes action, expands permissions, signs as the
owner, or replaces Guardian/approval.
