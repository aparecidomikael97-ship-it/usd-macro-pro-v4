# A190 / G127 — External Custodian Authority Contract (ADR, LAB ONLY)

Date: 2026-10-26
Status: PROPOSED / NOT IMPLEMENTED / NOT HOMOLOGATED
Parent: G126 Draft #1618, exact parent HEAD ecea036fd361377a4d89e55e6229ee482116f647
Related: A190 issue #1486; SQLite/native issue #1477; G120–G126 Draft #1610–#1618.
Absolute invariant: 0/6 P0 homologated, HARD NO-GO, UNCERTAIN, ZERO_AUTO_RESEND.

## 1. Decision and non-decision

Decision D1: the reference design for the next falsifiable *offline contract work* is a
separate authority that owns a monotonic epoch and the original, canonical
business-event reservation. The AION process must never have administrative
access, write access to the authority's state, or a capability to sign arbitrary
authoritative receipt payloads. The authority must authenticate and authorize the
request and must independently generate its receipt fields. Cloud KMS alone,
a file signature made by a client, or a local sidecar does not meet D1.

Decision D2: compare **AWS DynamoDB conditional transaction + AWS KMS asymmetric
signing + S3 Object Lock COMPLIANCE** as a reference research design, against
**Google Firestore transaction + Cloud KMS asymmetric signing + Cloud Storage
Bucket/Object Retention Lock**. These are capability examples, NOT approved
vendors or deployable configurations.

Non-decision: no real custodian/provider, account, region, IAM role, key,
retention time, SLA, price or identity-verification provider has been approved.
No paid API, WORM policy or customer data may be used in this LAB. This ADR
creates NO additional authority or independent evidence by itself.

## 2. Trust principals and powers (must be established by evidence)

| Principal | May do | Must not be able to do |
| --- | --- | --- |
| HUMAN_OWNER | Authenticate with separately controlled original enrollment; approve a scoped first action | Retroactively sign a different original event or self-repin root after failure |
| AION orchestrator / compromised host | Submit a candidate request; display status; seek explicit reconciliation | Mint an original owner proof, reset epoch, modify remote custody or trigger automatic resend |
| Independent authority service | Check the actual owner proof, canonical event key, authorization and monotonic epoch; reserve at most once; issue bound receipt | Trust any client-provided provider outcome, accept unsigned root replacement, erase history silently |
| Separate custody operator / immutable log | Archive authorized original reservations and evidence under governed retention | Rewrite an already retained version through AION app credentials |
| Real external effects provider | Execute a business action and produce independently verifiable identity + causal receipt | Delegate the final outcome claim to AION's local synthetic fixture |
| Privileged cloud/project/account administrator | May retain emergency disaster-recovery power under policy | Be called independent of AION if the same stolen principal can delete all resources and re-register roots |

Admin account closure, authorized deletion, credential compromise and retention
expiry remain residual threats. No single cloud account provides unconditional
immortality. Real separation requires distinct operator/control plane, public
key provenance, authenticated version/rotation/revocation, and an external audit
trail the local app cannot backdate.

## 3. Canonical event identity: reject request-id substitution

The authority must derive or verify one canonical business-effect identifier
from trusted, domain-specific fields (tenant, provider account, effect type,
resource ID, immutable economic payload digest and approval scope). It must
bind this to the approved HUMAN_OWNER identity and original enrollment nonce.
Do NOT trust a new random request_id, a new self-declared event_id or a new
synthetic certificate as proof of a new economic effect.

A first attempt has immutable identity even if HTTP connection, process,
machine, timestamp or request ID changes. If no trustworthy canonical mapping
can be derived, fail closed: HUMAN_REVIEW_REQUIRED. Never use only clock time
or a generated UUID as semantic uniqueness.

## 4. Proposed state machine / API contract (architecture, not code)

Provisional operations:
- QueryCanonicalEvent(canonical_key) returns signed bound history plus freshness;
  UNKNOWN and timeout are not absence.
