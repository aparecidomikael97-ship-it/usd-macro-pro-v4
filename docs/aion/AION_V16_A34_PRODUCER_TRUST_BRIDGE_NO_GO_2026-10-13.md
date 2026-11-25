# AION V16-A.34 — External producer trust bridge (DESIGN, NO-GO)

Status: **BLOCKED / DESIGN ONLY / NO INSTALLATION OR DEPLOYMENT**.
Reference child: Draft #1246, Outbox HEAD `95b420301eaa75fdffabbca84e6f3e6f77167d63`.
Independent reference: Draft #1224, V5 HEAD `e9cd8854e38c9fc0d317adc0a5b07569cde40532`.
Authoritative tracking: #1190 (Checkpoint), #1178 (source/rollback), #1117 (first installation).
No provider, external account, root, HUMAN_OWNER credential, witness, payment or deployment has been chosen or activated.

## 1. Verified boundary and negative evidence

The current Outbox is deliberately fail-closed:

- In `dispatch_claimed`, A.31 stores the **nonterminal** `BLOCKED_PRODUCER` under scoped, lease-guarded CAS before it could access `adapter.send`; the same `INDEPENDENT_PRODUCER_NOT_ENROLLED` exception follows. No sender or producer effect can be inferred from the local code.
- In `reconcile`, A.33 denies before accessing an adapter `reconcile` property or calling it for historical SENT/UNCERTAIN. A read-only-sounding callback is still arbitrary executable code.
- A.24 quarantines self-attested positive results. A.20 quarantines negative results and apparent absence. The original post-send code behind the hard stops is **unreachable**, not a working attested producer flow.
- CI for #1246 exact HEAD: Quality 6162 tests / 23 historical Outbox errors; Security, Certification and Release Readiness CI workflows SUCCESS. These do not establish external security or physical release readiness.

A.32 tests directly proved that the unchecked readback boundary could access a malicious dynamic descriptor and callback **before** A.33 corrected this in the LAB candidate.

## 2. V5 reusability — a hard semantic firewall

V5 is not a producer receipt authority. Verified source, exact V5 HEAD:

| V5 component/contract | Exactly what it establishes | Why it CANNOT authorize Outbox |
|---|---|---|
| `contracts.root_contract` | Requires root IDs beginning `fixture-`, provenance exactly `FIXTURE_UNENROLLED` | No real out-of-band owner/producer root enrolled |
| `contracts.binding_contract` | Restricts operation to `fixture-causal-read` or `fixture-state-read` | Does not attest producer **send**, external commit or fenced no-effect |
| `contracts.PROOFS` | Institutional custody, independent consent, trusted time and revocation channel all `UNKNOWN` | No authority to turn UNKNOWN into true by mapping booleans |
| `contracts.receipt_contract` | Ed25519 signature over the domain-separated V5 query/read response | Signing a *read snapshot* is not a causal receipt for an external effect |
| `admission.ReferenceReceiptAdmission` | Local ISSUED/RESERVED/CONSUMED and monotonic floors within caller-managed SQLite | Joint rollback of DB and retained local references can erase consumed receipts/revocations |
| `contracts.outcome` | Productive credential, owner consent, independent monotonicity and root remain false | A caller must not map `REFERENCE_DURABLE_ADMISSION_UNTRUSTED` to PROD_GO |

V5 canonicalization, strict schema patterns, nonce handling and proof/revocation algorithms are useful *reference techniques*. They are not interchangeable purpose domains and are **not imported as productive trust roots**. A genuine bridge must have separately enrolled producer identities, signed-domain types, independently retained monotonic heads, and a permission mechanism explicitly reviewed for external effects. Do not change the meaning of fixture aliases or the V5 proof flags.

## 3. External trust components required BEFORE an effect boundary

A. Independently administered enrollment registry (the loader, request, repo and adapter cannot enroll their own root):

