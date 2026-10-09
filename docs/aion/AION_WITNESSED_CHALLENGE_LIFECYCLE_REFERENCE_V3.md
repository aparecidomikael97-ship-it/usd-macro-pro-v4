# AION witnessed challenge lifecycle reference V3

Base Draft #1115, impl/aion-independent-monotonic-witness-reference-v2-20261009,
exact cfb2e2008511fe2a4f51ed3eeffe09c4238f32f7.
Previous verified hosted CI: 282 Windows / 282 Linux.
Separate stacked Draft, frozen V1/main/#1114 unchanged.
DO NOT MERGE / DEPLOY / BUILD / INSTALL / ENROLL / RESUME.

## Gap, inspection and reuse

V2 bootstrapped after ISSUE and could witness only consumption; a subsequent
ISSUE/EXPIRE/REVOKE changed the complete ledger hash outside that protocol.
V3 closes this reference gap by starting from an explicitly EMPTY validated
fixture and witnessing EVERY new challenge transition.

Inspected exact #1109 three-role transcript/custody design, #1110 public
Ed25519 verifier, #1111 dual math, #1113 SQLite BEGIN IMMEDIATE CAS/receipt/
policy/audit validator, and #1115 V2 pin/live-state reservation/snapshot logic.
Open-PR searches for transitions/lifecycle/witness found no existing V3 fix.
#1114 is a separate Windows physical-evidence front, untouched.

Reused:
- SAME existing ReferenceChallengeRegistry tables, CAS, issue/consume/revoke,
  audit validator, canonical JSON/hash, parser and monotonic clock watermark.
- EXPIRE explicitly invokes old consume at/after expiry with original valid
  V1 dual signatures. It uses the existing EXPIRED transition, not a second SQL
  implementation or new scheduler. Its nonce-consumed flag is correctly false.
- V2 read-only validated complete snapshot, bounded data copier, custody digest,
  public Ed25519 mathematical verifier, expected consumed transition.
- LifecycleWitnessState extends SAME V2 ReferenceWitnessState initialization,
  RLock, pending/head/ledger-head/used machinery and base confirm mutation.
  V3 adds operation validation and signed history; it is not another nonce DB.

No old source/test/workflow modified. Only one new reference module, suite,
dedicated hosted workflow and this document.

## State protocol

~~~mermaid
stateDiagram-v2
    [*] --> Absent
    Absent --> ISSUED: witnessed ISSUE_CHALLENGE
    ISSUED --> CONSUMED: witnessed CONSUME_CHALLENGE
    ISSUED --> EXPIRED: witnessed EXPIRE_CHALLENGE / untrusted clock
    ISSUED --> REVOKED: witnessed REVOKE_CHALLENGE
    CONSUMED --> [*]
    EXPIRED --> [*]
    REVOKED --> [*]
~~~

Each operation: unsigned construction -> two role math verifications ->
independent PREPARED reservation -> existing SQLite commit ->
signed CONFIRMED checkpoint -> exact current ledger/head comparison.
Errors/uncertain acknowledgments/divergence => BLOCKED, original intent/ticket
required for explicit supervised recovery, no automatic retry/repair/fallback.

## Closed V3 contract and operation separation

Exact schema/version=3, operation and its fixed REFERENCE_NOT_AUTHORIZATION
purpose. Domain-separated operation+role intents; ISSUE signatures CANNOT
verify CONSUME/EXPIRE/REVOKE messages. Witness signatures separately bind
operation and PREPARED/CONFIRMED phase PLUS request_sha256 of the entire verified
original request, canonical sorted ASCII JSON. Request digest is recomputed;
an unsigned metadata digest cannot substitute for that authenticated binding.

Body binds installation/trust-chain/witness, 256-bit lower-hex nonce, transaction
ID, checkpoint sequence, full before/expected-after ledger hashes, previous
checkpoint hash, effective generation/policy, fixed public owner/collector
fingerprints, V2 custody digest, collector binary hash, ENTIRE original proposal
including custody metadata/estimated cost, previous/next challenge states,
issue/expiry/observation times, clock_trusted=False.
No bool-as-int, implicit coercion, future schema, extra authority fields, raw
execution/transport material or client-selected root/head accepted.

