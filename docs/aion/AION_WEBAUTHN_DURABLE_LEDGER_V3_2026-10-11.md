# AION V3 — durable offline WebAuthn ledger

FIRST INSTALL = HARD NO-GO. All 20 original evidence gates remain BLOCKED.
Base: Draft #1218, a9b2033f79755e6a5f8e3cc908287023dc57eaa9.
No production authentication integration. No private evidence or real keys.

## Audit and reuse

`atlasquant_aion_first_install_preparation_v2/webauthn_reference.py` already
verifies real ES256 signatures, COSE, client JSON, RP/origin, UP/UV, BE/BS,
counters, intent binding and explicitly supplied replay/revocation state.
Reproduction on the exact base: two calls with the same valid assertion and
unchanged empty replay list both return REFERENCE_ASSERTION_CRYPTO_VALID_UNTRUSTED,
with durable_replay_protection=false. This is a documented MEDIUM preparation
gap, not a production authorization bypass. V3 supplies persistent replay and
credential state to that unchanged verifier, never replaces its crypto.

V1 `ceremony.prepare_intent`, `contracts.binding/digest/result` are reused.
V1 ceremony remains simulated consistency, not a signature verifier.
`ReferenceV2NonceCostLedger` handles signed financial hold/request nonces;
`ReferenceOneShotUnknownOutcomeJournal` persists conservative one-shot dispatch
claims. Their tables/configuration are purpose-specific and cannot atomically
update WebAuthn counters/generations without changing earlier contracts.
V3 follows their durable-before-effect/no-resend pattern in a separate reference
file, with no migration of those stores and no second production auth system.

The existing witness CAS commit-attempt tracking and UNKNOWN_OUTCOME fix are
untouched. `atlasquant_aion_execution_outbox.py` was inspected: `reconcile`
distinguishes confirmed effects from uncertainty, but `release_expired_claims`
and authoritative-absence paths may return RETRY. Those action-dispatch paths
are deliberately not used for one-shot WebAuthn challenges. No dispatcher,
Worker, provider or productive authorization module imports V3.

Distinct facts: valid signature is fixture mathematics; an ISSUED challenge is
not yet consumed; ACTIVE is only a local disposable registry state; durable
consumption is local causal evidence; NONE supplies owner enrollment, consent,
physical device proof, installation, spending, Worker or deploy permission.

## Data model and closed contracts

One explicitly created disposable SQLite file, bound to exact fixture aliases
owner_id/tenant_id/workspace_id. Native connections are owned by each call and
closed in finally; check_same_thread is never disabled. Subsequent mutations
open mode=rw, never recreate a missing store. Readback uses mode=ro/query_only,
a fresh connection and a read transaction; it never invokes constructors,
claims, consumption or CREATE statements.

| Table | Purpose |
|---|---|
| config/meta | Immutable scope; local sequence/hash head |
| credentials | Credential ID + generation PK, device alias, public COSE key/hash, BE, counter, latest BS, validity, ACTIVE/RETIRED/REVOKED |
| challenges | Unique challenge, request ID and nonce; full prepared intent/digest, credential/generation, RP/origin, issue/expiry, state and attempt ID |
| attempts | Unique causal attempt + challenge, intent/assertion/request digests, state and consumed counter |
| receipts | Namespaced operation ID, exact request digest, unique event sequence |
| events | Ordered cause, previous digest, current-state digest and event digest |

Only public fixture keys and logical scope/intent metadata are stored. Raw
clientDataJSON, assertions/signatures and private keys are not persisted.
Private keys are generated only in test memory. JSON/COSE/type/size contracts
come from V1/V2. Scope aliases, native timeout (at most two seconds), table and
column shape, rows (512 per table), materialized row size (32768) and event
payload (1024) are bounded. Limit exhaustion blocks; there is no pruning/reuse.
Ledger metadata and receipts must match a contiguous hash chain and current
state. This is local integrity, not signing, encryption, WORM or antirollback.

## States and transaction boundary

1. REGISTER/ROTATE/REVOKE/ISSUE commit their registry/intent change and causal
   event together, then require independent readback before a positive result.
2. Confirm begins IMMEDIATE, verifies immutable challenge/intent/scope and the
   current active credential, signature and counter under the write lock.
3. ADMISSION atomically changes ISSUED -> ATTEMPT_PENDING and records a bound
   PENDING attempt before the possible consumption. Admission is not success.
4. A second IMMEDIATE transaction rechecks generation/revocation/key/counter.
   Valid: challenge -> CONSUMED, attempt -> CONSUMED, counter/BS update and
   CONSUMPTION receipt/event in ONE commit. Invalidated after admission:
   challenge/attempt -> QUARANTINED with a causal event, without counter update.
5. A new mode=ro snapshot verifies causal receipt, scope, chain and state.
   Only then REFERENCE_DURABLE_RECEIPT_UNTRUSTED is returned. Its namespace
   distinguishes admission, mutation and consumption. Consumption readback is
   explicitly historical_consumption_only, never current operational consent.

No transition leaves ATTEMPT_PENDING, QUARANTINED or CONSUMED for ISSUED.
No expiry release, reset, reclaim, refund, resend or automatic retry exists.
Repeated attempt IDs, challenge/nonce/request IDs and changed payloads block.
The second transaction cannot be resumed through the public API after a lost
ACK or process interruption: uncertainty remains quarantined for future review.
Two transactions are intentional: admission remains durable if consumption
never commits; actual consumption/counter/generation verification are atomic.

## Simulated credential lifecycle and counters

