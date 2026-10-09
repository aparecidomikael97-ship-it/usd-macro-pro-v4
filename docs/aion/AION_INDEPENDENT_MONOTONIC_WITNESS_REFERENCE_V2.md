# Independent monotonic checkpoint / witness reference V2

Base: Draft #1113, branch impl/aion-durable-dual-ed25519-replay-policy-v1-20261008,
exact SHA cabcf5661c69078fafa13139ed7e2bd4ad3e80fc.
Separate stacked Draft. Frozen Core V1, main, old sources/tests/workflows unchanged.
Reference architecture and disposable simulated proof only.
DO NOT MERGE / DEPLOY / BUILD / INSTALL / ENROLL / RESUME.

## Existing evidence and reuse

#1109 defines the three roles and V1 intent; #1110 verifies actual Ed25519 public
math; #1111 recomputes dual role math; #1113 implements the bounded durable
SQLite challenge/receipt/audit/policy CAS. Base CI 37873008719 passed 182 cases
on each Windows/Linux hosted runner (35+27+33+87).

This reference reuses their public verifier, strict bounded copier, canonical
JSON, timestamp parser, complete ledger validator, receipt derivation and CAS
consume. It does not create another nonce authority, enrollment, executor,
repair service or generic store. Read-only snapshot opens existing fixture DB,
BEGIN + query_only, validates every old table, orders every row, hashes all
metadata, policy, challenges including receipts, and audit records. Nothing in
SQLite selects the witness public key. No original file is modified.

## Protocol and trust boundary

Explicit bootstrap: the test coordinator fixes scope and witness PUBLIC pin
separately, and initializes independent witness state from the validated
initial ledger snapshot AFTER challenge issuance. Bootstrap is a controlled
test assumption, not evidence of enrollment/identity/custody. New issuance after
that baseline changes the hash and requires separately supervised design; no
silent resynchronization or epoch reset exists.

Scope: installation_id, trust_chain_id, witness_id, independently fixed test
owner/collector public fingerprints and custody policy digest.
Closed checkpoint includes schema/version=2, purpose/domain, PREPARED or
CONFIRMED, scope, monotonic generation, exact policy hash, complete ledger hash,
sequence, previous confirmed checkpoint hash, transaction ID, challenge ID,
observed timestamp and clock_trusted=False. Sorted ASCII canonical JSON and
distinct null-separated V2 domains for custody, full policy, role intents,
complete ledger state and checkpoint digest.

1. PREPARE: verify raw V1 dual signatures required by old SQLite AND additional
   explicit V2 custody-bound dual signatures. Snapshot the intact ledger.
   Compute the exact single permitted consumed transition using the original
   receipt/audit derivation. Independent witness verifies the dual V2 request
   itself and recomputes that target, checks baseline hash, fixed scope, prior
   sequence/hash, monotonic policy and unique transaction, then reserves ONE
   pending transition. Only the disposable test wrapper signs its prepare
   checkpoint. Adapter verifies separately fixed witness pin, exact target and the live
   independent pending reservation before touching the nonce.
2. CONSUME: invoke unchanged SQLite transaction. Nonce+receipt+policy+audit commit
   atomically within SQLite ONLY. Witness and SQLite have no shared transaction.
   A pending reservation is not a confirmed checkpoint and never executable.
3. CONFIRM: independently compare current validated complete ledger to exact
   prepared target. Witness moves only compatible pending to confirmed; signs
   the confirmed phase separately. Verifier checks pin, exact checkpoint,
   ledger match and current independent head. No implicit trust-chain/pin change.
4. RECOVERY: explicit original prepared intent is required. Restarted adapter
   may confirm a matching already-consumed pending transition or acknowledge
   the same latest confirmed checkpoint. It never consumes/issues again,
   repairs, recreates missing storage or reconciles different states.
   Missing intent, mismatched ledger, stale head, unavailable witness or
   uncertain state => BLOCKED / supervised recovery. No local fallback.

ReferenceWitnessState is independent controlled RAM in CI; test WitnessPort
alone holds ephemeral private objects and signs. No private bytes are exported,
persisted or logged. This state is NOT restart-durable real infrastructure.
An adapter restart is tested while the independent witness survives. A witness
restart/loss without protected persistence is outside the guarantee and blocks
unless the test deliberately resets it to demonstrate loss of protection.

## Restore proof and limits

Restoring DB alone, or DB plus a local checkpoint copy, while the independent
witness retains its higher checkpoint blocks prepare/recovery before a new
confirmed transition. Complete hash includes every old record and audit head.

Restoring BOTH DB and independent witness to their old coherent state permits
the old request again. Test explicitly proves guarantee loss, with all installer,
hardware, owner and execution gates false. SQLite plus unprotected RAM is not
physical/admin-resistant storage. An administrator controlling the verifier,
pin or witness can replace the whole simulation. Signatures require a genuinely
independent enrollment/root, live authenticated transport, durable witness
persistence and antirollback/recovery controls in a real system.

