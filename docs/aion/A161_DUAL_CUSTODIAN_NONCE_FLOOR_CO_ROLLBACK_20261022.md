# AION A161 — Two-custodian signed floor with nonce, explicit co-rollback counterexample

**Date:** 2026-10-22  
**State:** SYNTHETIC LAB only / PR Draft / **HARD NO-GO, 0/6 P0**.  
**Policy:** NO production account, external witness enrollment, real key, provider SDK,
Worker, automatic resend, checkpoint restore, deployment, merge, external transaction
or new expenses.

## Why we need this

A145–A150 provide signed local checkpoints, a local SQLite witness and CAS,
signed receipts, a locally pinned policy and a 30-second challenge lease. A160
demonstrated and fixed an inherited A149 method-bypass vulnerability with
RED-first 21/30 failed tests and GREEN 716/716 tests per OS.

**However:** if an administrator controls *both* the local checkpoint SQLite
and the local witness database and key, they can restore all of them from
a single old snapshot. The old checkpoint and witness then mutually validate
despite both being stale. A good Ed25519 signature alone does not prove the
signer has retained the latest external state; similarly a policy/clock
stored in the same mutable snapshot cannot prove freshness.

A161 models precisely what would be required to notice that attack when a
genuinely independent custodian supplies a more recent irrevocable floor.
It DOES NOT implement such a real custodian.

## New read-only protocol — exact signed claim and mandatory trust roots

`aion_p0_a161_dual_custodian_floor_lab.py` defines:

- `HeadSnapshot(ledger_id, epoch, sequence, history_digest)`, a read-only local
  comparison value. `a150_read_only_head_snapshot` adapts the A150 real LAB
  `read_head` to this format; the adapter is not a trust authority.
- `FloorClaim(ledger_id, epoch, sequence, history_digest, request_nonce, audience,
  observed_ns, valid_until_ns)`, serialized as canonical UTF-8, sorted JSON
  under a unique versioned **A161 Ed25519 domain separator**.
- `SignedFloor(claim, custodian_id, signature_b64)`, with two distinct
  mandatory roles `d1` and `d2`. A caller must pre-pin exactly the two
  public keys **outside the response**. Key reuse, missing/extra custodians,
  swapped roles, malformed signatures and a single matching signature fail.
- `verify_dual_floor`: both signatures must independently validate over the
  EXACT same claim. It binds the expected nonce, expected ledger, epoch,
  hardcoded read-only audience, freshness timestamps and a maximum
  30-second signed validity window. It rejects stale/replayed nonce,
  time-in-the-future, expired attestation and invalid inputs.
- `assess_restart_dual_floor`: compares the local head with the signed
  floor, but **NEVER produces a GO status**.

| Evidence scenario | Read-only result | Meaning |
|---|---|---|
| Local sequence lower than the newest preserved custodian floor | `LAB_HARD_BLOCKED` | A local rollback is detectable **under independent-custodian assumption** |
| Local sequence greater than signed floor | `LAB_HARD_BLOCKED` | Unknown unwitnessed local advance; NO automatic repair/resend |
| Equal sequence, different digest | `LAB_HARD_BLOCKED` | History divergence |
| Missing, unsigned, one signer, invalid key, stale nonce, expired proof | `LAB_HARD_BLOCKED` | Not acceptable evidence |
| Equal sequence and digest, two valid signatures + fresh nonce | `LAB_QUARANTINE_MANUAL_REVIEW` | Cryptographic mathematical consistency only; no external authority proven |
| **Joint rollback of local DB + both custodian histories and keys, then fresh signing** | `LAB_QUARANTINE_MANUAL_REVIEW` | **Critical negative counterexample:** valid signatures CAN NOT independently detect this attack |

The last row is **intentional**: the two signers in this LAB are simply
temporary Ed25519 keys owned by one test process. Even with two signatures
over a fresh nonce, if their state/custody is rolled back too, the freshness
claim is not authoritative. A161 *does not use* role IDs as proof of
organizational or geographic independence. The request nonce itself
has no durable anti-replay value unless a requester outside the shared
rollback domain persists fresh challenge state. The timestamp uses a
test-injected clock, not an attested real clock. There is no real network.

No function stores keys, records, requests, SQLite, effects or receipts.
Every returned `FloorReview` includes immutable false flags:
`externally_independent_custodians_verified`,
`nonrollbackable_external_floor_proven`,
`owner_identity_verified`,
`real_provider_effect_proven`,
`checkpoint_restoration_authorized`,
`external_execution_allowed`, `worker_allowed`,
`automatic_resend_allowed`, with `homologated_p0_count=0`.

## Targeted adversarial evidence (not a substitute for real custodian)

- `tests/test_aion_p0_a161_dual_custodian_floor_lab.py`: **70 new tests**,
  including 50 explicitly named scenarios +20 malformed claim mutations:
  bad nonce and replay, wrong epoch and ledger, two valid but conflicting
  signatures, swapped authority, signer/key substitution, missing d2,
  expired/long floor, unequal digest or sequence, co-rollback detection with
  out-of-band newer floor, and the **two compromised signer counterexample**.
- Uses actual A150 LAB genesis/read-only head once, ephemeral Ed25519 keys,
  temporary SQLite and zero provider network.
- `tests/run_aion_a161_dual_custodian_counted_lab.py`: exact count/zero
  skips/no errors required. CI Windows+Ubuntu runs **716 existing A145–A160
  tests +70 new = 786 per OS**, for a planned **1,572 individual test
  executions** if both fully pass.
- Independently rechecks strict YAML source guards, real recovery/writer
  denial, the E0–E5 documentary evidence gate and the 32 historical external
  provider evidence errors. Documentary checks are NOT provider proof.
- The test/CI count is **a target until actual Actions logs confirm it**.

## What must happen outside code before AION H0 could be signed off

1. **Independent custody:** obtain two genuinely different administrators,
   accounts and key custody domains with audited restrictions, independent
   durable monotonic storage, tamper-resistant failure recovery, explicit
   owner enrollment and key rotation/revocation.
2. **External freshness**: an actual remotely challenged, signed head from
   those custodians with verifiable response provenance and irrevocable
   sequence advancement; a genuinely independent source of time/nonce
   freshness and documented outage behavior.
3. **Real H0 reboot/restore**: prove first-uncertain-effect reconciliation
   against the *actual* provider and authoritative receipts. A witness
   CAS receipt is NOT a provider COMMITTED_EFFECT or NO_EFFECT_FENCED receipt.
4. **Closure of canonical P0 acceptance:** historical 32 provider errors
   (23 enrollment, eight causal receipts, one terminal no-effect),
   HUMAN_OWNER/FIDO2 proof, the two SQLite compatibility issues,
   Quality/Security coverage and documented owner signoff.
5. **Financial and operational approvals:** explicit owner authorization
   and observed FinOps budget before provisioning any real external service.
   This PR does not ask for enrollment, keys, APIs, paid accounts or merge.

**No amount of green self-signed LAB tests replaces external witness custody.
Remain HARD NO-GO, ZERO_AUTO_RESEND, 0/6 P0.**