V3 dual signatures are required for ALL operations. CONSUME/EXPIRE additionally
require the original V1 math payload solely because unchanged SQLite consumes
that contract. Exact proposal/nonce must match. V1 signature is not a V3 intent.
P256 host does not satisfy either independent Ed25519 role. Fingerprints and
custody descriptions in proposals still do NOT prove real owner/custody.

## Bootstrap, issuance, policy and tombstones

Bootstrap is explicit once: empty metadata version1/clock0, no policy/challenge/
audit rows, fixed separately supplied scope, public witness TEST pin and policy
floor. An existing nonempty V2 ledger is NOT silently imported/reinitialized.
Its real migration needs a separately reviewed authorized genesis ceremony.
This phase implements the full clean-fixture lifecycle; it does not authorize a
production migration or generate/enroll keys.

First and subsequent ISSUE reserve and witness exact insertion/audit transition.
No reset, pruning or arbitrary resynchronization. Duplicate/terminal nonce always
rejects. Tombstones remain in SQLite and signed witness history.
Witness sequence advances on every confirmed transition.

Effective global policy generation advances ONLY on CONSUME, matching old ledger
semantics. Initial policy floor is independently fixed at bootstrap; issuance
of a higher-generation challenge does not activate that policy. ISSUE/CONSUME
reject lower generation and equal/conflicting policy. After a higher consumption,
old consume/issue intents cannot be reused. Expiration/revocation may close an
old-generation issued challenge while preserving CURRENT global policy. The
body also binds the challenge's original proposal/generation/hash, distinguishing
challenge metadata from active policy. Scope/custody/chain/pin rotation is absent.

Recreating a deleted DB or changing IDs cannot reset an intact independent state.
Missing DB opens mode=rw and fails; deliberately recreated empty DB differs from
the retained higher witness hash and blocks. Initial standalone bootstrap is a
TEST assumption; restoring the witness itself defeats it.

## Independent state, signed history and verification

Separately supplied live LifecycleWitnessState is the SAME simulated witness
behind the signing port, not a head learned from a client response. Port claims
cannot replace it. Expected sequence/hash and exact reservation are checked
before any SQLite write, retaining V2's fixes against replayed signed replies
and unreserved signed PREPARED messages.

Witness independently verifies dual V3 math and recomputes the expected transition
from its exact authenticated-by-test-bootstrap prior hash. It stores one pending
intent/request digest; signed confirmed history binds every checkpoint to the
previous checkpoint and ledger hash. Re-validates signed history against its
separately fixed TEST pin, scope, lifecycle, policy, contiguous sequence, head and
used transactions before operations. Corruption/deletion/reorder/head divergence
fails closed. Private signing occurs ONLY in hosted TEST wrapper, under the same
witness lock; no production signing API/private material export.

Signed history improves corruption detection; it does not protect a process/
administrator who replaces the pin/whole independent state. Witness remains RAM
and restart/backup/rollback-resistant persistence is NOT implemented. Signature
verification against a synthetic fixed pin is not real trusted enrollment.
Witness port is a controlled object, not a protected remote network service.

## Transaction, concurrency and recovery

SQLite alone owns ACID across nonce/receipt/policy/audit/clock. Witness+SQLite
are NOT a distributed ACID unit; no exactly-once external execution is claimed.

One witness pending reservation globally serializes transitions. All signed
intents contain a specific before hash and sequence. Concurrent stale intents
block even when they refer to different nonces. A new attempt must rebuild and
re-sign against the new head, not silently retry the old intent.
Same-nonce consume/revoke/expire races may confirm only one terminal transition.
Generation/issuance races cannot lower active policy.

Before SQLite commit: DB stays before; witness may retain pending. No automatic
abort/release or repair; supervision needed. After real SQLite commit with lost
ack: run remains BLOCKED, sqlite_transition_committed is not asserted from an
uncertain acknowledgment. Explicit recovery can independently read/prove the
exact target and complete the same witness reservation.
After witness confirmation with lost reply: original request+signed prepare
ticket can recover the SAME last checkpoint. Repeating recovery is an observation,
not another confirmation or authority. Older receipts stop matching after a
newer transition. Pending PREPARED reply loss without original ticket blocks.

