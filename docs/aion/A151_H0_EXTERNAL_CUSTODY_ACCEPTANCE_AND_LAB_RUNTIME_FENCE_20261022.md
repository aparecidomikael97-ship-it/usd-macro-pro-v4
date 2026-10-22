# AION H0 / P0 — A151 external custody acceptance + LAB/runtime boundary

**22/10/2026 — DESIGN REVIEW + STATIC FAIL-CLOSED GATE ONLY**

> **HARD NO-GO; 0/6 P0 homologated; Worker OFF; ZERO_AUTO_RESEND.**
> This document is NOT approval to open an account, incur expenses, enroll
> real keys, merge a Draft PR, deploy, enable Cloudflare Workers, run the AION
> Global Worker, restore production state or perform a real external effect.

## Why A151 is different from A145–A150

A145–A150 now have **259 counted LAB tests per OS** in
[PR #1434](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/pull/1434).
They test synthetically signed checkpoints, a high-water CAS, crash
windows, subprocess separation, pinned Ed25519 publication, one-time
challenges, lease expiry and LOCAL operator policy. Their **negative**
tests explicitly establish that operator-controlled snapshots, mutable
publisher policy and local timestamps can still forge apparent currency.

These tests cannot be translated into an independent H0 witness simply
because the CI is green. The actual runtime integration is NOT complete.

A151 therefore adds:
1. A **static import boundary gate** preventing direct/literal dynamic
   imports of A145–A150 test models into non-test Python runtime modules
   without triggering a CI failure.
2. An **external custody acceptance contract**, cross-linked to the
   existing Cloudflare/DynamoDB/S3 and provider-gate research, stating
   what must be demonstrated using genuinely independent authority.
3. A frozen distinction between **LAB proof**, **documentary feasibility**
   and **live independently attested evidence**.

### A151 static gate: narrow guarantee, not a security certificate

- \`tools/aion_p0_a151_lab_runtime_import_sentinel.py\` scans Python
  source files, excluding explicit A145–A150 root LAB modules and tests.
- Direct \`import\`, \`from ... import\`, literal \`__import__(name)\`
  and literal \`importlib.import_module(name)\` are rejected for A145–A150.
- Unparseable or unreadable non-test Python source fails closed.
- \`tests/test_aion_p0_a151_lab_runtime_import_sentinel.py\` has **16**
  adversarial mutations; \`tests/run_aion_a151_no_go_gate.py\` requires
  exact count and a repo-wide source scan.
- The status returned after a clean scan is STILL
  \`HARD_NO_GO_EXTERNAL_WITNESS_UNPROVEN\`.
- **Known limits:** static syntax inspection cannot prove all
  reachability, executable control-flow, obfuscated computed imports,
  compiled packages, native code or external plugins. The H0 runtime
  and Worker need independent dynamic security tests. This static gate
  **does not make the LAB modules safe for production use**.

## Actual external witness topology required

\`\`\`text
  D0: AION executor host / local SQLite
       |
       |  authenticated intention / nonce / scope / immutable request ID
       V
  D1: transaction custodian under distinct administrative + recovery domain
       |   conditional CAS, signed high-water, nonce consumed, audit/readback
       |
       |  version digest / predecessor / object version / signed anchor receipt
       V
  D2: independently administered append-only / WORM anchor
           verifies history continuity, retention, forks and D1 PITR
       |
       | authenticated *current* head evidence (not a stale saved version)
       V
  RESTART/H0 READONLY VERIFIER
       |
       +--> NO-GO unless D1 + D2 + enrollment + revocation + freshness
       |
       +--> provider effect verification must come from the PROVIDER,
            NEVER inferred from D1/D2 signing or list/404/timeout
\`\`\`

**Important:** Three storage directories, two subprocesses, two GitHub
branches, a second keyfile, or even an account with the same full
backup/admin recovery authority do NOT establish this separation.
D1 may be conditionally consistent and still admit PITR. D2 may retain
immutable versions but still permit new versions/delete markers and
does not by itself prove the currently highest sequence. The design
must prohibit or detect coordinated restore, administrative compromise
and stale-but-valid readbacks.

### Candidate services — feasibility ONLY; not selected

- **Cloudflare Durable Objects SQLite**: potential D1 conditional
  serializer, subject to PITR/admin rollback, authentication,
  Cloudflare account/admin separation and quotas. A DO alone is
  **insufficient for H0 anti-rollback**.
- **AWS DynamoDB**: potential D1 conditional update + consistent read,
  subject to IAM, restore/copy/write rights, durable nonce registry,
  billing and separate account custody. Not self-proving independence.
- **AWS S3 Object Lock COMPLIANCE**: possible D2 retained-version
  anchor. Must verify distinct account/admin, real retention policy,
  exact VersionId, chain continuity, forks, current-head discovery,
  delete markers, lifecycle, retention policy tampering, signed receipt
  and independently verified issuer. NOT an automatic monotonic counter.

Other providers may qualify if they can demonstrate the same guarantees;
the implementation must not hard-code vendor as evidence of trust.

### Acceptance evidence before deploying even a pilot

| Gate | Independent evidence required | Current status |
|---|---|---|
| E0 — finance | verified current spend, provider plans/quotas, 31-day stressed simulation, hard limits and owner-approved delta | **UNVERIFIED** |
| E1 — identity/IAM | accounts, MFA, owner/reviewer, admin separation, proven denials for executor backup/delete/restore/rotate and key replacement | **UNVERIFIED** |
| E2 — durable independent anchor | append-version receipt, retention, exact version/readback, chained signed head, delete marker/fork/PITR and rollback exercise with independent reviewer | **UNVERIFIED** |
| E3 — monotonic custodian | publisher enrollment through an independent channel, versioned key pin, challenge/nonce/epoch, remote one-winner CAS, strongly consistent latest readback with independent freshness | **UNVERIFIED** |
| E4 — interruption/recovery | physically restart host, D1 and D2 separately; fail at every commit/ack boundary, asymmetric + simultaneous snapshot restoration, network partition; never blind resend | **UNVERIFIED** |
| E5 — full H0 sign-off | real HUMAN_OWNER approval and scope, genuine producer effect/no-effect evidence, H0/Outbox/Worker bypass tests, canonical Security+Quality resolved, independent approval of 6 P0s | **UNVERIFIED** |

**No gate may be marked verified from screenshots of a test result,
local JSON flags, test harness keys, vendor promotional text or
self-asserted "independent=true".** Evidence must state issuer, reviewer,
enrollment, request/intent IDs, nonce, scope, version, controlled account,
signed receipt/readback and failure experiment provenance. A support
reply is only a claim until independently evaluated.

## Read-only acquisition map: reuse existing artifacts

The repo already contains the following **unmerged and documentary**
work; do not send new requests or create services merely to obtain a
larger test count:

- Custodian options and isolation model:
  \`docs/aion/AION_P0_H0_INDEPENDENT_HIGHWATER_CUSTODIAN_OPTIONS_NO_GO_20261019.md\`.
- Cloudflare DO SQLite and PITR risk:
  \`docs/aion/AION_P0_H0_CLOUDFLARE_DO_CUSTODY_GATE_PROPOSAL_20261019.md\`.
- Third-anchor and coordinated-restore negative:
  \`docs/aion/AION_P0_H0_THREE_DOMAIN_ROLLBACK_ADVERSARIAL_REVIEW_20261020.md\`.
- IAM/FinOps E0–E5 and previously proposed Cloudflare + S3:
  \`docs/aion/AION_P0_H0_IAM_FINOPS_EVIDENCE_MATRIX_NO_GO_20261019.md\`.
- Provider/custodian documentary two-role candidate review:
  \`tools/aion_p0_h0_vendor_custodian_documentary_gate.py\`.
- **Already drafted but unsent** vendor questions (34) and read-only
  reply tracking: \`docs/aion/p0-h0-unsent-onesignal-cloudflare-aws-technical-rfi-20261021.md\`,
  \`tools/aion_p0_h0_vendor_rfi_readonly_intake_gate.py\`.
- Historical 32 outbox/saga producer proof failures that cannot be
  replaced by local synthetic receipts:
  \`docs/aion/p0-h0-current-32-provider-proof-gaps-and-acceptance-20261021.md\`.
- Structural-only evidence admission, which is explicitly always
  BLOCKED: \`atlasquant_aion_p0_external_evidence_admission_lab.py\`.
- A150 latest experimental outcomes and residual threats:
  \`docs/aion/A150_PINNED_POLICY_LEASE_LAB_AUDIT.md\`.

**Do not treat the existing 85 Quality failures/errors as resolved by
the 259 passing A145–A150 tests.** Passing isolated suites are not
equivalent to canonical Quality/Security passing.

## The next *real* decision and its guardrails

The owner may later approve a limited **read-only documentary feasibility
study** for (i) distinct D1 and D2 administrative custody and (ii) total
cost/infrastructure burden, without connecting live credentials or
creating immutable retention. No actual service provision has been
approved by this Draft.

Before any external test, require a separate explicit decision on:
1. **Custodians / accounts:** choose D1 and D2 with non-overlapping
   recovery/control authority; define key admin and emergency procedure.
2. **FinOps:** total AtlasQuant/AION recurring spending ceiling is
   **R$200/month**, NOT a new allotment of R$200 for witnesses. A
   temporary R$250 exception requires separate explicit justification/
   approval. No payment provider/cloud account setup in LAB.
3. **Data minimization:** only opaque IDs and digests; no PII, SMS,
   contracts, phone numbers, customer content or user credentials
   in audit/logs; LGPD retention policy required.
4. **No real-effect authorization:** independent witness enrollment
   alone can at most support pre-effect fencing; provider receipts
   must independently prove \`COMMITTED_EFFECT\` or a terminal,
   enforceable \`NO_EFFECT_FENCED\` guarantee. Missing receipts mean
   UNKNOWN/BLOCKED/ZERO_AUTO_RESEND.

### Homologation is NOT granted by this package

**0/6 P0 homologated. HARD NO-GO, Worker OFF, no merge/deploy,
account provisioning, API keys, transactions, purchases, production
restore or automatic retries.**
