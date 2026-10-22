# AION A162 — Three-source H0 restart evidence correlation (LAB NO-GO)

**2026-10-22 · LAB / PR Draft · NO LIVE EXECUTION · 0/6 P0 homologated · HARD NO-GO**

## Gap after A161

The first uncertain provider operation has multiple relevant local representations:
- **A147 SQLite**: durable LOCAL `RESERVED_UNCERTAIN` intent sequence, never a supplier effect.
- **A145 checkpoint / A150 witness**: a locally signed checkpoint and a local lease/clock/CAS witness; the A150 signer and SQLite still share one recoverable domain.
- **A161 dual signed floor**: two mathematically verifiable Ed25519 attestations over exactly one ledger/epoch/nonce/current-head claim; test keys belong to one synthetic operator and are NOT independently administered.

Each subsystem had its own focused negative tests, but no **single read-only gate** required their histories and digests to agree during one synthetic H0 restart. A147 can be ahead of A150 if the local reservation committed before the witness acknowledgment, or A150 can be ahead of A147 if the local journal was rolled back. Either is an **unknown state** and must NEVER promote a retry or automatically repair/rebootstrap.

A162 introduces `aion_p0_a162_three_source_recovery_lab.py::assess_three_source_restart`, a strictly synthetic cross-source inspection. It does **not** change any operational restore or writer method.

## Enforcement rules

1. Requires `AION_LAB_MODE=1`, `AION_WORKER_ENABLED=0`, `AION_EXTERNAL_EXECUTION_ENABLED=0` and exact A147 and A150 LAB engine classes. This is not an IAM boundary or host isolation proof.
2. Requires the expected ledger identifier to bind to A147, A150 policy and the A150 head; the epoch must match A150's caller-provided pinned policy. A147 does NOT natively store an epoch.
3. Validates **five unique public key roles**: signed A145 checkpoint, A161 d1 and d2 external role identifiers, local A150 publisher and local witness. Refuses missing/extra checkpoint or d1/d2 pins, same-byte key reuse and malformed bytes. Distinct keys are **NOT distinct organizations**.
4. First read A147 events and A150 head, and require a valid signature over the A145 checkpoint that matches the exact A147 event sequence/digest. Compare the signed checkpoint sequence/digest against A150, and compare A150 against locally recalculated A147 history digest.
5. Verify A161's Ed25519 d1 and d2 pair, exact ledger/epoch/nonce/audience, bounded synthetic observation window, sequence and SHA-256 digest against the A150 local head. Any floor disagreement, unobserved local advance, malformed signature, stale nonce or expiry is **LAB_HARD_BLOCKED**.
6. Re-read A147 and A150. A detected intervening change or read outage is **LAB_HARD_BLOCKED**, not automatic retry. This simple double read is NOT a distributed transaction or race-proof concurrent snapshot.
7. Even if every representation matches, the result is **LAB_QUARANTINE_MANUAL_REVIEW** (first uncertain local reservation still requires actual provider effect/no-effect evidence; genesis still needs real enrollment). No `GO`, `READY`, `RESTORE_AUTHORIZED` or `RETRY` value exists.
8. All returned dataclass authority flags are explicitly false: independent issuer, non-rollbackable floor, verified owner, provider `COMMITTED_EFFECT` and `NO_EFFECT_FENCED`, restore authorization, external effect, Worker, automatic retry/resend, and `homologated_p0_count=0`.

## Tests and results

New:
- `tests/test_aion_p0_a162_three_source_recovery_lab.py` — **70 new adversarial cases**, 50 explicit and 20 invalid-input variations.
- Real synthetic SQLite A147 + A150 with two other signed sources and five ephemeral keys. Cases include pre/post local reservation, valid but stale checkpoint, mutated SQLite schema/ledger, A150 witness missing, key substitution/reuse across *all* trust roles, d1/d2 disagreement, d1/d2 ahead or behind, nonce replay and expired claims, double-read TOCTOU, disabled LAB/Worker/external flags and explicit co-rollback negative proof.
- `tests/run_aion_a162_three_source_counted_lab.py` enforces exactly 70 with **no failure/error/skip**.
- CI Windows/Ubuntu also requires prior A145–A161 **790** counted regressions per OS (70 A161 + 30 A160 +259 A145–A150 +20 A151 +55 A152 +48 A153 +73 A154 +78 A155 +90 A156 +67 A157). **Target: 860 tests per OS; 1,720 total executions**, plus A154/A156/A157 static NO-GO and the historical 32 producer-proof blocking errors.
- **A151 CI negative finding and correction:** first CI run discovered that the repository's static LAB-import barrier only recognized A145–A150. The new A162 experimental root module was therefore (correctly for its old configured scope) treated as non-LAB source importing A145/A147/A149/A150. Instead of silencing A151, this PR extends its **explicit prefix rule** to A161 and A162 and adds four tests: runtime imports of A161/A162 are denied, an explicitly named root A162 module is accepted, and a nested deploy/ copy remains denied. A151 now enforces **20 exact tests**, not 16. Existing A151 protection is preserved and broadened. Original failure [Actions #39822359745](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39822359745) is retained as evidence. 
- These numbers are **targets until real Actions logs confirm them**. Green local synthetic tests are not independent issuer enrollment.

## Co-rollback impossibility counterexample remains

An attacker who can snapshot/restore the **A147 database, A150 witness and its policy/key**, along with both **synthetic d1/d2 custodian histories and private keys**, can produce a set of mutually matching *old* evidence with valid signatures and a fresh test nonce. A162 returns **LAB_QUARANTINE_MANUAL_REVIEW** rather than a false clear; it cannot know the real world advanced in the meantime.

The actual requirements for a real exit gate remain independently operated and authenticated nonrollbackable head custody with revoked/rotated keys, proven HUMAN_OWNER approval, protected challenge freshness, real H0 reboot/first-effect reconciliation, actual supplier-issued causal receipt, and an authoritative terminal no-effect fence. The 32 historical provider-proof errors (23 pre-adapter enrollment, eight causal effect receipts, one terminal no-effect) are still open. No test-only issuer is real proof.

**No merge, deploy, external keys, provisioning, credential enrollment, Worker, live payment/trade/provider send, automatic retry, or expense authorized. HARD NO-GO / ZERO_AUTO_RESEND / 0 OF 6 P0.**
