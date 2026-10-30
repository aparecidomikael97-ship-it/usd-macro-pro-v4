# A294 — Volatile independent-process SQLite witness simulation (LAB)

**HARD NO-GO**: no integration, merge, production Worker, deployment,
order execution, third-party sends, new paid service or automatic resend.
**P0 homologated: 0/6.** Standard-library temporary files and a local child
process only. The witness has **NO** actual off-host custody.

## What A293 showed

A previously valid SQLite database can replace newer committed history
while closed. A fresh `SQLiteChatStore(strict_local_data_version=True)`
still opens it and reports healthy, because its `PRAGMA data_version`
baseline is new and the local pre-COMMIT marker has gone.

## A294 experimental protocol

The laboratory launches a **separate local Python process** through
`subprocess.Popen` and exchanges JSON lines over private pipes. The child
creates an ephemeral `secrets.token_bytes(32)` HMAC key and maintains
only its current in-memory commitment. The key is not exported.

The client computes SHA-256 over canonical, sorted rows of these
SQLite semantic tables: `conversations`, `messages`, `records`.
We hash their actual content, **not** bytes of the SQLite database or
journal/WAL, which may change after checkpointing without semantic changes.

A witness record contains:

| Field | Meaning |
| --- | --- |
| `seq` | Monotonically increasing anchor counter |
| `digest` | SHA-256 of current semantic database tables |
| `previous` | Prior receipt head, or `GENESIS` for first |
| `mac` | Child-local HMAC over version, seq, digest, previous |
| `head` | SHA-256 of version, previous and MAC |

The child refuses unrecognized operations, invalid digests, reused or
out-of-order sequence numbers, wrong parent heads, modified receipts,
stale receipts and snapshots different from its **latest** anchor.

Verification is performed **explicitly** in this LAB; the existing
`SQLiteChatStore` is **not** changed to depend on it.

## Experiments and expected outcomes

1. **Rollback with active witness:** anchor a committed message, replace
   the closed DB with older valid bytes, and verify. SQLite's own strict
   health check is green, but the child returns `SNAPSHOT_MISMATCH`.
2. **Monotonicity and receipts:** a repeated anchor, wrong parent, forged
   HMAC or old receipt is rejected. Updated history requires an explicitly
   authorized new anchor; nothing is automatically resent.
3. **Witness killed:** the client returns `WITNESS_UNAVAILABLE` and must
   deny rather than fabricate verification.
4. **Witness restarted under host control:** it has forgotten both its
   state and secret. The prior receipt fails against the empty child,
   **but** an improperly trusted new `GENESIS` bootstrap can anchor
   the rolled-back database and make the old state appear current again.
   This is a deliberate negative finding, not a passed security claim.

## Security caveats that remain P0 blockers

- Both child and SQLite run under the same host. A privileged attacker can
  terminate/replace the child, intercept its pipes, change or extract its
  HMAC key, control bootstrap, or simply bypass verification.
- An HMAC signed inside a process controlled by the same trust domain is
  **not an external signer, independent owner approval, cryptographic
  custodian, or durable witness**.
- No durable append-only off-host storage, key rotation, multi-signer
  quorum, recovery authority, native SQLite VFS/FD binding, or atomic
  evidence linking an authorized intent to a business effect.
- The simulated `anchor` operation trusts the caller's claim that a
  transition is authorized. That caller is not authenticated. A production
  design must solve authorization, antirollback bootstrap, and durable
  external custody before it could ever issue a GO.
- Fail-closed results are properties of this test protocol only; they
  **do not enforce** any gate on the current AION application.

## Commands

```bash
python -m unittest -v labs.test_a294_volatile_witness_sim_lab
python -m unittest -v labs.test_a293_host_sqlite_boundary_lab
python -m unittest -v labs.test_a292_staged_chat_write_inventory_lab
python -m unittest -v labs.test_a291_chat_write_gate_commit_fence_lab
python -m unittest -v labs.test_a290_sqlite_local_write_gate_lab
```

GitHub Actions executes the isolated A294 and stacked A293–A290 suites on
public standard Ubuntu/Windows runners using Python 3.12. No third-party
packages, provider credentials, network endpoints, live data or chargeable
service is required.

**Outcome gate:** GO-LAB on green unit tests only; NO-GO integration and
HARD NO-GO operation remain. **P0 homologated 0/6.**