- ReserveOriginal(original_owner_proof, canonical_key, payload_digest,
  expected_epoch) atomically moves MISSING -> RESERVED and epoch n -> n+1,
  returning a signed reservation with remote counter, account and key version.
- MarkAttemptDispatched(reservation_id, dispatch_identity) is permitted only
  after durable original reservation and audited retention evidence. It marks
  uncertainty; it DOES NOT report execution.
- ReconcileProviderReceipt(reservation_id, independently authenticated
  provider_receipt) may record an observed outcome, subject to provider-specific
  idempotency and replay rules, but MUST NOT automatically initiate a retry.
- ReadAuditProof(reservation_id) returns signed authority record, independent
  WORM version identifier and verified hash chain / inclusion evidence.

One authority-side compare-and-swap/transaction must serialize canonical
event reservation and monotonic epoch. Cross-service DynamoDB↔S3 or
Firestore↔Cloud Storage publication is NOT atomically committed merely
because both APIs returned success independently.

Adopt fail-safe ordering:
A. authenticate owner and canonical scope with pinned roots;
B. perform unique reservation+counter in the authoritative transaction;
C. write immutable archive and independently verify its visibility/version;
D. only if A, B, C are attested, emit the *one-shot first-attempt capability*
   bound to the reservation; if B/C fail or are ambiguous, no SEND;
E. after a real effect request, loss of acknowledgement => UNCERTAIN;
F. reconcile with authoritative *provider-generated* evidence and HUMAN_OWNER,
   never infer NO_EFFECT from missing ACK and never auto-resend.

This sequence is a hypothesis: failures between B and C require a defined
repair procedure that cannot mint a second first-attempt capability and cannot
hide an epoch gap. Do not claim atomicity across these systems. Specifically
a signed receipt for storage alone is not a real provider settlement receipt.

## 5. Negative acceptance gates — REAL evidence required for P0

G127-T1 / local joint rollback: roll back DB + WAL + SHM + snapshot + local
witness plus process restart. The **actual independent authority** must detect
stale epoch and refuse read/write/first effect. A mocked remote ledger does
not pass this gate; the verifier must pin a key externally from host control.

G127-T2 / semantic duplicate: two request IDs and two synthetic local event
IDs for the SAME business effect. Exactly one original reservation; subsequent
requests DENIED/QUARANTINED with actual authority logs. A test that changes
the canonical business effect is not a duplicate test.

G127-T3 / missing ACK: provider effect can already have executed before
network crash. State UNCERTAIN and ZERO_AUTO_RESEND across process restart,
offline queue, budget shutdown and restored database. Only independent
provider-causal receipt can resolve actual outcome; no inferential green.

G127-T4 / issuer spoof and repin: user-controlled key, local root file,
reissued same-host owner enrollment, key substitution or self-signed provider
statement cannot replace separately verified trust anchors. Key rotation and
revocation must be authenticated and versioned independently.

G127-T5 / OS-native SQLite: native SELECT cache after revoked permission,
explicit default-VFS connection, non-guarded sqlite3.connect, WAL write and
same-inode old-byte restoration must NOT bypass the intended security boundary.
If any native path can bypass it, retain P0-5/6 RED and block affected
operations. See #1477 and experimental #1479/#1480. A separate local Python
wrapper, progress_handler or filesystem hash cannot demonstrate this gate.

G127-T6 / failure and cost: offline authority, unreachable DNS, unauthenticated
response, stale epoch, missing archive, KMS unavailable, project budget pause,
revoked key, leaked/removed account, or data lifecycle deletion must fail
closed. Expected output: NO_FIRST_SEND / UNCERTAIN / HUMAN_REVIEW, not success.
Recovery and long-term retention under failed billing must be explicitly proven.

G127-T7 / original real HUMAN_OWNER and effect origin: a cloud user login,
KMS signature, JWT or sample provider claim does not by itself establish
HUMAN_OWNER original enrollment or actual provider execution. Require
independently obtained origin proof and causal provider receipt before any
P0 acceptance claim.

