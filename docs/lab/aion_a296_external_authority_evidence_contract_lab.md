# A296 — Independent authority evidence contract, negative-proof ledger

**LAB only. HARD NO-GO real operation, NO-GO integration.**
**P0 homologated: 0/6.** No paid service, Worker, deploy, real order,
provider send, third-party signature or key registration. No production code
changed. This laboratory is not a procedure for granting permission.

## Why A296 exists

A292–A295 demonstrated seven concrete reasons **local** SQLite and
same-host signer controls cannot be considered independent authority.
A295's two-HMAC-signer simulation may produce syntactically plausible
receipts, but caller-controlled booleans are not a person's consent,
and an attacker can reset both local signers.

A296 therefore defines **eight additional research sub-obligations**.
These are **NOT** a relabeling or homologation of the project's six
canonical P0 items.

| A296 sub-obligation | External evidence a future reviewer would need |
| --- | --- |
| Independent owner identity | Demonstrably separate owner key custody, trusted registry and human consent |
| Independent custodian identity | Distinct externally controlled trust root and verified public identity |
| Cryptographic intent binding | Verifiable owner/scope/action/payload/history/nonce/expiry/sequence binding |
| Durable off-host epoch and nonce | Unforgeable monotonic epoch, nonce reuse and incident reopening history |
| Atomic effect and ACK receipt | Provider/DB effect bound to authorized intent with unknown-ACK reconciliation |
| Native SQLite VFS/FD authentication | Authenticated native handle/file identity beyond a pathname stat |
| Host-resistant antirollback witness | Independent durable record that survives local file/key reset |
| Independent uncertain-outcome recovery | Authorization before resumption; no guessed rollback or automatic resend |

## The intentionally narrow evaluator

`labs.a296_external_authority_evidence_contract_lab` validates the
**shape** of a proposed evidence pack:

- Exact versioned fields, eight named obligations, no duplicates or
  missing entries, typed bounded identifiers.
- Common subject/history-epoch SHA-256 binding, unique nonces,
  short evidence validity windows.
- Claimed separate issuer and verifier roles, rejecting
  `same_host`, `self_attested`, identical issuer/verifier,
  wrong domains and malformed signature shapes.
- Base64 encoding of 64-byte signatures labeled `Ed25519`
  (format only; **NO cryptographic signature verification**).

An important test fabricates all eight proofs using **64 arbitrary bytes**
per signature and plausible role labels. The pack is structurally
complete: **8/8 shapes**. But the result is intentionally:

- **0 authenticated obligations**;
- **0 verified cryptographic signatures**;
- **0/6 P0 homologated**;
- **HARD NO-GO, no Worker/deploy/real send permission.**

Even a sophisticated all-green JSON response cannot configure a trust root
or prove custody. The evaluator has **no independent public-key registry,
hardware trust, trusted issuer, actual third-party verifier or external
effect receipt**. It never emits a production GO under any input.

## Seven exercised counterexamples, not fabricated P0 evidence

A296 reruns actual previous LAB probes and records:

1. A292: direct same-process SQL helper COMMIT bypasses the marker.
2. A293: another process changes SQLite while default-mode reads continue.
3. A293: host replaces a closed DB with valid older history, accepted as healthy.
4. A294: volatile witness reset can re-anchor old history.
5. A295: one signer may acknowledge while the other fails.
6. A295: caller-set local owner Boolean accepts a false owner claim.
7. A295: resetting both same-host signers permits the same semantic intent again.

All seven are **negative security observations**. Passing the tests means
the contract did not conceal those failures; it does **not** mean the
underlying system is secure against them.

## Engineering acceptance conditions for a future A297+

Before any attempt at canonical P0 closure:

1. Obtain and independently verify a real owner-controlled root and a
   separate custodian identity. User consent and enrollment are required;
   do not provision credentials or spend money without authorization.
2. Establish durable, externally stored antirollback/epoch evidence and a
   recovery process that cannot be reset by this host.
3. Demonstrate atomic intent-to-effect receipt binding on the actual
   native SQLite/VFS/provider boundary, with a lost-ACK test.
4. Red-team owner impersonation, dual-signer reset, file replacement,
   incident reopening, semantic duplicate effect and provider ACK loss.
5. Run canonical Security/P0 suites; independent reviewer must examine
   evidence. Local LAB green alone is insufficient.

## Reproduce

```bash
python -m unittest -v labs.test_a296_external_authority_evidence_contract_lab
python -m unittest -v labs.test_a295_dual_local_authority_contract_lab
python -m unittest -v labs.test_a294_volatile_witness_sim_lab
python -m unittest -v labs.test_a293_host_sqlite_boundary_lab
python -m unittest -v labs.test_a292_staged_chat_write_inventory_lab
python -m unittest -v labs.test_a291_chat_write_gate_commit_fence_lab
python -m unittest -v labs.test_a290_sqlite_local_write_gate_lab
```

The isolated draft PR has Ubuntu/Windows Python 3.12 standard-library
GitHub Actions only. No network call to issuers, no real credentials or
production workload. **GO-LAB on passing regression only; HARD NO-GO
production regardless of evidence-pack contents.**
