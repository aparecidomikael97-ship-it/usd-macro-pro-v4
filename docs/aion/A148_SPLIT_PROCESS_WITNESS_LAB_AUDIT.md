# AION P0 A148 — split-process witness: evidence and open threats

**Classification:** synthetic isolated LAB. **HARD NO-GO; 0/6 P0 homologated.**

## Scope and verifiable results

- A145: threat model 4 + checkpoint comparator 12 + Ed25519 checkpoint 10.
- A146: high-water CAS 20 + separately signed high-water 13.
- A147: SQLite crash/reconciliation 50.
- **A148: split-process SQLite witness 40.**
- Cumulative: **149 exact-count passing tests per OS**; count mismatch,
  skipped test, failure or error fails the CI gate.
- Tested on 2026-10-22 UTC: commit
  \`228fda8c97d8e67e7080bb991198c3eab8e33c8d\`;
  [GitHub Actions #39710149312](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39710149312)
  completed SUCCESS on **Ubuntu and Windows**.
- Draft PR [#1432](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/pull/1432)
  is stacked on [#1431](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/pull/1431).

## Process boundaries actually tested

\`\`\`text
                      TEST RUNNER (synthetic)
      +-----------------------+----------------------------+
      |                       |                            |
  LOCAL JOURNAL          subprocess CLI              pre-pinned
  SQLite file            via stdin/stdout           Ed25519 public key
  synthetic intent  ---> (signed high-water) --->    verifier + recovery
  unknown effect         SQLite file + signer        read-only decision
      |                       |
      +----- SAME MACHINE / SAME SECURITY ADMIN -----+
\`\`\`

The signer private key and witness SQLite reside in one mutable witness
directory. No HTTPS, external API, Worker, provider, cloud availability,
hardware root, TPM monotonic counter, authenticated client or production
key custody is involved.

A new subprocess is started for reads and publications. A CAS transaction
(\`BEGIN IMMEDIATE\`, \`PRAGMA synchronous=FULL\`) runs on the synthetic witness
SQLite, separately from the local journal. Only a matching expected sequence
can advance the in-process witness. The response is a domain-separated
Ed25519 signed high-water, validated against a caller-pre-pinned public key.

### Negative and crash evidence

| Test | Observation | Security interpretation |
|---|---|---|
| Witness process killed before commit | old high-water survives | no false ack |
| Witness process killed after commit, response lost | new high-water survives restart | no claim of remote effect / automatic resend |
| SQLite local journal commit, witness not yet updated | restart gate blocks | fail-closed uncertainty |
| Local DB restored, witness DB preserved | signed witness higher than history | old local history blocked |
| Concurrent separate process publications | only one CAS sequence wins | no two accepted seq-1 states in test |
| Witness signer key replaced | signatures no longer verify under old pin | caller-side key pin detects mismatch |
| Witness DB schema/identity tamper | read rejected | conservative validation |
| Local AND witness DB restored together | old signed state again looks internally consistent | **negative proof: not genuine anti-rollback** |
| Witness key retained while state DB reset | old data receives a valid NEW signature | **negative proof: signatures alone do not ensure freshness** |
| Unknown caller publishes valid CAS content | synthetic witness accepts it | **negative proof: publisher authentication missing** |
| Witness missing / unavailable | gate denies | NO auto-resend |

The witness \`publish\` command deliberately has **NO authenticated publisher**:
any LAB caller able to access the local process can advance it. This is
EXPLICITLY a security gap, not a feature. The caller's signed checkpoint
and the witness's independently signed high-water do not prove real issuer
identity, custody, independent storage, current epoch or provider result.

## Needed before H0 can pass a P0 gate

1. **Independently provisioned identities:** HUMAN_OWNER, checkpoint issuer,
   witness issuer and permitted publisher identities, with explicit
   externally verified enrollment, rotation and revocation.
2. **Authenticated publisher commands:** intent-bound, nonce-bound, sequence-
   bound signed requests to a witness with an independent pinned client key.
   Reject forged, altered, replayed, expired or unauthorized publication.
3. **Actual separate trust/failure domain:** witness storage and signing key
   must not be under the same snapshot/recovery authority as the local DB.
   Show denial after rollback, reinstall, key rotation and network partitions
   using an environment that cannot be reset by the local operator.
4. **Monotonicity and crash consistency:** durable high-water across real
   restarts, power loss and storage failure; handle local commit/witness ack
   uncertainty without creating, replaying or resending an external effect.
5. **Independent provider-effect evidence and real H0 integration:** an
   unknown first operation remains UNKNOWN until a trusted authoritative
   read-only reconciliation proves the actual effect.
6. **Windows end-to-end, owner approval and adversarial sign-off:** evidence
   must be collected in the actual deployment topology, not synthetic SQLite
   files in a CI runner.

## Invariants and prohibited interpretation

- No merge/deploy/Worker/provider execution/real account action.
- No successful LAB result authorizes first/second real execution.
- \`LAB_HARD_BLOCKED\` or \`LAB_QUARANTINE_MANUAL_REVIEW\` are the only
  recovery decisions; neither means business approval.
- Zero automatic resend, even on lost acknowledgment.
- **0/6 P0 homologated; HARD NO-GO.**