- Scope: `owner_id, tenant_id, workspace_id, host_identity, producer_issuer_id, producer_account_id, permitted_action_class, canonical_intent_digest, idempotency_key`.
- Current public trust roots/pins, authentication method, policy version, enrollment generation, valid-from/until, revocation/rotation state, operator custody evidence, provenance of OWNER ceremony.
- Enrollment observation has a signed/otherwise externally authenticated freshness challenge and its latest current head verified outside the host and outside the same admin/backup failure domain.
- Reject mismatched scope, resource/account rebind, stale epoch, expired or revoked issuer, self-provisioned key/pin, and a registry snapshot with no independently checked current head.
- **No fallback** to GitHub blob SHA, a token or role ADMIN, localhost SQLite, a V5 fixture signature, environment flag, or local copied head.

B. Producer-enforced operation fence:

- The producer must verify the same scoped, non-transferable enrollment/fencing capability **atomically with its own acceptance of the requested effect**. A pre-send check in the AION process alone has a time-of-check/time-of-use gap and does not stop delayed attempts, parallel regions or previously accepted jobs.
- Producer-side uniqueness covers account + tenant/resource + canonical intent digest + idempotency key + attempt/fence generation. Document real guarantees for replicas, retries, queue workers and crash recovery.
- For requests with insufficient evidence, producer must refuse before performing any external action; if its own fence is unavailable, AION remains blocked.

C. Independent witness/head:

- Separate failure domain and operator administration from the PC, AION DB backups, source repo and effect-producing adapter.
- Authenticated latest epoch/sequence/head and revocation observation, challenge freshness, monotonic/fork detection, durable read-after-write semantics and recovery policy. One historical valid signature is insufficient.
- If custodian/clock/key availability is UNKNOWN, do not send, reconcile via untrusted callback, retry or compensate.

D. Real HUMAN_OWNER and host proofs:

- Explicit scoped owner consent separate from issuer/controller signing, trustworthy device/host binding and provable custody. A synthetic fixture, Windows provider list or guessed TPM availability does not prove this.
- Onboarding of any real credential, hardware ceremony, storage/account or customer data requires distinct approval and physical/institutional evidence.

## 4. Three logically distinct typed admissions (none implemented)

These conceptual methods describe *review gates*, not callable production APIs.

| Admission | Required independent proof | Permitted state mutation only AFTER proof | Without proof |
|---|---|---|---|
| `PRE_SEND_ENROLLED_AND_PRODUCER_FENCED` | Current registry + owner/host/tenant/account binding + witness head + producer-enforced idempotency/epoch fence, bound to exact decision and attempt | Transactionally reserve an enrolled attempt before crossing the effect boundary; producer also validates fence at ingress | Retain `BLOCKED_PRODUCER`/no-send. Do not simply flip it to CLAIMED |
| `POSITIVE_COMMITTED_CAUSAL_RECEIPT` | Producer-origin signature/authenticated readback of committed effect with scope/digest/attempt/key/fence, independently verified against current head and revocations | Conditionally `UNCERTAIN/SENT→CONFIRMED` and add effect ledger exactly once under CAS, subject to immutable proof identifier | Keep UNKNOWN; no effect ledger, no Saga completion |
| `NEGATIVE_NO_EFFECT_FENCED` | Producer durably commits **terminal no-effect AND a fence preventing any late effect of old attempts**, across all workers/queues/regions, before issuing authenticated receipt | Only after nonrollback witness/readback and exact CAS may a separately approved retry/abort policy be considered | Keep UNKNOWN; never infer absence from `found=false`, timeout, HTTP 404, accepted=false, retryable=true, or an unfenced signed lookup |

Positive/negative receipts need separate signed domains, canonical closed schemas, exact owner/tenant/workspace/host/account/operation/payload_digest/idempotency_key/attempt/epoch/challenge/head/policy binding, signature/issuer chain/revocation checks, replay denial, expiry and causal readback. A valid generic V5 signed *read* cannot be silently cast to either type.

## 5. Race and recovery rules