A static signed checkpoint alone does not prove latest state. Expected sequence,
previous hash and target must be obtained from the independent state protocol.
The test signer/port is separate from the independently supplied live
ReferenceWitnessState. Adapter NEVER derives the expected head from the port;
it checks the exact reservation in that same independent state. This direct
live-state access is a controlled simulation assumption, not authenticated
remote transport or a production storage API.
No claim of network freshness, cryptographic remote attestation, availability
under malicious transport or protection against restored witness state is made.
The plain state-machine class is not a signer or access-control boundary. Its
confirm target is constrained by an earlier independently verified prepare;
production access control/durable reservation design is absent.

No distributed ACID, exactly-once external execution, physical power-loss
guarantee, trusted clock or actual hardware guarantee. An acknowledgment can
be lost after SQLite or witness commit; blocked response does not imply rollback.
Repeated explicit recovery may repeat an observation, never create authorization.
Bounds: uint32 sequence/generation, 2048 witness terminal transactions, 2048
challenge rows/8192 audit rows/8192-char record strings; no automatic pruning/reset.
Hashing a maximal valid ledger is linear and bounded, not a small fixed latency.
Concurrent callers share locked witness state and SQLite CAS, never a global
execution permission. An older confirmation may conservatively lose its latest-
head acknowledgment when a newer checkpoint wins concurrently.

## V1 omitted signed custody fields: executed finding and versioned migration

#1109 validates custodian_id, custody_boundary and estimated_monthly_brl but its
V1 signed transcript omits them. Three executable cases alter each field while
retaining the SAME V1 signatures; mathematical V1 verification remains valid.
That is a binding gap, not proof of an authenticated owner or exploitable installer
(the original V1 never authorizes either). Risk: downstream code must not treat
these mutable descriptions as signed custody/cost commitments.

V2 build_v2_binding explicitly includes the ENTIRE validated proposal, including
all three role custody/IDs and estimated cost, under NEW schema, purpose and
role domains. V1 signatures cannot satisfy V2 intents. New fixture adapter
requires BOTH old math for old ledger and V2 signatures for the new boundary.
Pinned custody digest prevents swapping descriptions even with new signatures.
Policy/generation advancement requires new dual V2 intents; equal conflicting
policy and old generation reject. No implicit trust-chain/custody rotation.

This is a proposed/tested migration only, not activated production wiring.
Self-described custody, IDs, cost estimate and fingerprints still do not prove
real-world custody, budget fulfillment, independent enrollment or authority.
No V1 history/transcript/test result is rewritten or silently reinterpreted.

## Separate observations in every result

- DUAL_SIGNATURE_MATHEMATICALLY_VALID: actual public math, not identity.
- NONCE_CONSUMED_INTACT_LEDGER: actual SQLite state in the fixture.
- EXTERNAL_WITNESS_CHECKPOINT_VERIFIED: signature matches separate fixed TEST pin.
- LEDGER_MATCHES_WITNESS: exact current fixture/independent-state comparison.
- HARDWARE_ANTIROLLBACK_VERIFIED: FALSE.
- OWNER_IDENTITY_AUTHENTICATED: FALSE.
- INSTALLER_AUTHORIZED: FALSE.

Also always FALSE: independent_custody_verified, p256_tpm_origin_attested,
physical_sandbox_verified, physical_network_deny_verified,
key_enrollment_authorized, build_authorized, deploy_authorized, safe_to_resume,
execution_allowed, execution_authorized and all inherited V1 safety gates.
No successful observation changes physical gates or installer authorization.

## Real anchor options — proposal only, no purchase/activation

Budget cap R$200/month; the ranges below are preliminary planning estimates
INFERRED for low-volume use, not vendor quotes or evidence of total cost.
Engineering, device replacement, independent key custody, backup/recovery and
audits are NOT included. No account/resource/service was created or contracted.

| Option | Complexity / rough recurring planning | Recovery/offline | Cloning and lockout |
| --- | --- | --- | --- |
| Supported, independently proven TPM NV counter/mechanism on existing host | High; R$0 service fee if already supported, engineering/hardware separate | Offline possible; TPM loss/clear/replacement needs supervised re-enrollment | Disk clone alone can differ from protected counter; trusted enrollment and clear/reset policy essential; lockout risk high |
| Authenticated independent witness with protected monotonic storage | Medium/high; provisional R$0–100/mo small volume, not guaranteed all-in | Online required, fail closed on outage; protected backups MUST NOT rewind trusted head | Independent admin/custody makes local clone diverge; witness rollback/compromise defeats guarantee |
| Corporate/HSM anchor | High; no substantiated <=R$200 all-in quote, assume budget gate BLOCKED unless existing allocation proven | Corporate lifecycle/availability dependency | Potentially stronger key protection, but HSM signature alone is not monotonic database state; recovery still required |
| Hybrid independent witness + proven hardware mechanism | Highest; provisional R$0–200/mo only if existing hardware/service allocation suffices | Offline transitions need separately designed bounded policy; no fallback here | Protects against different failure domains only with independent enrollment/state, high lockout/recovery complexity |

