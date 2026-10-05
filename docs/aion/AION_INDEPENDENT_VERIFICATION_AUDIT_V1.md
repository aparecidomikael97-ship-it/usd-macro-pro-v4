# AION Independent Verification + Governance Audit V1

Status: staging hardening only. No provider, external tool, deploy, payment,
trading, production persistence, or authority expansion is activated here.

## Objective

Close the remaining verification gap identified by the independent architecture
review: the same model or component that produced a claim must not be able to
turn that claim into trusted canonical memory merely by saying that it verified
itself.

This block also reuses the existing UnifiedJournal hash-chain instead of
creating a parallel audit system.

## Verification request

Every claim verification request binds:

- owner / tenant / workspace;
- claim reference;
- exact content digest;
- producer id + producer fingerprint;
- evidence references;
- provenance references;
- policy version;
- creation timestamp;
- request digest.

## Independent verification lanes

Four explicit lanes exist:

- CODE — deterministic constraints, all required checks must be exactly true;
- SOURCE_REQUERY — evidence is re-fetched/re-resolved by an injected resolver;
- HUMAN — exact evidence set + explicit review reference;
- INDEPENDENT_MODEL — a distinct verifier identity/fingerprint plus explicit
  independence attestation.

The producer id and producer fingerprint must differ from the verifier id and
verifier fingerprint.

## Receipt contract

A successful verifier emits a tamper-evident receipt binding:

- request digest;
- claim/content digest;
- verifier id/fingerprint;
- producer id/fingerprint;
- exact evidence refs;
- verification method and evidence;
- verified timestamp;
- receipt digest.

Receipts are short-lived and scope-bound.

A receipt never:

- grants approval;
- grants execution authority;
- expands permissions;
- executes an action.

## Memory promotion integration

A memory proposal may reach VERIFIED through the legacy callback seam for
compatibility, but it **cannot reach PROMOTED** without a structurally validated
independent verification receipt.

The promotion proof now includes the verification receipt digest.

Therefore:

`PROPOSED -> VERIFIED -> PROMOTED`

requires both:

1. independent verification receipt; and
2. explicit human promotion review.

Neither step authorizes an external action.

## Audit

The existing UnifiedJournal is extended with governance event classes:

- VERIFICATION_RECORDED
- MEMORY_PROMOTION_RECORDED
- AUTHORITY_REVALIDATED
- OUTBOX_RECONCILED

These events use the same per-request hash-chain, scope binding, event digest,
head digest, physical durable store, crash recovery, idempotency and quarantine
behavior already certified in the unified journal.

The governance audit bridge does not create another source of truth.

## Red-team coverage

Tests prove:

- producer cannot verify itself by id;
- producer cannot verify itself by fingerprint;
- deterministic verifier fails if one constraint is false;
- source requery requires exact refs, content digest and source snapshots;
- independent-model lane rejects missing independence attestation;
- human review cannot approve an evidence subset;
- receipt tampering fails digest validation;
- cross-tenant receipt reuse fails;
- stale receipts fail;
- memory promotion without a validated receipt is blocked;
- a valid receipt is bound into the promotion proof;
- journal tampering after verification is detected;
- governance audit events survive physical journal-store restart;
- revocation and outbox reconciliation are auditable without granting authority.

## Explicit limits

This block does not claim that an external model is currently connected or
independent in production. Independence is a contract that a future configured
verifier must prove at runtime.

Tenant encryption/key management, cache/vector-index deletion semantics,
production backup crypto-shredding and process/container sandboxing remain
separate gates.
