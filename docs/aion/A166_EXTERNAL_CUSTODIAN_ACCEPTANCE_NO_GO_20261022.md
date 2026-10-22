# AION P0 / H0 — A166: custodian acceptance criteria and evidence provenance

**22 October 2026 · Draft stacked on A165 (#1454) · READ-ONLY LAB.**

**Verdict: HARD NO-GO · 0/6 P0 homologated · ZERO_AUTO_RESEND.**

A165 validated the *format* of four mathematical signatures (V1/V2/R1/R2)
bound to an A164 policy floor. It did not establish any external company,
administrator, account, immutable storage, real timestamp or vendor effect.
A166 changes the next-stage checklist into a typed, testable intake standard
while refusing to equate a dossier, signature or string with real-world truth.

## Acceptance obligations — R1 and R2, separately

Each custodian must supply all eight classes. Each row below is an
**objective request for real independent proof**, not evidence already held.

| Kind / intake channel | Minimum external acceptance evidence | Counterexample to reject |
|---|---|---|
| LEGAL_IDENTITY / OFFICIAL_REGISTRY_READBACK | Official legal registry lookup, contract party and beneficial-control chain, reviewed independently of the applicant | Company names typed into signed JSON |
| ADMIN_CONTROL / PROVIDER_CONTROL_PLANE | Independent readback of distinct administrators, privilege assignments, emergency recovery and revocation capability in the provider control plane | Two different IDs under the same controlling superadmin |
| KEY_PROVENANCE / HSM_POLICY_ATTESTATION | R1/R2 public-key pin provenance, isolated key custody, HSM/KMS policy, rotation and destruction evidence reviewed outside AION | Two process-generated Ed25519 keys |
| ACCOUNT_SEGREGATION / PROVIDER_CONTROL_PLANE | Separate real provider account/tenant, billing authority, admin recovery and failure domain, with cross-tenant denial exercise | Different tenant labels in one account |
| WORM_READBACK / IMMUTABLE_OBJECT_READBACK | Original external object version readback; retention/lock policy from provider; deny-delete/overwrite evidence including privileged actor | Self-signed “immutable: true” flag |
| REVOCATION_PROPAGATION / EXTERNAL_REVOCATION_CHALLENGE | REVOKE_ALL propagated and independently observed after a fresh challenge, including offline/delayed R1 or R2 | Both compromised custodians re-signing an old floor |
| ROLLBACK_RESTORE / INDEPENDENT_RESTORE_DRILL | Real hostile restore of AION policy+anchor and reboot, while provider-retained monotonic head and revocation are immutable; fork/stale denied | Local rollback of all test data together |
| NONCE_TIME / TRUSTED_TIME_READBACK | Unreused challenge issued/retained outside AION and independent freshness/expiry source, with replay and clock-drift denials | Caller-supplied clock/nonce that can be rolled back |

## Machine-checkable candidate intake (not actual verification)

The test-only offline contract in `tests/aion_p0_a166_review_contract.py`
requires a total of **16 records** (8 per role); exact `ledger_id`,
`epoch`, `policy_generation`, `policy_digest` and `challenge_nonce`;
fixed read-only audience; freshness within the A165-style 20-second floor;
unique evidence references and typed claimed source channels. Administrative,
HSM, account, immutable-storage, revocation and restore *source labels* must
also be separate across roles.

Records may only advance from **invalid** to **structurally complete but
quarantined**. This deliberately tests a fully forged dossier: one test process
manufactures all 16 records and distinct-looking issuer IDs; the result stays
`LAB_QUARANTINE_MANUAL_REVIEW`, with zero authority flags. Caller-supplied
source names, SHA-256 strings and timestamps are **not** authenticated source
records. No test invents a bank, HSM, vendor contract, audit log or receipt.

The checked-in JSON registry
`docs/aion/evidence/aion_p0_a166_custodian_acceptance_open_20261022.json`
keeps all 8 requirements for each role as **missing**. It contains no customer
personal data, credentials, secret key, mock invoice or counterfeit proof.

## Rules for real acceptance — outside this LAB

1. **Independent enrollment and custody.** A trusted human examiner must
   verify provider legal identity and beneficial/administrative independence
   using sources not alterable by AION, the issuer of R1/R2, or a shared admin.
   Record how identity was authenticated and how revocation works.
2. **Independent control and storage tests.** Collect provider-originated
   readbacks and append-only/immutable receipts in independent account and
   fault domains, and demonstrate enforcement against privileged deletion,
   rewriting, backup restore and old-highwater replay.
3. **Strong adversarial exercises.** Rotate and revoke keys; isolate a role;
   simulate partial outage, clock skew and uncertain ACK; after restoring an
   older local image, a fresh authenticated external read must reject stale
   policy and re-signed old floors. Failure, ambiguity or unavailability
   **always blocks**; no automatic resend or retry.
4. **Binding and audit provenance.** Preserve original binary/signed objects,
   source-verification method, independently pinned keys, hash, timestamp,
   one-time challenge, ledger/epoch/generation/digest, issuer and examiner.
   Separate who collects evidence from who decides. Revocation invalidates
   earlier proofs; an expired reply cannot extend any policy floor.
5. **Owner, FinOps and external effect are separate gates.** Genuine fresh
   HUMAN_OWNER approval using authorized ceremony, explicit budget and vendor
   agreement, real provider causal `COMMITTED_EFFECT` or terminal
   `NO_EFFECT_FENCED`, all 32 historical proof issues, Quality/Security
   and full P0 homologation remain mandatory. “Vamos lá” does **not** grant
   consent to provision accounts, spend money, deploy or execute.
6. **Decision record.** A separate independent reviewer documents ACCEPT /
   REJECT / UNKNOWN for each real obligation with primary evidence. UNKNOWN
   is REJECT for H0. Even complete acceptance documentation cannot
   automatically flip production flags: require a separate explicit formal
   owner authorization and end-to-end homologation.

## Fail-closed invariants and test scope

- A166 has **40 test-only** adversarial assertions. Missing/duplicate
  records, shared claimed domains, wrong issuer channel, stale floor,
  nonce/ledger/digest mismatches, fake source, unexpected `verified` flag
  and malformed input must stay `LAB_HARD_BLOCKED`.
- All 16 forged but consistent records yield quarantine; the code never
  authenticates an external source and never sets any operational permission
  to true. The code is **inside tests/**, not an H0 runtime module.
- CI must separately run A166, cumulative A145–A165 regression,
  A151 static LAB/runtime fence, A152 E0–E5 documentary NO-GO,
  restore/credential/write-denial guards and the 32 external provider proof
  crosswalk. Expected numeric total: **1,152 per OS = 2,304** check
  executions, only if Actions actually reports successful completion.
- No production issuer, provider account, WORM bucket, third-party witness,
  key enrollment, workflow executor, Worker, merge, deploy or spend.

**The next genuinely new proof cannot be self-created in this repository.**
It requires real independent custodian/vendor evidence and explicit HUMAN_OWNER
authority for any procurement or external test. Until then, keep HARD NO-GO.