Primary reference documents consulted 2026-10-09:
- [TCG TPM 2.0 structures specification](https://trustedcomputinggroup.org/wp-content/uploads/Trusted-Platform-Module-2.0-Library-Part-2-Structures_Version-185_pub.pdf):
  NV_COUNTERS_MAX/NV attributes exist as capabilities, not proof this owner's
  TPM supports an approved persistent monotonic scheme.
- [Microsoft TPM key attestation](https://learn.microsoft.com/en-us/windows-server/identity/ad-ds/manage/component-updates/tpm-key-attestation):
  independently attested key properties; key protection is not whole-ledger
  antirollback and no commands from the document were executed.
- [DynamoDB conditional operations](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/read-write-operations.html)
  and [pricing](https://aws.amazon.com/dynamodb/pricing/):
  conditional writes and free storage allowances illustrate a possible storage
  building block. They do not supply trusted witness identity/signing/antirollback
  against its administrator or guarantee a free whole service.

Technical recommendation: design and independently review the protected live
witness/enrollment/recovery protocol first; use this simulation to specify failure
semantics. Evaluate actual TPM capabilities ONLY in a separately authorized
physical phase. Consider hybrid after independent attestation and custody proof;
do not choose/install a TPM/HSM/service merely because a public API exists.
Proposed architecture, simulated proof and absent physical proof remain distinct.

## Post-green adversarial diff audit: reproduced bugs and minimal fixes

After initial full-green 90-case CI, additional executable attacks found:
1. Replayed old PREPARED/CONFIRMED signed replies plus fake port head hid a
   restored DB from an intact witness. Reproduction checkpoint commit
   9164757b6d7372d96b26cedef447aab70653a78c; run 37904437213 failed the new
   test on both OS while original 182 tests stayed green.
   Minimal fix: require separately supplied exact live ReferenceWitnessState,
   whose scope/head is independent of port replies. It is the SAME witness,
   not a duplicated nonce store or authority. Real protected transport remains
   absent; an untrusted transport cannot supply this simulation trust root.
2. Valid signed prepare without its live reservation could consume SQLite,
   although final checkpoint stayed BLOCKED. Reproduction checkpoint
   967be4721f9a3aa968d390035350ecebf3f80149; run 37904669035 failed the new
   test on both OS. Minimal fix: matches_pending under witness lock before
   SQLite consumption. No fallback/reset or new authorization.

Two regression tests remain mandatory and unchanged after reproduction.
All gates stayed false even in the failing reference observation/consumption.
These were NEW reference-adapter bugs, not silent patches to V1 or production.

First run 37904119178: Linux all 272 passed; Windows old182 passed and new90
had 4 cleanup errors caused by test SQLite context managers not closing handles.
Explicit closing fixes fixture cleanup without loosening corruption asserts.
Run37904261968: bothOS272 passed.
Intermediate run37904534544: source constructor change preceded fixture change
in separate API commits, producing 91 fixture TypeErrors perOS; original182
passed. Run37904542033: old182 passed, new91 had one BOTH-restore fixture
failure because the independently fixed state reference had not also been
restored; the test now explicitly reconstructs the adapter after restoring BOTH.
This preserves and accurately demonstrates the loss-of-guarantee scenario.
Final changes use one Git-data tree commit for coordinated files.

## CI and adversarial audit

Dedicated new Windows/Linux hosted workflow, exact PR SHA, read-only checkout
credentials, pinned actions and dependency versions. Hosted guard runs before
ephemeral private-key fixture imports. Existing 35/27/33/87 cases unchanged;
new suite individually collects 100 cases plus faults/concurrency/determinism.
Compile/YAML/AST forbids signing/key generation/network/native/installer/worker/
filesystem writes in new reference source. Runtime mocks deny socket/subprocess
during full flow and all Python file opens during pure public verification.
Snapshot proves byte-identical DB before/after. Explicit fixture SQLite writes
are expected, exclusively under disposable temporary roots, not "zero all I/O".

Artifacts contain counts and tested head ONLY, never DB/payload/signature/keys.
Final measured CI counts, failures, corrections, run links and follow-up diff
audit are recorded in the PR delivery report after execution. No speculative CI
success is asserted here.

All implementation uses GitHub APIs; execution is ONLY disposable hosted CI.
No implementation/test command on am12, no owner-computer/security/TPM/Hello/
registry/ACL/firewall/real-key/production modification. User attachment was read
to obtain the instructions; no further host access. No provider/billing/real
order/customer contact/CRM/provisioning/deploy/merge/installer/collector activation.