G127-T8 / cross-OS evidence and cost audit: execute full original
Quality/Security/canonical acceptance without waivers on Windows and Ubuntu;
cite exact SHA, runner logs and real refusal, not only a passing synthetic
unit test. Unchanged five genuine external acceptance failures MUST remain
visible and RED until actually solved.

## 6. Threat/negative-result ledger (do not lose evidence)

- A189 #1485: dual local DB+witness rollback bypasses local monotonicity.
- G120–G125: synthetic owner proof and synthetic separately signed
  provider-like EXECUTED claim compose, yet real provider outcome UNKNOWN.
- G126 #1618: while the same live local epoch remains intact, old
  same-inode bytes can be detected; hostile host re-pin or restart after
  rollback still bypasses the detector.
- A185 #1479/#1480: custom native SQLite VFS xRead is bypassed by cached
  SELECT; alternative default-VFS connection can bypass customized xWrite;
  WAL must be considered separately. A progress handler can be removed by
  the host and is not external authority.
- Signing bytes sourced entirely from the compromised client proves at
  most that a signing API was called, not genuine custody, original owner
  or a real provider effect.

## 7. FinOps gate and availability conflict

No vendor selection until region-specific **total** cost model includes
transaction reads/writes, storage and immutable versions retained over time,
key versions + Sign/Verify, requests, service/network egress, access logs,
taxes, currency movement, contingencies, disaster-recovery retention and
operational staff work. The limit is R$200/month; R$250 is an EXCEPTION
requiring Mikael's specific approval, never an automatic budget expansion.

AWS KMS public example: US$1/month/customer-managed key and ECC
100k Sign requests at US$1.50, but that is NOT the total custody bill.
AWS Settings project spend limits require Paid Plan, have a minimum
greater of US$20 or provider estimate, pause projects, and warn that
90 days of unattended paused state can trigger permanent project-data
deletion. They cannot be the sole retention safety design.

Google Cloud KMS software asymmetric version has a published approximate
US$0.06/month baseline before operations, but Google spend-cap budgets
currently only apply to specified services such as Cloud Run and Vertex,
not Firestore / Cloud Storage / Cloud KMS. Persistent storage can still
accrue costs after a spend cap. Budget alerts and asynchronous caps are
not equivalent to guaranteed all-in BRL ceiling.

Until written budget and human provider/account decision: **NO account,
key, billing plan, retention lock, hardware, live custodian or real provider.**

## 8. Primary sources (checked 2026-10-26)

- AWS conditional writes: https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Expressions.ConditionExpressions.html
- AWS Object Lock: https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lock.html
- AWS KMS pricing: https://aws.amazon.com/kms/pricing/
- AWS Settings spend limits: https://docs.aws.amazon.com/accounts/latest/reference/create-spend-limit.html
- Google Firestore transactions: https://firebase.google.com/docs/firestore/manage-data/transactions
- Google Cloud Storage Bucket Lock: https://docs.cloud.google.com/storage/docs/bucket-lock
- Google Cloud KMS pricing: https://cloud.google.com/kms/pricing
- Google spend caps: https://docs.cloud.google.com/billing/docs/how-to/budgets-spend-caps

## 9. Evidence required before changing status

- Real independent operator/issuer/root, not keys provided by caller.
- Real owner enrollment origin and independently authenticated provider receipts.
- Remote atomic counter+canonical reservation proven under adversarial replay.
- Independent WORM archive with cross-system crash-gap reconciliation proven.
- Native SQLite/OS principal boundary on Windows AND Ubuntu.
- Verified H0 fail-closed, no automatic resend, outage and recovery.
- Budget formally approved after complete regional quote; retention safety.
- Original five external RED gates become green because the hostile cases
  are genuinely blocked, not because tests are skipped/renamed.
- Distinct sign-off per one of the six P0. No blanket homologation.

**Current status remains 0/6 P0 HOMOLOGATED, HARD NO-GO.**
No production/Worker changes, no merge/deploy, no SEND, no paid accounts,
and no new claims of external trust from this documentation-only PR.
