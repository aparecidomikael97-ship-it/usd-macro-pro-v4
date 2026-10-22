# AION / P0 A163 — Synthetic enrollment, rotation, and terminal revocation (NO-GO)

**2026-10-22 · Draft stacked on A162 · isolated LAB · no approval to merge or deploy.**

## A162 gap: a signature can be cryptographically valid under a retired key

A162 is a read-only reconciliation combining the A147 SQLite
`RESERVED_UNCERTAIN` journal, A145 signed checkpoint, A150 local witness
head, and A161 dual-signed D1/D2 nonce-bound floor. Its successful output is
always manual quarantine: **HARD NO-GO for real H0**.

A162 takes two pinned D1/D2 public keys from a caller. **That does not
determine whether the caller's pin is current, properly enrolled, rotated,
compromised, retired, or revoked.** An old Ed25519 key continues producing
valid mathematical signatures after an administrator revokes it.
The origin of the out-of-band pins and the latest nonrollbackable policy
generation are external trust preconditions. A163 models how a future
operator ceremony should be checked without asserting those preconditions.

## New policy and read-only checks

`aion_p0_a163_custody_enrollment_revocation_lab.py` defines an exact
domain-separated `PolicyEvent` and `SignedPolicyEvent` chain with:

- `ledger_id`, `epoch`, `generation`, `action`, prior signed-policy
  digest, D1/D2 public keys, nonce and synthetic issuance time.
- A **single expected issuer verification key pre-pinned by the test
  caller**; it is NOT a proof of HUMAN_OWNER identity or independent
  administration.
- `ENROLL` may occur **only at generation 1**, with zero genesis digest,
  distinct D1/D2 keys, unique nonce, an issuer Ed25519 signature, and each
  new custodian's **proof of possession** over the exact event under a
  separate domain.
- `ROTATE` must advance one generation, bind the previous full signed
  digest, move synthetic time forward, use an unused fresh nonce, get both
  *old* D1/D2 cryptographic **retirement acknowledgements**, get both
  new D1/D2 proofs of possession, and obtain the issuer signature.
  Every retired key is forever forbidden from reuse in either role.
- `REVOKE_ALL` is a conservative terminal emergency shutdown signed by
  the issuer with **no new D1/D2 keys, POPs or retirement claims**.
  There is **no reenrollment, repair, reversal or auto-rebootstrap
  within the same ledger epoch**. A new real epoch would need a distinct
  independently authorized design beyond A163.
- `PolicyAnchor(ledger_id,epoch,generation,chain_digest)` is an explicit
  caller-supplied expected latest head and MUST match the whole chain.
  An old policy with a latest anchor (or latest policy with old anchor) is
  blocked. This **does not** establish that the anchor was independently
  retrieved or that its storage cannot be rolled back.
- Issuer and active/retired D1/D2 key reuse is forbidden. The complete
  check rejects wrong ledger, epoch, type, malformed signature/nonce/digest,
  sequence gaps, duplicated nonces, clock reversal and unbounded records.
- The wrapper `assess_enrollment_and_recovery` first validates this chain.
  For a revoked policy it returns `LAB_HARD_BLOCKED` before using any
  existing old signatures. For a non-revoked policy it passes **only the
  current generation's D1/D2 pins** to the already-conservative A162
  correlator. A previously valid floor from the old keys must then fail.

No procedure in this module stores keys, contacts custodians, provisions a
real provider, writes SQLite or returns production approval. Every
`CustodyReview` has explicitly false fields for independent issuer and
D1/D2 administration, irreversible anchor, HUMAN_OWNER consent, real
provider effect/no-effect, Worker, external execution, auto-retry/resend,
and `homologated_p0_count=0`. Cryptographic consistency may return
`LAB_QUARANTINE_MANUAL_REVIEW`, **never GO**.

## Negative proof: two independent-looking keys can still be jointly compromised

A policy chain issued, held and signed by the same local test operator can
be rolled back **together with the caller-supplied 'trusted' anchor**.
The stale policy and old custodian signatures can still mathematically
validate. The A163 test explicitly demonstrates that case and requires
quarantine, not authorization. Merely changing D1/D2 key bytes or
generating more signatures cannot solve compromised shared administration.
Real independence requires separate accounts, administrators, durable
nonrollbackable anchors and authenticated key enrollment, plus revocation
propagation and externally verified freshness.

This LAB does NOT establish true emergency revocation delivery if
the attacker controls the caller's anchor; an old anchor can be replayed
from a shared snapshot. A real revocation requires protected and
independently distributed policy floor and outage-safe denial.

## Adversarial / CI requirements

- **80 A163 tests**: 60 explicit negative or controlled scenarios plus
  20 malformed enrollment-record variations (actual Ed25519 and real
  disposable A147/A150 SQLite + A162 read-only).
- A151 static LAB/runtime fence is **extended to recognize only the
  explicit A163 root experiment**, with **four more tests** that ensure
  `runtime/`, `deploy/` and dynamic imports of A163 still fail. The
  A151 runner now expects 24 tests, up from 20.
- Prior A145–A162 = **860** in the A162 CI baseline. This A163 branch
  adds four A151 boundary cases and 80 policy cases = **944 cases per
  Windows/Ubuntu platform**; **1,888 individual executions** if both pass.
  Independent A154 restore/writer, A156 recovery, A157 workflow IAM
  guard, E0–E5 documentary and the historical 32 provider proof errors
  must all still report **HARD NO-GO**.
- These are **planned counts** until Actions actually finishes.
  A green synthetic suite does not certify independent custody.

## Human actions and formal acceptance still missing

1. Proof of verified **HUMAN_OWNER** possession and authorization for
   critical P0 enrollment/revocation decisions (FIDO2/Windows Hello);
   signatures from a test operator are NOT that proof.
2. Two independent vendor custodians with identities, key lifecycles,
   authenticated transport, immutable monotonic policy floor, real
   revocation distribution and audit evidence.
3. Verified external H0 restart/recovery and trusted supplier response
   (`COMMITTED_EFFECT` or terminal `NO_EFFECT_FENCED`) for the first
   uncertain effect. A CAS/witness receipt is not a provider receipt.
4. Closure of **32 independent producer blockers** (23 enrollment,
   eight causal effect receipts, one terminal no-effect), historical
   SQLite and Quality P0 blockers and formal independent acceptance.
5. FinOps owner approval prior to provisioning accounts or spending.
   No new service/vendor/provider purchase is requested by this PR.

**NO MERGE · NO DEPLOY · Worker OFF · ZERO_AUTO_RESEND · 0/6 P0 · HARD NO-GO.**
