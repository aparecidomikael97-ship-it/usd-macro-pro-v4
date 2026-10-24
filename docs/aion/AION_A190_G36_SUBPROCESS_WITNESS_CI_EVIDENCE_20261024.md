# AION A190 G36 — Subprocess witness custody and real Outbox restart admission

**Date:** 2026-10-24. **Exact passing tested code/workflow SHA:** `555002a8e9f52b911004f507e3d443c324217bcd`. Branch: `lab/aion-a190-g36-subprocess-custody-recovery-20261024`. Stacked on G35 Draft PR #1522. **No merge, deploy, Worker or real provider.**

## LAB implementation (not a trust claim)

- `labs/a190/g36_subprocess_witness_custody_lab.py`: separate subprocess CLI with its own local SQLite database, append-only-*by-API* monotonic sequence and hash-chained head, its own Ed25519 signing key file, and nonce-bound signature of its **latest** snapshot digest. New process per command, key persisted in its directory. The code deliberately does not implement network, external operator, real secure key provisioning, tamper-proof persistence, host isolation, or authority to authenticate the truth of a snapshot.
- `outbox_snapshot_digest(ExecutionOutbox)`: hash of a live real Outbox `list()` projection, not a transactionally serialized global snapshot with writers.
- `inspect_outbox_against_subprocess_witness`: verifies root ID, previously pinned Ed25519 public key, challenge nonce, signature, sequence, and equality of attested snapshot digest to current real Outbox snapshot. It returns only `Admission.UNCERTAIN`, **never SEND or RETRY**.
- The witness `observe` method accepts a **caller-provided digest**. A malicious host can lie. Files are all on the same host, so both copies and the key can be rolled back. Two request aliases of one business intent remain distinct. These are explicit RED tests, NOT solved.

## Verified RED / GREEN

- `G36_SUBPROCESS_MATCH_GREEN=SIGNED_TIP_ONLY_UNCERTAIN`: matching challenge-bound latest signed tip allows only UNCERTAIN.
- `G36_UNANCHORED_STATE_GREEN=UNCERTAIN_DENIED_UNTIL_WITNESS_OBSERVES`: a change to real Outbox not observed in witness fails closed.
- `G36_RESTART_GREEN=HOST_REOPEN_TIP_MATCH_ZERO_AUTO_RESEND`: a new local SQLite/Outbox handle matches retained synthetic witness tip after restart, no auto re-claim/send.
- `G36_HOST_ROLLBACK_GREEN=RETAINED_TIP_DETECTS_OLD_OUTBOX`: restore old local SQLite while retaining later witness head; mismatch denied.
- `G36_SAME_HOST_COROLLBACK_RED=DB_AND_WITNESS_OLD_STATE_ACCEPTED`: if attacker restores BOTH SQLite histories on same host, the verifier accepts old matching head as UNCERTAIN. This is the unresolved rollback gap.
- `G36_UNTRUSTED_OBSERVATION_RED=WITNESS_SIGNED_HOST_SUPPLIED_FALSE_TIP`: witness can sign a false host-supplied digest, but honest verifier comparing live outbox rejects mismatch.
- `G36_SEMANTIC_ALIAS_RED=TWO_CALLER_REFS_ONE_BUSINESS_OPERATION`: caller changes request ID, creates two local Outbox reservations, each included in a signed snapshot. No trusted semantic identity.
- `G36_PIN_RESET_GREEN=NEW_WITNESS_KEY_NOT_PINNED`: replacing witness key causes signature failure with original pin. Other tests reject nonce replay, forged signature, wrong root, missing witness and malformed observations.

## CI with exact SHA and first failure

- First run [#40127432099](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40127432099): **Ubuntu SUCCESS, Windows FAILURE** with `WinError 32` during cleanup in test 17. A `with sqlite3.connect(...) as db` committed but **did not close** the connection; Windows refused to unlink an open test database. This is a test hygiene issue, NOT a demonstrated custody bypass.
- Corrected test 17 to explicitly `db.commit()` then `db.close()` in `finally`.
- Second run [**#40127513913**](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40127513913): **SUCCESS** at exact code SHA `555002a8e9f52b911004f507e3d443c324217bcd`.
- Ubuntu job `120971996301`: **20 G36 + 18 G35 + 16 G34 + 24 G33 + 20 G32 + 18 G31 + 23 G30 = 139/139**.
- Windows job `120971996175`: **139/139**.
- **278 executions of 139 distinct tests**; no production integration or provider access.

## Independent evidence still REQUIRED

1. Witness keys provisioned and pinned independently of hostile AION host, ideally service/operator/hardware separation.
2. Append-only, non-rollback storage/monotonic source outside the host's administrative and backup/restore control.
3. Witness-side truth verification or authenticated source for reserve/first-attempt, not an arbitrary host digest; no double-send across semantic aliases.
4. Real provider-signed/independently authenticated receipt, and atomic or recoverably staged boundary between local reserve and external effect.
5. Failure behavior for missing/unreachable witness: deny SEND; preserve UNCERTAIN; no blind automatic resend.
6. Actual H0 hostile-host reboot/rollback and native SQLite identity/compatibility qualification. A184 security/Quality and dependency-audit RED were **not rerun by the G36 path-specific CI**, so no new A184 success is claimed.

**0/6 P0 homologated · HARD NO-GO · UNCERTAIN · ZERO_AUTO_RESEND. No main/merge/deploy/Worker/provider/customer secrets/spend.**
