# AION H0 A164 — Independently preserved revocation policy floor: synthetic proof and impossibility example

**Date:** 2026-10-22.  
**Status:** isolated LAB, PR Draft stacked on A163, **HARD NO-GO, 0/6 P0 homologated**.

## Confirmed gap in A163

The A163 synthetic policy ceremony requires signer-correct Ed25519 ENROLL, ROTATE and terminal REVOKE_ALL events. It detects reuse of retired keys, old signed floors, forked sequence/digest and stale local `PolicyAnchor` when that anchor remains newer than the restored policy.

**But an attacker who can restore BOTH** the complete A163 signed policy and its caller-provided `PolicyAnchor` can make an old, never-revoked generation appear current. Existing A163 adversarial test #47 explicitly demonstrated this. The H0 recovery still must never be authorized, even when mathematics agrees.

The A164 gate models what *would* detect that joint rollback **if a separately controlled and provably nonrollbackable external authority retained the latest generation and terminal revocation state**. The implementation intentionally does not claim any such real authority exists.

## A164 read-only protocol (no real witness)

`aion_p0_a164_independent_revocation_floor_lab.py` defines:
- `RevocationFloor` containing ledger identifier, epoch, policy generation, exact A163 signed-chain SHA-256 digest, **terminal_revoked boolean**, fresh challenge nonce, fixed read-only audience, synthetic observation/expiry timestamps (maximum 20 seconds).
- Domain-separated canonical JSON serialization under `AION-P0-A164-REVOCATION-POLICY-HEAD-v1` to exclude accidental use of A161/A163 signatures for A164.
- `SignedRevocationFloor` from exactly two separately named reviewer roles **R1 and R2**, each verified with caller-supplied **pre-pinned** Ed25519 public keys. Rejects role swaps, missing/extra pin, same signing key for both reviewers, missing/malformed/forged signatures, mixed floor claims, mismatched ledger/epoch/nonce, expired/future claim and overlong expiration.
- Refuses key reuse between R1/R2 and A163 policy **issuer or D1/D2**, including D1/D2 keys already retired in the signed A163 history. Distinct key bytes do **not** establish independent administrators or custodian organizations.
- `assess_external_revocation_floor` first validates the existing signed A163 chain against its local anchor, then verifies BOTH independent-looking signatures over one floor. Differences **BLOCK**, even if each input looks internally valid:
  - A163 generation *lower* than externally signed floor → `LAB_HARD_BLOCKED`: restored policy + local anchor could have rolled back together.
  - A163 generation *higher* than signed floor → `LAB_HARD_BLOCKED`: unexplained unwitnessed local policy advance; no automatic repair.
  - Equal generation, different chain digest → `LAB_HARD_BLOCKED`: same-generation policy fork.
  - Equal generation/digest, disagreeing terminal revoke flags → `LAB_HARD_BLOCKED`.
  - Fully matching and signed **REVOKE_ALL** → `LAB_HARD_BLOCKED` even if an old key still signs.
  - Fully matching, active latest chain → delegate to existing A163+A162 read-only H0 verification; the strongest possible result is `LAB_QUARANTINE_MANUAL_REVIEW`. Missing or contradictory checkpoint, witness or supplier causal receipt still blocks real effect.
- Every result asserts false values for independent external auditor custody, irreversible policy floor, actual HUMAN_OWNER/FIDO2 consent, real supplier effect, restore authorization, automatic replay/resend, external execution, Worker and `homologated_p0_count=0`.

**No method enrolls, revokes, persists, or sends any real key, secret or request.** The module only reads synthetic signed values, local A147/A150 test stores and existing A163+A162 read-only checks.

## Critical negative proof: two synthetic auditors can collude

A163 test #47 already showed that restoring the policy and its local anchor together can make expired keys look valid. A164 includes:
- **Positive conditional detection**: keep a *newer* R1/R2-signed policy floor representing a ROTATE or REVOKE_ALL, then restore an older A163 policy **and its old anchor**. A164 blocks on `local_policy_and_anchor_rolled_back_below_signed_floor`. This is a conditional observation, not proof that production can retain such a floor.
- **Impossibility/collusion counterexample:** the same test process controls both R1/R2 private keys, so it can sign an **old policy floor with a fresh nonce** after a newer rotation or revocation has actually been simulated. The old policy and anchor then match that false evidence; A164 returns **quarantine only**, **never GO**. There is no cryptographic substitute for independent, authentically enrolled, nonrollbackable revocation custody.

Even if all A164 tests are green, this does NOT provide remotely attested freshness or delivery/acknowledgement of a revocation order.

## Exact tests and static separation

- `tests/test_aion_p0_a164_independent_revocation_floor_lab.py`: 80 cases (60 explicit + 20 malformed input mutations) that use actual *disposable* A147 journal, A150 witness and A163 fixture/signatures. They cover generation ahead/behind, active/revoked divergence, wrong D1/D2, R1/R2 cross-role key reuse, signed signature mismatch, nonce replay, old policy/anchor rollback, explicit auditor collusion, missing real SQLite witness, and full NO-GO flags.
- Counted runner `tests/run_aion_a164_revocation_floor_counted_lab.py` fails on changed count, any skip, failure or error.
- A151 static runtime import boundary extended only to the explicit root experimental A164 module. Four new negative regressions ensure production `runtime/`, `services/`, `deploy/` or dynamic imports cannot quietly invoke it. A151 becomes **28** tests, while genuine H0 modules remain prohibited from importing A145–A164 experimental internals.
- CI matrix Windows and Ubuntu: **80 A164 + 80 A163 + 70 A162 + 70 A161 + 30 A160 + 259 A145–150 + 28 A151 + 55 A152 + 48 A153 + 73 A154 + 78 A155 + 90 A156 + 67 A157 = 1,028 tests per platform**; **2,056 executions total** when both pass. Also reruns A154/A156 real-writer/restore deny, A157 workflow YAML/credential policy, A152 E0–E5 and the **32 historically missing external provider proof obligations**. The 32 remain OPEN even when their crosswalk test passes.
- These counts describe the requested CI gate, NOT a proven green result until GitHub Actions actually completes and its logs are inspected.

## External acceptance requirements remain unchanged

AION's H0 must still have verified HUMAN_OWNER identity/consent, genuinely separate enrolled R1/R2 and D1/D2 administrations, an authoritative persisted monotonic and nonrollbackable policy floor, demonstrably propagated revocation, fail-closed key compromise/recovery, and real provider-issued `COMMITTED_EFFECT` or terminal `NO_EFFECT_FENCED` outcomes, plus closure of the outstanding SQLite P0 and 32 provider evidence errors.

Any new real custodians, paid accounts, cryptographic material, resource provisioning, automation execution, deployment or main-branch merge requires explicit human-owner approval. No such activity is performed here.

**HARD NO-GO · ZERO_AUTO_RESEND · 0/6 P0 · Worker OFF · no merge/deploy/gasto.**
