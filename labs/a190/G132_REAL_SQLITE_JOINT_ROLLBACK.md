# G132 — Real SQLite joint rollback falsification (LAB ONLY)

Status: **NOT P0 / HARD NO-GO**. This laboratory reproduces failure; it does not build a live custodial service or authorize provider SEND.

## Threat and scope

- SQLite runs as a real on-disk database in WAL mode on the runner, not an in-memory fake. The baseline snapshot uses SQLite's online backup API to include committed WAL transactions, rather than copying the main file alone.
- Witness is a JSON file controlled by the application, deliberately **not** a trusted independent principal.
- The "effect" is only an in-memory Python list, **not** a network call, brokerage order, payment, email, Worker, or third-party receipt. No personal/customer credentials.
- After a simulated effect with lost ACK, the attacker restores BOTH the physical SQLite state (database and deleted WAL/SHM sidecars) and the local witness to an older snapshot. The synthetic effect list stays intact.
- The same original event is then accepted a second time with another request ID: **UNSAFE_READMISSION_REPRODUCED**. The test is intentionally green if it reproduces this failure; it must **never** be counted as a security gate passing.
- DB-only restoration, witness-only restoration, missing witness, and a new request_id with intact prior reservation are blocked locally. These successes do **not** prove resistance to full-host compromise.
- Changing a **self-claimed** original_event also permits two logical claims. Original business-event provenance is not authenticated in this model.

## Decision / next acceptance

For A190 P0-1/2/3/4 and A185 SQLite P0-5/6 to progress, the custodian must demonstrably maintain monotonic ordering and the ORIGINAL event authorization outside the app/host rollback domain. Its root keys, enrollment and revocation must not be repinnable by the client. Supplier effect receipts must be independently authenticated.

A valid follow-up test must restore all app-controlled DB/WAL/SHM/snapshots/keys/witness, restart H0, and capture a **rejection from the actual external authority** for the same original semantic event. Simulated success, a local checksum, an extra localhost process, ACLs against only a low-privilege account or caller-signed evidence do not satisfy it. If the authority is offline or results are unknown: **deny, UNCERTAIN, ZERO_AUTO_RESEND**.

## Bounds

Runner tests provide portability evidence for Windows and Ubuntu only. They do not demonstrate a remote signer, third-party provider idempotency, actual anti-rollback storage, attack under admin/root, or complete compatibility with the AION operational SQLite stores. CI for G122 must remain red with all five external acceptance assertions unmasked. No main/merge/deploy, Worker, SEND, account provisioning, paid provider or cost. Human approval before any external service or key enrollment.

Tracking: A190 #1486; A185 #1477. Base: G131 Draft #1623.