1. **Pre-send vs revocation:** If root, account, tenant ownership, host grant or fence can change between lookup and producer acceptance, producer must validate an epoch-bound non-transferable capability at the effect commit boundary; re-reading local state alone is not adequate.
2. **Lost ACK after producer commit:** Keep `UNCERTAIN`; repeat only trusted readback, not send. A missing receipt is not absence of effect.
3. **Lost ACK for fenced no-effect:** No effect may happen later because the producer has already durably rejected old attempts; lacking verifiable proof, remain `UNCERTAIN`.
4. **Rollback of DB plus retained head:** Must be caught by current external head. If the witness can also be restored by the same custodian, this guarantee is unproven.
5. **Stale, conflicting and cross-tenant receipts:** Reject before any Outbox or Saga mutation. A verified receipt for one account/action must never authorize another.
6. **Producer/reconciliation callback may itself perform work:** No adapter attribute getter or callback is accessed without the same authenticated capability and approved sandbox/side-effect policy.
7. **Indefinite unavailability:** Safe no-progress is preferable to duplicate effects or false confirmation. Manual review does not manufacture producer no-effect evidence or bypass the fence.
8. **Offline local mode:** Read-only analysis and education can be scoped separately in the product design; protected external effects stay disabled while trust domains cannot be checked.

## 6. Required acceptance matrix (future LAB tests are not physical proof)

| Negative case | Correct outcome |
|---|---|
| V5 `fixture-` root or `FIXTURE_UNENROLLED` presented as producer enrollment | BLOCK, zero adapter access |
| V5 `REFERENCE_DURABLE_ADMISSION_UNTRUSTED` treated as evidence of external effect | BLOCK, zero CONFIRMED/effect ledger |
| `UNKNOWN` custody/consent/time/revocation channel presented as true | BLOCK |
| Root pin carried only inside callback or request | BLOCK |
| Correct signature but wrong tenant, workspace, owner, host, producer account or action digest | BLOCK |
| Revoked, rotated, stale or expired pin; wrong producer epoch | BLOCK |
| Old signed head replay after restoring AION DB and local retained head | BLOCK against **independently read** current external head |
| Registry/witness unavailable, forked or incoherent | BLOCK, no fallback |
| Malicious `send` / `reconcile` attribute getter | 0 reads, 0 callback invocations while unenrolled |
| Positive `confirmed=true` from unverified adapter | UNKNOWN, no ledger/Saga advancement |
| `found=false` / `retryable=true` from same adapter | UNKNOWN, no resend |
| Valid *signed* absence from read-only cache but no producer terminal fence | UNKNOWN, no resend |
| Two simultaneous requests with same logical idempotency key in separate workers/regions | Producer rejects duplicate effect at commit |
| Effect arrives after purported NO_EFFECT_FENCED | Impossible by tested producer enforcement; otherwise NO-GO |
| Commit/ACK loss, power loss, partial commit and witness outage | UNKNOWN, evidence-only recovery |
| Previous outbox `BLOCKED_PRODUCER` and a new issuer becomes enrolled | NO automatic unblock, require new reviewed transition/owner authorization |

These are *future* executable acceptance tests and require real independent evidence to be called PASS. The historical 23 Outbox post-send test errors on #1246 remain RED; the A.12 37 + A.16 8 original ZIP cases have not been executed in the current session.

## 7. Integration order and independent approvals

1. Owner/technical review: choose a producer whose **documented API** actually supports committed causal receipt, producer-side idempotency and terminal no-effect fencing. If no vendor supports it, the protected action class remains NO-GO; do not weaken the requirement or substitute self-attestation.
2. Select genuinely independent root/head custody and recoverability with verified cost, residency/LGPD, operators and revocation; respect the R$200/month ceiling, **without committing funds or opening accounts**. Operator ownership and backup-failure separation are an architectural prerequisite.
3. Agree on immutable schema + signed domain for producer-specific receipt, trust distribution, host/HUMAN_OWNER ceremony, witness current-head, and recovery from loss/compromise. Record the explicit approval request per external action.
4. Only then implement a separate, typed productive verifier and producer adapter in an isolated Draft, retaining hard stops as default. Prove all negative cases *before* enabling a positive path, with end-to-end tests against real source evidence.
5. Re-run original A.12/A.16 37+8 only when their original archives/manifest and genuine source hashes are recovered. Execute physical first-install 20 requirements separately; no CI green or document can waive them.
6. Separate review for any merge, deploy, installation, credential creation, Worker activation or spending.

**Decision now:** A.34 is a nonoperative interface/security design. No productive `send` or `reconcile` path, no vendor selection, no trust enrollment and **no claims of security homologation**. 0/6 P0 homologated, 20/20 first-install requirements BLOCKED.