Recovery requires original valid dual-signed request AND exact signed PREPARED
ticket. It never issues/consumes/revokes/expires, recreates storage, changes scope,
selects new roots, repairs history or contacts providers.
Unavailable witness, lost intent, partial/corrupt storage or different target
=> BLOCKED / manual approved recovery design remains absent.

## Time, bounds and truthful indicators

RFC3339 UTC-Z strings with original parser, integer microseconds, max300s positive
challenge window, persistent application-clock watermark. ISSUE observation
equals issue time. EXPIRE requires observed time >= recorded expiry, but this is
an UNAUTHENTICATED input clock. Witnessing EXPIRED proves a state transition,
not that physical wall-clock expiration occurred. trusted_clock_verified and
temporal_expiration_proven remain FALSE in every result.

Bounds inherited: uint32 generation/sequence, 2048 witness confirmations,
2048 challenge rows, 8192 audit events, 8192-char stored record strings,
256-node/depth8 plain request copier. No eviction/reset.
Signed-history verification and complete snapshot hashing are linear bounded
work; no large-scale benchmark, constant-latency or general DoS guarantee.

Five separate observations:
transition_mathematically_verified; transition_reserved_by_reference_witness;
sqlite_transition_committed; checkpoint_mathematically_verified;
reference_ledger_matches_witness. They become true only from actual verified
math, live reservation, validated acknowledged/recovered state and exact signed
latest checkpoint in the fixture. A blocked outcome can truthfully show some
completed facts; it never promotes physical authority.

Always FALSE: trusted_owner_identity_verified, owner_identity_authenticated,
independent_custody_verified, protected_witness_storage_verified,
hardware_antirollback_verified, p256_tpm_origin_attested,
physical_sandbox_verified, physical_network_deny_verified,
key_enrollment_authorized, installer_authorized, build_authorized,
deploy_authorized, safe_to_resume, execution_allowed/execution_authorized,
and all inherited physical/operational gates. No argument/environment/test mode
can make them true. No INSTALLER_READY/physical certification state.

## Required negative proofs

A. Old DB + preserved witness: old before hash/sequence/used transaction fails.
B. Both DB and witness/expected state reset to old coherent genesis: old request
   can confirm again. Guarantee loss is deliberately demonstrated, not hidden.
C. Valid ephemeral signatures + no real enrollment: math true, owner false.
D. Valid checkpoint + RAM witness: checkpoint math true, protected storage/
   TPM/HSM/service/antirollback physical proof false.
E. EXPIRED on supplied clock: state confirmation true, trusted expiration false.
All cases remain installer/execution unauthorized.

## Minimum real-anchor recommendation — NOT activated

Recommended architecture proposal: independently enrolled live witness with
authenticated request/reply protocol, separately pinned public identity,
durable monotonic state/reservations/tombstones and protected history that cannot
rewind via ordinary backups; explicit supervised restore/rotation/loss plan.
Windows adapter uses authenticated public receipts and independent expected head;
disk copy alone cannot choose a root/head. Keep fail-closed on outage; do not
offer "offline fallback" via a local restorable copy.

| Option | Security/simplicity/Windows | Offline/recovery/lockout | Cost planning |
| --- | --- | --- | --- |
| Independent authenticated protected witness | Clear separate rollback domain; remote enrollment/transport/storage require review | Online transitions; no fallback, supervised protected restore; outage blocks | Provisional low-volume R$0–100/mo inference, not vendor/all-in quote |
| Proven compatible TPM NV mechanism | Local integration complex; only after actual capability/policy/attestation proof | Offline possible in separately designed protocol; clear/replacement risks permanent lockout | Existing hardware may have R$0 recurring service fee, engineering/replacement separate |
| Hybrid | More independent failure domains, greater complexity | Recovery policy must avoid both anchors rewinding or mutually locking out | Provisional R$0–200 only if existing allocations suffice, unproven total |
| Corporate/HSM | Only if separately justified; signing hardware alone is not ledger monotonicity | Enterprise lifecycle/key-loss dependency | No demonstrated <=R$200 quote; budget gate remains blocked |

These are engineering planning inferences, not purchases or guarantees.
Infra cap R$200/month, any spending needs separate approval. No contract/account/
provider/service/cloud was activated.

