# AION V2 — fresh signed witness READ and monotonic CAS protocol reference

**Date:** 2026-10-09. **Parent:** Draft #1127; future stacked Draft #1128.
**NO-GO** for physical installation, trust enrollment, actual witness service,
provider execution or costs. No main/Core changes.

## Precise objective and threat model

The #1127 external-head comparison can only detect host snapshot rollback
when its "independent expected head" really is independently controlled and
fresh. A malicious host can replay a matching stale head or substitute its
collector pin; mathematical consistency alone is not antirollback.

This next step specifies an explicit **independent witness signing key**
(`INDEPENDENT_WITNESS_ED25519`, separate from HUMAN_OWNER and COLLECTOR).
It signs a challenge-bound READ of the witness head. The signed READ includes
full scope, fixed reference period, signed policy generation, owner-pin digest,
service ID, unpredictable client challenge and **minimum acceptable witness
epoch**, as well as the witness head epoch, sequence, latest receipt hash,
latest complete ledger snapshot hash and reference hold totals. A closed
schema and independent signature domain prevent treating a collector-signed
ledger snapshot as witness-signed freshness.

The pure CAS precondition verifier rechecks the signed READ and strict
caller-supplied current witness head; new collector receipt MUST bind
previous receipt hash, increment sequence by one, append a single local
reference hold and increase total reserved signed-cost microunits within the
fixed cap while keeping scope/policy/owner-pin digest/period identical.
The proposed new head remains **data only**. No CAS write is performed by
the product module. The CI contains a separately maintained in-memory mock
witness whose lock models serialized head changes.

## Explicit known limitations

- **No external witness exists yet.** All keys are ephemeral test fixtures,
  not enrolled. The returned "witness public pin", current witness state
  and minimum epoch are injected by tests/callers, not anchored to trusted
  storage, a real protected remote service, TLS identity or hardware.
- The fresh nonce must come from an authenticated, independent CSPRNG and
  **never be reused**, and host policy/epoch floors must themselves be
  integrity protected. Merely echoing a nonce supplied by an adversary
  cannot guarantee freshness. Replay of a signed READ under the identical
  reused challenge remains mathematically valid.
- Test-only `MockExternalWitness` is RAM-only and **not** protected against
  full service restore, split-brain writer, network replay or operator
  substitution. The host-supplied `current_service_head` MUST NOT be
  authoritative in a production CAS; the witness server must obtain the
  current head and compare/update **atomically inside its own trust boundary**.
- CAS preconditions based on signed sequence/counters are not a proof of
  an append-only trusted history without validating the actual complete
  ledger state and witnessed committed chain. It is a mathematical envelope,
  **not production cost accounting or execution authority**.
- The local SQLite ledger and an independent witness cannot be updated
  atomically using this module. Crash after local hold but before remote
  CAS => local state ahead of witness, **BLOCK**; crash after remote CAS but
  before client response => fresh READ reveals remote advancement but NOT
  paid HTTP outcome. Never assume a model was called or retried safely.
- A genuine implementation needs durable per-operation idempotency and
  witnessed state machine, an authenticated **protected** witness head
  with compare-and-swap and an independently enrolled public trust root,
  offline fail-closed policy, rotation/revocation and recovery, stable
  pricing/FX/budget and separate single-shot paid dispatch outcome journal.
  Check point #1117 before any host changes or spending.

## Read-only exported contracts

`atlasquant_aion_v2_authenticated_witness_read_cas_reference.py` contains:

- `canonical_fresh_read`: closed canonical domain-separated signing bytes.
- `review_signed_fresh_witness_read`: math-only challenge/scope/pin/epoch
  verification; rejects missing or mismatched query including changed epoch
  floor, bad signature, old sequence, malformed signed fields.
- `review_reference_witness_cas_preconditions`: math-only rereview of READ,
  strict expected current state and signed collector append; produces an
  uncommitted proposed head, **NEVER persists a CAS**.

Every return path sets actual owner enrollment, witness key enrollment,
trusted network freshness, CAS durability, real budget, provider call,
billing and installer/safe-to-resume fields to **false**. Neither
`READ_SIGNATURE_AND_CHALLENGE_MATH_ONLY_UNTRUSTED` nor
`CAS_PRECONDITIONS_MATH_ONLY_UNTRUSTED` may become
`request_approved=True` or be interpreted as paid consent.

### Adversarial CI

Uses GitHub-hosted Windows and Ubuntu, ephemeral synthetic keys and isolated
SQLite. Concurrent CAS against the same in-memory mock head allows at most
one synthetic winner; replayed old READ with different challenge, old remote
state, fork, tampering, role/purpose changes, policy/scope/epoch changes,
invalid cost sequence, failed signatures and malformed schemas block.
Demonstrates both crash-gap directions and separate witness-pin swap.
Prior #1127/#1126/#1125/V1 provider regressions remain part of the matrix.

**No CI secret; no real HTTP, no deployment, no main merge, no paid model,
no device installation, no real owner signing ceremony.**
