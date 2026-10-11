# AION V2 — signed EXTERNAL witness head challenge (reference only)

**Date:** 2026-10-09. Stack: #1127 on #1126 → #1125 → #1124 → #1123 → #1122 → #1121 → #1120 → #1119.
**Status: PRE-ENROLLMENT, PRE-WITNESS, PRE-PRODUCTION, NO-GO.**

## What this change actually tests

A local SQLite nonce/cost ledger (#1126) remains restorable. A detached,
domain-separated `COLLECTOR_ED25519` signature can commit to its **complete
canonical V2 ledger snapshot**, including config and every scoped hold's nonce,
signed-intent digest, entire resolved provider-request digest, signed maximum
micro-USD amount, policy generation, period, public owner pin hash and
aggregate counters.

A **separately supplied external head** must match the exact witness
sequence and fingerprint of the signed receipt. The verifier independently
recomputes the digest over the currently opened local ledger; any mismatch
blocks. Unknown/older/newer sequence, same-sequence forked signed receipt,
missing external head, failed signature, malformed closed schema, changed
local full-request digest, inconsistent local SQL counters or old snapshot
restore against a newer head block.

**The external head in CI is a deliberately independent in-memory fixture,
not a remotely enrolled, persistently attested or independently trusted
service.** The code does **not** create, sign or publish witness receipts,
fetch any network head, enroll collector keys or manage hardware.

### Deliberate counterexample / limitations

An attacker who can restore the SQLite DB **and make the caller supply a
matching stale external head** can make the restored state pass a mathematical
equality check. Similarly, attacker-chosen `collector_public_pin` and
attacker-signed receipts are mathematically valid if the caller supplies the
corresponding forged head. The adversarial tests DEMONSTRATE both failures of
external trust assumptions; the candidate outcome is explicitly
`EXTERNAL_HEAD_MATCH_MATH_ONLY_UNTRUSTED`, never real antirollback.

Even with real protected external storage, a checked head would need:
- server-authenticated, fresh read, protected against MITM/replay/cache
  substitution, pinned origin, strict scope and genuine enrolled collector
  key; protected monotonically increasing sequence with compare-and-swap;
- atomic witness head advancement and one-shot authorization allocation, or
  an explicit crash/unknown outcome protocol. A local reference hold
  followed by witness publication is **not atomic**, and may be interrupted
  after one side commits. This demonstration never asserts otherwise;
- protected recovery semantics: unavailable witness, unsigned reset,
  stale or future epoch/sequence, divergence or unknown dispatch must BLOCK;
  do not silently repair by replacing the external head with local data;
- key rotation/revocation/recovery tied to HUMAN_OWNER presence and trust
  registry. Separate `COLLECTOR_ED25519` and `HUMAN_OWNER_ED25519` roles,
  never owner key in CI/host/GitHub. Never infer live consent from an
  arbitrary matching mathematical signature;
- production-verified provider/auth identity, quote/pricing/FX, operational
  billing caps, full HTTP body and transport semantics, one-shot dispatch
  persistence and client reply. Current signed request digest excludes
  authentication secret and wire serialization specifics.

## Reference code surface

`atlasquant_aion_v2_external_witness_rollback_reference.py`:

- `local_v2_snapshot_commitment(ledger)` takes an internally consistent
  local transaction and returns the canonical digest and aggregate counts.
  It never attempts a trusted external fetch or changes ledger holdings.
- `make_unsigned_witness_head_candidate(ledger, ...)` returns an **unsigned**
  proposed head. A real trusted collector is NOT implemented.
- `canonical_witness_head(payload)` and `signed_receipt_sha256(envelope)`
  define closed V1 witness transcript and receipt fingerprints.
- `review_witnessed_v2_reference_state(ledger, envelope,
  collector_public_pin, independent_expected_head)` is a **math-only**
  comparison. The supplied external expected head **must** later come
  from an independently trusted service; none is configured or claimed.

The CI simulates snapshot save and rollback while keeping the latest
witness head outside the snapshot; older local ledger + newer external head
are rejected. It also shows that old local + deliberately stale external
head can pass math, proving why **real independently protected freshness**
cannot be skipped.

## Acceptance gates — do not promote

This Draft does not activate a witness in cloud, Windows, TPM, GitHub
Actions, user phone or any other device. No public key enrollment,
credentials, billing, production DB, real model calls, installer, merge or
deploy. No policy/owner approval flag can be derived from any candidate
status. No automatic rollback repair, ledger reset or stale-head acceptance
can be added without distinct explicit owner approval.

**Still false:** HUMAN_OWNER identity/custody verification,
collector enrollment/custody verification, independent witness freshness,
production antirollback, atomic witness+nonce budget, source Chat DB
atomicity, real model quota/spend, real network/provider/billing invocation,
installer authorization and safe-to-resume.

**Next review:** choose a genuine independent trust anchor/witness with
verifiable freshness and monotonic CAS (compare cost and hosting options
inside R$200/month cap *before* requesting any expense or deployment),
then design trusted enrollment and crash-atomic state machine. Keep
Core/main/Draft stack untouched until separately authorized.