Initial generation must be 1. Rotation requires SIMULATE_ROTATION_ONLY, exact
previous generation/public key pin, next generation old+1 and a DIFFERENT
valid public key for the same identity/device scope. CAS under IMMEDIATE
allows one competing rotation. ACTIVE old versions become RETIRED. REVOKED
versions stay REVOKED; explicit rotation to a new version does not rehabilitate
the old one. Unknown keys, overwrite, downgrade, mismatched pin/device/tenant,
ADMIN/HUMAN_OWNER role spoof and unregistered versions block.
Revocation persists irreversibly for that generation. Recheck in consumption
closes the admission-to-consumption rotation/revocation/counter race.

Nonzero signCount must increase. Two operations with the same counter cannot
both advance the same credential. Zero/zero is permitted for the fixture
profile, with counter_assurance=NONE_FOR_ZERO. Zero after known increment is
conservatively blocked. BE is immutable within a generation; BS may change
for a backup-eligible credential, but BS without BE is invalid. Neither an
increment nor zero proves absence of cloning: cloning_absence_verified=false
always. WebAuthn scope remains ES256/.invalid RP/37-byte data without extensions.
This is not browser/device conformance certification.

Protocol reference: [W3C WebAuthn assertion verification and counters](https://www.w3.org/TR/2026/REC-webauthn-3-20260825/#sctn-verifying-assertion).

## Failure and recovery matrix

| Failure | Observed behavior / recovery |
|---|---|
| Before BEGIN / missing active DB / lock | RECONCILIATION_REQUIRED, no automatic retry or new DB creation |
| Invalid signature/JSON/RP/COSE | BLOCKED, no admission, consumption or counter mutation |
| During final write | Rollback restores counter; durable admission stays pending |
| Before final COMMIT | UNKNOWN_OUTCOME; no consumption receipt; readback remains RECONCILIATION_REQUIRED |
| Final commit persisted, ACK/close/readback lost | UNKNOWN_OUTCOME; fresh read proves the exact local consumption; another attempt is blocked |
| Admission commit ACK lost | PENDING survives; consumption not attempted; repeated request blocked |
| Rollback error | UNKNOWN_OUTCOME, no fabricated absence or leaked exception payload |
| Abrupt os._exit after COMMIT | Another process reads committed receipt; no second consumption |
| Revocation/rotation process exit after COMMIT | Persistent REVOKED/new generation; repeated mutation blocked |
| Payload changed with same attempt ID | BLOCKED; readback digest conflict blocks |
| Corrupt file / mutation of counter, generation or causal receipt | UNKNOWN_OUTCOME or BLOCKED, no rebootstrap |
| Entire earlier coherent DB restored | Supplied newer floor detects regression; absent trusted floor, local consistency alone cannot detect privileged restoration |

Real subprocess tests cover four competing processes on one challenge,
different operations/same credential counter, termination after consumption,
revocation and rotation, and readback from another process. Thread tests cover
same challenge, shared counter, concurrent rotation and revoke/consume races.
Process separation does not establish independent administrative custody.
os._exit simulates abrupt process loss, NOT physical power-loss testing.

During new fixture development, Windows exposed test helper handle leakage:
sqlite connection context managers commit/rollback but do not close. The helper
now uses explicit contextlib.closing; no skip or ignored cleanup error was
added. This was a new test-harness defect, not an inherited production change.

## Validation evidence and limits

Local integrated run: 13 challenge tests/30 subtests, 12 registry tests/12
subtests, 18 recovery tests/6 subtests; unchanged V2 groups 14/61, 17/15, 6/26;
unchanged V1 246/380. Zero failures/errors/skips/expected failures. Windows and
Linux candidate-head CI is required and recorded in the Draft description;
base #1218 results are not candidate approval. Global root Quality runs its
original official list; counts and overlapping regressions are kept separate.

Not tested: physical energy loss/fsync hardware behavior, authenticators,
browser passkeys, owner identity, external providers, TPM/FIDO enrollment,
production databases or independent institutional evidence. No paid API,
private checkpoint, real customer data, installation or Worker was accessed.

## Residual risks and review criteria

- HIGH deployment blocker: a privileged operator can restore ALL local files,
  including a self-consistent ledger. The negative restore test demonstrates
  local replay can then be accepted again; all productive flags remain false.
  A caller-supplied high-watermark is not independent trust.
- HIGH deployment blocker: real key enrollment, custody, independent approval,
  physical owner/device identity and the 20 evidence requirements are absent.
- MEDIUM: timestamps/floors and initial fixture registry are caller-supplied;
  no trusted external clock, signed institutional record or custody exists.
- MEDIUM: pending admission cannot be automatically cleared even after proven
  local absence. This sacrifices liveness to prevent ambiguous repetition.
- MEDIUM: original assertion is intentionally not stored; replay of its crypto
  requires the original fixture supplied separately. Local receipt is causal
  bookkeeping, not independently signed remote attestation.
- LOW: bounded experimental schema has no migration/pruning/production SLA;
  local hash chain cannot defend malicious privileged recomputation.

Review acceptance is offline reference readiness only: exact-base child Draft,
all candidate Windows/Linux jobs green, full original Quality, no removed
tests/skips, postcommit UNKNOWN_OUTCOME preserved, original Core/manifest and
productive flags unchanged. FIRST INSTALL remains HARD NO-GO.

Next safe mission: offline verification of independently signed monotonic
head/credential-revocation anchors, with explicit trust-root provenance and
fork/restore negative tests. Fixtures remain untrusted; no enrollment or
provisioning follows from such a package.
