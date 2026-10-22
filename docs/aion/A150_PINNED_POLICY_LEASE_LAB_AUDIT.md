# AION P0 A150 — policy pin and challenge lease: laboratory audit

> **HARD NO-GO; 0/6 P0 homologated.** No merge, deploy, real Worker,
> remote witness, external provider or trading operation. All keys,
> identities, timestamps and SQLite stores are synthetic. This document
> and all A150 checks are limited to the isolated LAB.

## Evidence and exact scope

- Stack: Draft PR [#1434](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/pull/1434)
  on Draft [#1433](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/pull/1433),
  with A148/A147/A146/A145 below.
- Cumulative counted runner: \`python -B tests/run_aion_a150_counted_lab.py\`.
- Contract checks: A145 26 + A146 33 + A147 50 + A148 40 + A149 50
  + **A150 56 = 255 tests per operating system**. Zero skips/failures
  permitted; count mismatch fails the job.
- Candidate code commit: \`232a11e305ef2c1b27d712ec0e41b69ef61bef10\`.
- GitHub Actions candidate: [run #39761387792](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39761387792)
  (push) and [run #39761394187](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39761394187)
  (PR). Consult the run's final job conclusions before treating
  test count as a PASS; a queued/running job is NOT evidence of approval.

## Control 1 — operator policy pin separate from mutable SQLite

\`OperatorPinnedPolicyLAB\` is injected into \`LeasedPinnedWitnessLAB\`
by a test harness with these synthetic values: ledger identity,
epoch, permitted publisher key ID, publisher Ed25519 public key,
witness Ed25519 public key and maximum challenge lease policy.

In each LAB read/transaction, SQLite publisher identity/key, ledger,
and epoch must exactly match this in-memory pin. Witness keyfile is
also checked against the pinned witness public key BEFORE changes
to the witness SQLite.

**What it demonstrates:** isolated substitution of the enrolled
publisher key in SQLite is rejected; witness private-key swap is
rejected; same key for publisher and witness is forbidden.

**What it does NOT demonstrate:** external identity or trust. The
harness supplies the policy and an attacker controlling BOTH the
in-memory policy and SQLite can replace the authorized key. There is
no authenticated external enrollment, durable trusted key custody,
revocation or independent administrative domain.

## Control 2 — bounded, one-time challenge lease

A150's separate schema adds \`challenge_lease\` (issued_ns,
expires_ns) and a \`witness_clock\` floor. Challenge issuance,
time-floor update, challenge record and lease record commit in
ONE local SQLite transaction.

An authorized Ed25519 publication checks within \`BEGIN IMMEDIATE\`:

1. Exact SQLite schema, publisher identity and out-of-band test pin.
2. Witness keyfile matches the pinned witness key before writing.
3. Clock value is a positive, strictly-typed 64-bit-ish nanosecond
   integer and must not regress below the persisted local floor.
4. Challenge lease exists, is unconsumed, and
   \`issued_ns <= now_ns < expires_ns\`.
5. Expires-issued interval exactly equals the operator-pinned lease
   duration (1 to 300 seconds, normally 30).
6. Signed request binds ledger, epoch, publisher, challenge,
   request ID, expected sequence/digest, next sequence/digest.
7. CAS, consumed challenge, witness sequence/digest, local clock floor
   and publication receipt commit as one SQLite transaction.

After an ambiguous acknowledgment, the only safe local operation is
\`read_receipt(request_id)\`: it does NOT resend or infer external
effects. A successful witness receipt is **not** a provider-effect
receipt.

## Tested boundaries

| Attack / fault | A150 LAB behavior |
|---|---|
| Forged publisher key/signature | Denied |
| SQLite publisher key mutated; operator pin unchanged | Denied |
| Witness private key swapped; operator pin unchanged | Denied BEFORE mutation |
| Challenge reused after consumption | Denied |
| Challenge replay at or after exact lease deadline | Denied |
| Lease interval changed from 30 to 15/60/301 seconds | Denied |
| Operator pin for duration doesn't match runtime | Denied |
| Clock rewinds below committed local floor | Denied |
| Missing lease or orphan lease record | Denied |
| Unexpected trigger / schema deviation | Denied |
| Competing same-sequence writers | At most one succeeds in test |
| Signed receipt fetched after restart | Read-only, no CAS performed |
| Witness SQLite snapshot restored | **NEGATIVE:** prior state can reappear |
| Operator policy AND SQLite replaced together | **NEGATIVE:** attacker-controlled key may become accepted |
| Both issued_ns and expires_ns shifted together | **NEGATIVE:** even an exact-duration pin does not detect time shift |
| Local clock forged inside allowed interval | **NEGATIVE:** local time cannot attest actual elapsed time |
| A149 unchanged API | Separate synthetic legacy engine; not a production integration |

## Further P0 H0 blockers (mandatory)

- Trusted HUMAN_OWNER binding and critical-action Windows Hello/FIDO2
  consent with verifiable provenance/nonce.
- Issuer identity enrollment, independent key custody, multi-party
  policy pin, revocation and signed key rotation.
- Independently attested time and/or a monotonic lease mechanism
  resistant to local clock rewinds, snapshots and metadata changes.
- Real external witness with durable append-only or hardware-backed
  nonrollbackable state in a **distinct administration/failure domain**.
- Prove crash consistency, authorized publisher, uncertain first
  operation, authoritative provider-effect reconciliation and
  **ZERO AUTO RESEND** on real integration topology.
- Independent adversarial review and Windows H0 restart/failure
  exercise on the actual deploy environment.

**A150 is NEVER an authorization for real execution.**