Primary docs consulted 2026-10-09:
[TCG TPM2 structures](https://trustedcomputinggroup.org/wp-content/uploads/Trusted-Platform-Module-2.0-Library-Part-2-Structures_Version-185_pub.pdf)
defines counter capabilities; it does not prove support/policy on owner's host.
[Microsoft TPM key attestation](https://learn.microsoft.com/en-us/windows-server/identity/ad-ds/manage/component-updates/tpm-key-attestation)
describes independently attestable key properties, not whole-ledger rollback proof.
[AWS storage pricing](https://aws.amazon.com/dynamodb/pricing/) has storage
allowances; they do not price/establish a complete protected signing witness.
No commands from these documents were executed.

## Objective approval/rejection checklist before physical install

PASS only with independently reviewed evidence, not caller booleans:
- authentic owner/collector enrollment, separate custody and explicit consent;
- separately protected witness root, authenticated live expected head and
  persistent pending/terminal records with no unsafe backup rollback;
- protocol/schema/domain test vectors and V2->V3 authorized genesis migration;
- compromise/revocation/rotation/reset/recovery and lost-device/denial drills;
- real clock/freshness contract if required by operation;
- actual TPM/P256 attestations if used, no assumed algorithm/support;
- physically evidenced sandbox/network denial from separate #1114 front;
- verified binary/package provenance, explicit build/install/deploy approval,
  budget decision and supervised fail-closed rollback/restore procedures.

REJECT missing/conflicting/unknown evidence, both-anchor restore, untrusted pin,
arbitrary resync, stale phase/intent, pending ambiguity, altered signed history,
unproven custody/hardware/time, unavailable witness or automatic repair/retry.
No physical gates are approved in this PR. Integration with #1114 is separate.

## Post-green adversarial review and reproduced corrections

First run37907650216 at07c7f590b3aa3c1e9156651cb82eb0dc59b461b3:
Windows/Linux each99 new +282 regressions =381 passed,0 errors/failures/skips.
After that green run the full diff review found two gaps:
1. Successful output exposed only PREPARED ticket, not a CONFIRMED verifiable
   receipt. Reproduction test_confirmed_result_exports_verifiable_reference_receipt.
   Minimal fix returns a deep-copied validated public CONFIRMED envelope.
2. Original-intent request digest in witness history was format-checked but not
   included in checkpoint signature. Changing it passed history validation.
   Reproduction test_original_request_digest_is_authenticated_in_signed_history.
   Minimal fix binds recomputed request_sha256 into BOTH signed checkpoint phases,
   requires equality in history/pending and checks it on prepare/recovery.

Reproduction commit e387245119d3b0e1fd8046d53a8f0985863571e7;
run37907893972 bothOS:101 new tests with2 failures, old282 pass,0errors/skips.
Original failing tests retained; receipt-key assertion inspects keys instead of
printing the synthetic public signed payload on failure, same semantic assert.
No private or real owner key was ever logged/exported. No V1/V2 test or source
was changed to accommodate V3; fixes are confined to this new reference contract.
Additional cases cover missing signed request digest and tampered pending digest.
The final coordinated source/test/doc change uses one Git tree commit.

## CI and audit evidence

New dedicated Windows/Linux hosted workflow, exact PR head, pinned actions,
cryptography50.0.2 + isolated PyYAML6.0.3, hosted guard before test-key imports.
Runs new V3 suite plus UNCHANGED100 #1115,87 #1113,35 #1109,27 #1110,33 #1111.
Compile/YAML/static safety/old CAS inventory. Runtime mocks deny socket/subprocess
during the full chain and file opens in pure public verification. Explicit
temp-fixture SQLite writes are intentional; no claim of zero ALL filesystem I/O.
Successful output includes the public CONFIRMED receipt envelope, independently
verifiable against the separate TEST pin and exact expected checkpoint; PREPARED
ticket is separate. Both returned artifacts are deep copied. CI artifact uploads
contain counts/head ONLY, no DB/private key/signature/payload files.
Final measured counts/run links, failures and corrections belong in PR report.

Implementation exclusively GitHub APIs, tests exclusively disposable hosted CI.
Only initial reading of user attachment occurred on device; no subsequent host
access/implementation/test experiment. No PC/security/TPM/Hello/registry/ACL/
firewall/real-key/production/#1114/main/frozenCore/ruleset mutation, collector,
installer, provider/billing/purchase/merge/deploy or automatic service/repair.
