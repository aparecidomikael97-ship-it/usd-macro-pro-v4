# AION P0 — A147 crash/restart, fail-closed, LAB ONLY

## Scope and evidence

A147 is a deliberately isolated **synthetic** journal; it does not represent
the H0 production gateway, payment provider, Global Worker, trusted witness
or HUMAN_OWNER consent protocol. Review of this component MUST NOT raise the
number of homologated P0 items.

- Draft PR: [#1431](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/pull/1431), stacked on #1430 and #1429.
- Candidate: `lab/aion-p0-a147-sqlite-crash-reconcile-20261022`.
- Counted runner: `python -B tests/run_aion_a147_counted_lab.py`.
- TEST_COUNTS: A145 4+12+10, A146 20+13, A147 50 = **109 tests per operating system**.
- CI evidence on commit `ef43c5275e4e605e909c512163d109257ec0fcba`:
  [pull_request run #39708852978](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39708852978).
  Both Windows and Ubuntu counted jobs returned SUCCESS with 109/109.

## Explicit safety invariants

1. **No implicit genesis:** only `bootstrap_synthetic_lab` creates a
   journal; normal startup uses SQLite `mode=ro` and rejects missing data.
2. **Strict schema/policy:** unexpected tables/triggers/indexes, foreign
   `application_id`, changed owner ledger identity or broken sequence
   cause a reject. No automatic schema repair.
3. **Durable uncertainty:** a locally committed first intent remains
   `RESERVED_UNCERTAIN` after restart; it is not a provider receipt.
4. **No second uncertain local intent:** additional intents are rejected
   while the first remains unresolved. Same intent is not inserted twice.
5. **No automatic resend or real effect:** neither the journal nor recovery
   decision includes a provider client, execution gateway or send interface.
6. **Read-only recovery decision:** even when the signed checkpoint and
   signed highwater agree, status is `LAB_QUARANTINE_MANUAL_REVIEW`,
   **never** external permission. Any invalid/missing evidence is
   `LAB_HARD_BLOCKED`.
7. **LAB runtime enforcement:** methods fail if `AION_LAB_MODE!=1`.
8. **Independent key material is necessary but insufficient:** A145 signs
   checkpoints; A146 signs highwater with a *different* pinned Ed25519
   public key. Key ownership, freshness and independent custody are not
   established by signatures alone.

## Tested crash boundaries

| Boundary | LAB observation | Safety decision |
|---|---|---|
| Process killed **before** SQLite COMMIT | Uncommitted insert is absent on reopen | No effect proved; no external authorization |
| Process killed **after** SQLite COMMIT, witness unchanged | Committed intent survives; witness is behind | HARD BLOCKED; no resend |
| Local COMMIT + synthetic witness update both completed | State and signatures match | QUARANTINE; provider effect still UNKNOWN |
| Signed witness ahead, SQLite reverted | Sequence mismatch | HARD BLOCKED |
| Signer key replaced / envelope altered | Signature verification fails | HARD BLOCKED |
| Witness missing, unavailable or raises | Cannot prove freshness | HARD BLOCKED |
| Concurrent writers (same or distinct run IDs) | Only first uncertain intent admitted | No concurrent second critical reservation |
| Old SQLite **and** synthetic witness jointly restored | Old signed pair can appear consistent | **NEGATIVE proof: real anti-rollback is NOT solved** |
| Database deleted, then manually re-bootstrapped | Synthetic genesis can be recreated | Only a NON-rollbacked external witness detects the missing history |

## Approval barriers remaining for H0 P0

These are **not complete**, and the above CI cannot certify them:

- Externally provisioned, authenticated identity of HUMAN_OWNER and
  intent-bound consent under the required security policy.
- Independent source identity, key custody and enrollment for both signing
  authorities; untrusted callers cannot nominate their own trust roots.
- Monotonic durable witness state that **cannot** roll back with SQLite,
  including device reinstall, snapshots, backups, power loss and key rotation.
- Crash consistency across the remote witness boundary: signed reservation
  receipt, at-most-once issuance, idempotency proof, authoritative reconciliation
  after uncertain response, and zero automatic resend.
- Verification of actual external provider effects independently of local
  `LOCAL_OUTPUT_OBSERVED` or a signed local history.
- End-to-end Windows reboot/hardware fault tests on the real H0 integration,
  independent reviewer evidence and explicit P0 sign-off.

## Constraints

**HARD NO-GO; 0/6 P0 homologated**. No merge, deploy, Worker, provider,
real transaction, production restore or background operation has been
authorized by this Draft PR. All keys, identities, files and timestamps
from the tests are **synthetic**.
