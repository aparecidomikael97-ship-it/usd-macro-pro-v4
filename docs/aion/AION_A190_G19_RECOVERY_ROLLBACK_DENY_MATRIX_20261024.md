# A190 G19 — Recovery and rollback denial matrix (LAB design only)

Base: G18 Draft PR #1505, SHA 2d4c1b51b8fc968c7ec57b4d6d150abdecfd08d5.

## Threat model
G18 demonstrated that a hostile host can replace a closed SQLite database with a same-marker clone; the actual stdlib connection and independent Win32 anchor agree on the replacement. Native file identity is insufficient to prove history.

## Fail-closed requirements
1. Every side-effecting intent has a semantic idempotency key independent of transport request_id.
2. Persist a durable PREPARED/RESERVED intent *before* first provider send, with an externally anchored monotonic witness. Without independent witness, do not claim rollback protection.
3. On provider timeout, uncertain response, missing receipt, restart, or disagreement, enter UNCERTAIN and ZERO_AUTO_RESEND. Never infer failure from missing local journal.
4. Recovery compares externally authenticated latest witness, semantic intent key, ordered sequence, provider receipt authenticity, SQLite state and independent restart evidence. If any source is unavailable or inconsistent, DENY and request human-supervised reconciliation.
5. A same-marker cloned DB, a closed-file replacement, a deleted journal, or two different request IDs for one semantic effect must not permit a second send.
6. A correct local native file identity is diagnostic only; WAL/SHM and crash atomicity require independent validation.
7. Owner identity and provider receipt verification must use independent, pinned trust roots, not self-supplied keys.
8. Never auto-resolve UNKNOWN/UNCERTAIN to FAILED, SUCCESS, or RETRYABLE based only on local files.

## Required adversarial tests before considering any production gate
- Same-marker clone and closed-file replacement with correct native file identity.
- Deletion or rollback of all local journal and marker files.
- Preopened rogue SQLite connection plus honest decoy.
- Semantic duplicate with distinct request IDs and same payload.
- Crash immediately before send, during send, after provider effect before local receipt, after commit before acknowledgment.
- WAL/SHM mismatch and partial recovery after restart.
- Witness unreachable, stale, untrusted, mismatched or replayed.
- Forged owner approval and provider receipt.
- Recovery after reboot without trusted monotonic witness.
- Multiple concurrent attempts with same semantic key.

## Current decision
No implementation, external witness or trusted provider was validated in this G19 document. This is a concrete acceptance matrix, NOT P0 closure. G18 Windows 10/10 synthetic LAB remains the last observed native CI evidence.

**0/6 P0 homologated. HARD NO-GO. UNCERTAIN. ZERO_AUTO_RESEND.**
