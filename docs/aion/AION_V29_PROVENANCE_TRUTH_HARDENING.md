# AION V2.9 — Provenance truth hardening

## Contract

V2.9 makes an existing limitation explicit and machine-readable:

- `origin_authenticated=False`
- `snapshot_signed=False`
- `snapshot_atomic=False`
- `execution_allowed=False`

These values are invariants. They are not feature flags and cannot be promoted by
caller claims, nested snapshot claims, source labels, deterministic hashes or a
rehashed consistency envelope.

## Why this exists

V2.8 introduced deterministic `identity_digest`, `evidence_epoch` and
`snapshot_digest` values. Those hashes detect content/evidence changes and support
deterministic consistency checks. They do **not** authenticate physical origin,
prove possession of a signing key, establish an attested loader, or prove a
coordinated atomic capture.

A source reference such as `resident/checkpoint` is a bounded provenance
descriptor. It is not cryptographic proof of where bytes came from.

## Authority

This change does not introduce:
- signatures;
- keys or key management;
- PKI/KMS/HSM;
- remote attestation;
- a new loader or collector;
- a global transaction/revision;
- execution authority;
- provider/billing/trading authority.

The existing `LoadedEvidence` boundary remains application-trusted resident
input. V2.9 only prevents that trust boundary from being misrepresented as
cryptographically authenticated provenance.

## Display truth

Master Status Board and Admin now display provenance truth independently from
health, consistency and atomicity. A fully consistent and healthy observation can
therefore still truthfully report:

`consistency=CONFIRMED · snapshot_atomic=False · origin_authenticated=False · snapshot_signed=False`

## Fail-closed behavior

A caller that injects or rehashes `origin_authenticated=True` or
`snapshot_signed=True` cannot turn the envelope into trusted evidence. The
display verifier recomputes the canonical envelope and returns UNKNOWN on mismatch.

## Next architectural boundary

Actual origin authentication requires a separately designed trust root: key
ownership, signing scope, canonical signed payload, verification policy, rotation,
revocation, replay resistance, failure semantics and recovery rules. That is not
silently inferred or implemented by V2.9.

Draft only. No merge, deploy, provider activation, billing, paid API, real order,
external execution or auto-repair.
