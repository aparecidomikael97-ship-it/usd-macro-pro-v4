# A292 — Staged-chat write inventory and uncertain COMMIT ACK (LAB)

**Status:** LAB-only, pre-homologation. **HARD NO-GO** for live operation, Worker,
deploy, customer use, order routing, external sends, restore/activation and
auto-resend. No paid services; no new dependencies; synthetic data only.
**P0 homologated: 0/6.** This does **not** complete the independent external
custody, SQLite file-descriptor identity or host-resistant rollback obligations.

## What is audited

The real `aion_chat.store.SQLiteChatStore` has six semantic write entrypoints
that now use the local pre-COMMIT marker and cooperative lifecycle lock:

| API | Direct SQL or helper | Local fence |
| --- | --- | --- |
| `create_conversation` | `INSERT conversations` | `_commit_fenced_chat_write` |
| `append_message` | `INSERT messages`, then `_update` | `_commit_fenced_chat_write` |
| `archive_conversation` | `_update` | `_fenced_chat_transaction` |
| `add_attachment_metadata` | `_save_record` | `_fenced_chat_transaction` |
| `save_checkpoint` | `_save_record`, `_update` | `_fenced_chat_transaction` |
| `save_context_summary` | `_save_record` | `_fenced_chat_transaction` |

The AST inventory inspects the **exact** `SQLiteChatStore` definition. It
refuses new or changed direct `self.db.execute` DML, unresolved SQL syntax,
missing `@_local_commit_gate`, missing fence calls, or a newly introduced
`self.db.commit`/`executescript`/`backup` sink.

It is **not** a proof against arbitrary Python code, reflection, dynamic
SQL reached through another receiver, native VFS modifications or compromised
host/process. Scanning function ASTs is a controlled regression inventory,
not secure executable confinement.

## Explicit negative findings

1. `_update` and `_save_record` issue SQL directly and can be called
   from arbitrary same-process Python without going through a semantic
   entrypoint. A caller can then call `store.db.commit()` directly; the
   pre-COMMIT marker is absent and local health can remain green. The A292
   negative test **demonstrates** this, not hides it. Treat same-process code
   as trusted for these local guards; do not expose these helpers as public
   authority-bearing APIs.
2. `__init__` schema initialization (`executescript`), `backup_to`
   (`sqlite3.Connection.backup`), `restore_from_backup` (file operations)
   and WAL checkpoint maintenance are **different classes of write** and
   are not covered by the six-business-write matrix. They need their own
   custody and restoration threat model.
3. A local, removable marker cannot prove that a hostile host has not
   deleted it, swapped the SQLite file, or rolled history back. The six
   confirmed code paths do not constitute end-to-end write isolation.

## Real SQLite experiments

No fake SQLite connection is used. A subclass of `sqlite3.Connection`
(from A291) injects **one synthetic exception** into `commit()`:

- **Before COMMIT:** no externally visible semantic effect; pending marker,
  FAIL-closed store and no automatic retry.
- **After real COMMIT, before application ACK:** exactly one externally
  visible semantic effect; same pending marker, FAIL-closed store and no
  automatic retry.

Each of the six semantic write APIs is exercised in **both** phases (12
matrix cells). Every probe measures the state from another independent
SQLite connection, tests that retry cannot change the outcome, closes the
store and checks refusal to reopen with a pending marker. Additional normal
run executes all six APIs and observes six marker publications and cleanup.

**Key rule:** a failed or missing COMMIT acknowledgment is **UNKNOWN**
rather than proof of rollback. Hence **ZERO_AUTO_RESEND**. The store
cannot infer from an exception alone whether the effect happened.

## How to reproduce

```bash
python -m unittest -v labs.test_a292_staged_chat_write_inventory_lab
python -m unittest -v labs.test_a291_chat_write_gate_commit_fence_lab
python -m unittest -v labs.test_a290_sqlite_local_write_gate_lab
```

GitHub Actions workflow `aion-a292-chat-write-inventory-lab.yml` runs
these suites on Ubuntu and Windows (Python 3.12) in the isolated draft PR,
using standard public-repository runners. The workflow does not deploy,
invoke providers, run production Worker, send messages, or run real trades.

## Gate

**GO-LAB (only if tests pass)** permits additional synthetic exploration.
**NO-GO integration, HARD NO-GO production.** A292 does not homologate a
single P0, establish external signer/custodian, authenticate the native
SQLite VFS/file descriptor, or provide host-independent rollback witness.
No merge or production change is authorized.
