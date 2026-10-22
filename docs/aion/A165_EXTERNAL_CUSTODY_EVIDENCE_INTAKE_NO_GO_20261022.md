# AION / P0 H0 — A165 Evidence intake for independent custodian review

**2026-10-22. Isolated Draft stacked on A164. HARD NO-GO · 0/6 P0 · ZERO_AUTO_RESEND.**

## Rationale

A164 (PR #1453) verifies an R1/R2 dual-signed nonce-bound, generation-
and-digest-bound synthetic revocation floor and detects an old A163 policy
plus old anchor **only when a later floor was preserved separately**.
A164 also proves a negative counterexample: two compromised synthetic
auditors can sign a stale policy under a fresh nonce, so no cryptographic
algorithm may infer independent custody from signatures alone.

There was no strict *custodian administrative evidence intake contract*
tying declared organization, real-world administrator, provider account
and storage failure domain to the existing signed R1/R2 policy floor.
A165 adds a conservative, read-only schema. This is **NOT the establishment
or verification of external provider custody**.

## New synthetic evidence protocol

`aion_p0_a165_external_custody_evidence_lab.py` checks:

- Exactly **V1/V2 reviewer public keys** supplied by the caller, distinct
  from both R1/R2 auditor keys and the A163 policy issuer root. It does
  not trust keys introduced by a received claim as roots.
- Two `SignedCustodyClaim` records, one each for R1 and R2, carrying
  exact ledger, epoch, generation, chain digest, terminal revocation state,
  request nonce, fixed read-only audience, R1/R2 auditor public key,
  synthetic issuance and expiration time (at most 20 seconds).
- Each record must be signed by the assigned V1/V2 reviewer and by the
  matching R1/R2 custodian auditor as a separate Ed25519 proof of possession,
  under different domain-separated contexts. Four mathematical signatures
  in total. Missing signature, malformed/corrupted base64, swapped roles,
  key substitution, wrong audience or signed history mismatch is blocked.
- Each record **claims** an `organization_id`, `administrator_id`,
  `provider_account_id`, `storage_failure_domain_id`,
  `custody_request_id` and booleans claiming independent administration
  and nonrollbackable storage. If any of these identifiers are identical
  between the two records, the claim set is blocked. **Nonidentical
  identifiers are just different strings** and may be invented by one
  attacker; acceptance at this stage is ONLY syntactic.
- Observation/expiry must fit inside A164's latest floor observation window,
  so a longer-lasting administrative claim cannot prolong a revoked or
  expired floor. A164 itself then revalidates its own two floor signatures
  plus the A163 policy chain, A162 journal/checkpoint/witness/floor
  cross-check, and all remaining H0 denials.
- Even if all four signatures, role pins, distinct-looking claims and
  A164/A163/A162 checks agree, the sole result is
  `LAB_QUARANTINE_MANUAL_REVIEW`.
  Every other outcome is `LAB_HARD_BLOCKED`.

**No returned object can set** true independent organizations, actual
admin separation, immutable storage, genuine V1/V2 provenance, owner
FIDO2 consent, supplier `COMMITTED_EFFECT` or `NO_EFFECT_FENCED`,
checkpoint restore, Worker, execution, retry/resend or P0 homologation.

## Explicit evidence still required from real external parties

A future owner-authorized assessment needs evidence that cannot be minted
solely by the AION machine and is bound to the same ledger/epoch/key IDs:

| Evidence type | Independent verification needed | Fail-closed state today |
|---|---|---|
| Real custodian legal/provider identity | Official source or contractual independent verification, not a self-declared string | UNKNOWN / NOT ENROLLED |
| Separate beneficial owners/admins | Independently sourced admin/tenant controls and segregation, including ability to revoke either without other's privilege | NOT PROVEN |
| R1/R2 keys protected in separate custody domains | Independently audited provider/HSM policies, key provenance and compromise/revocation records | NOT PROVEN |
| Different accounts and failure domains | Platform API attestations/authenticated support evidence with distinct account IDs, immutable provider-side control logs and access segregation | NOT PROVEN |
| Non-rollbackable monotonic policy/epoch floor | Provider-originated durable CAS/transparency receipt and external reboot/restore drills demonstrating an attacker cannot reset both | NOT PROVEN |
| Actual propagation of a terminal revocation | Challenge-response after revocation and an audit trail outside the attacked trust domain, tested under outage/partial failure | NOT PROVEN |
| Fresh requester nonce and external clock | Independently retained challenge state and trusted time or verifiable freshness source not restorable with AION | NOT PROVEN |
| Owner-critical consent and FinOps | Authenticated HUMAN_OWNER/FIDO2 ceremony, explicit procurement approval and quoted cost within approved budget | NOT AUTHORIZED |
| Real first-effect reconciliation | Provider-issued causal `COMMITTED_EFFECT` or terminal `NO_EFFECT_FENCED`, including 32 outstanding producer proof errors | OPEN |

No vendor account, auditor administration, real receipt, consent, expenditure
or challenge service is created by the A165 test suite.

## Counterexample and acceptance

One test harness controls **all** V1/V2/R1/R2 private keys, as well as the
policy issuer, A147 journal, A150 witness, nonce and clock. The harness
can make up different organization IDs, tenant IDs, administrators and storage
domains and sign these false independence claims with all four keys.
A165 purposely reports *mathematical consistency only* and maintains
`actual_independent_administrator_control_verified=False` and
`actual_nonrollbackable_storage_verified=False`. This is not a failure
that can be repaired by increasing the number of signatures.

## CI/isolated deployment constraints

- A165 adds 80 tests (60 explicit scenarios +20 malformed field attacks),
  including forged administrative identities, shared claimed accounts,
  missing V1/V2 signatures, wrong R1/R2 proof of possession, stale
  nonce, expired floors, generation/hash mismatch, revocation, rollback
  and missing previous witness evidence.
- A151's explicit root LAB import fence is extended to A165 and adds
  four checks that still **DENY** `runtime/`, `services/`, `deploy/`
  and dynamic imports of the experimental module.
- Cumulative expected Windows and Ubuntu regressions:
  **A165 80 + A164 80 + A163 80 + A162 70 + A161 70 + A160 30 +
  A145–A150 259 + A151 32 + A152 55 + A153 48 + A154 73 +
  A155 78 + A156 90 + A157 67 = 1,112 per OS / 2,224 total**.
  Also requires A154/A156/A157 writer/restore/IAM blocks, A152 E0–E5
  and the known 32 supplier evidence errors unchanged.
- **Counts are a target until independently checked Actions logs conclude.**

The A165 PR is Draft stacked on A164 Draft (#1453), which is stacked
on A163, A162, A161, etc. Nothing has been merged to `main`.
Production-quality UI Security/Quality CI success on A159 (#1448) is a
separate branch and must not be conflated with the P0 H0 acceptance.

**HARD NO-GO · ZERO_AUTO_RESEND · 0 OF 6 P0 · Worker OFF · NO MERGE/DEPLOY/SPEND.**
