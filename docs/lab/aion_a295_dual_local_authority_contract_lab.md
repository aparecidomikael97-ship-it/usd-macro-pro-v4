# A295 — Dual local signer / authority contract (isolated LAB)

**Gates:** HARD NO-GO operation, NO-GO integration, 0/6 P0 homologated,
ZERO_AUTO_RESEND. No Worker, deploy, provider sends, real trades, new paid
services or changes to the production AION store.

This is an **untrusted simulation**, not an independent-authority
implementation. Its two roles are local child Python processes launched via
A294's volatile witness. Each process creates its own ephemeral HMAC key.
Both keys and processes remain under the same host operator's control.

## Exact synthetic approval envelope

The pure stdlib model validates the following fields with exact presence,
type and bounded length:

| Field | Constraint |
| --- | --- |
| `schema` | Versioned A295 schema |
| `intent_id` | Nonempty bounded identifier |
| `scope` | owner, tenant, workspace strings |
| `action` | Only `CHAT_CHECKPOINT_LAB`; live sends/orders forbidden |
| `payload_digest` | Lowercase 64-digit SHA-256 |
| `history_digest` | SHA-256 of A294's semantic SQLite snapshot |
| `epoch` | 32 hex digits for one simulated local lifecycle |
| `sequence` | Positive monotonic integer |
| `previous_head` | Prior joint head or initial `GENESIS` |
| `nonce` | 32 lowercase hex digits |
| `expires_at` | Future integer UTC Unix seconds; at most 300 seconds ahead |

The entire validated envelope is canonically hashed with SHA-256.
Both independent local child processes must anchor **the identical hash**,
each with its own prior HMAC receipt head. The coordinator derives a
separate joint head binding the two receipts.

The model refuses missing local approval flags, wrong epoch, stale sequence
or parent, nonce replay, repeated semantic effects, expired intents,
mismatched payload/history digest, tampered receipts and unavailable signers.

## Why the proof does NOT close an AION P0

This contract deliberately contains four negative experiments:

1. **Missing second signer:** no approval; neither child is asked to sign.
2. **One signer dies mid-approval:** the first may have anchored, the
   second cannot; mark the coordinator sticky-FAILED. No retry, no
   presumed rollback and **ZERO_AUTO_RESEND**.
3. **Both local signers reset:** they lose HMAC secrets, signed receipts,
   nonce and semantic-effect memory. If the attacker reuses the old
   simulated epoch, the same intent can be re-approved as a fresh genesis.
   The new receipts differ and old receipts cannot be authenticated.
4. **False owner flag:** a caller supplies `owner_approved=True` and
   `custodian_approved=True` for a self-claimed unauthorized owner.
   Local structural verification can return success. This **proves**
   that booleans and process labels are NOT independent user consent,
   identity attestation or protected authority.

These are negative test findings; an `ok: true` return from two
same-host Python processes is never a real authorization token.

The semantic-effect dedupe only covers exact digest/scope/action tuples
for the current process lifecycle. It is neither an external dedupe
service nor a semantically complete idempotency key.

## Unsolved design requirements

An actual authority gate would additionally need, at minimum:

- Distinct independently controlled owner/authority roots of trust,
  verifiable public-key identities and protected approval UX.
- Durable, append-only off-host epoch and nonce/intent history, with
  authenticated bootstrap/rotation and recovery without rollback.
- An atomic binding between specific approved intent, SQLite/native
  file/VFS identity, actual external effect and acknowledgement.
- Correct failure reconciliation on loss of one partial signature or
  COMMIT ACK; never confuse unknown with known failure.
- Strict production integration and canonical P0 security evidence.

None is delivered in A295. The simulator does not intercept any real
AION operation or authorize Worker/deploy.

## Repeat tests

```bash
python -m unittest -v labs.test_a295_dual_local_authority_contract_lab
python -m unittest -v labs.test_a294_volatile_witness_sim_lab
python -m unittest -v labs.test_a293_host_sqlite_boundary_lab
python -m unittest -v labs.test_a292_staged_chat_write_inventory_lab
python -m unittest -v labs.test_a291_chat_write_gate_commit_fence_lab
python -m unittest -v labs.test_a290_sqlite_local_write_gate_lab
```

The draft A295 GitHub Actions workflow runs these suites on Ubuntu and
Windows, Python 3.12 standard library. All data and signers are temporary
local simulations. No new subscription, credentials, deployment or
production service is used.

**Verdict after green tests: GO-LAB only; NO-GO integration;
HARD NO-GO production; P0 0/6.**
