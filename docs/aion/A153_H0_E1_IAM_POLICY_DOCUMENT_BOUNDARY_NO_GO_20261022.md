# AION A153 — IAM Policy Proposal Adversarial Boundary (LAB ONLY)

**22 October 2026 — HARD NO-GO; 0/6 P0 homologated.** No merge, deploy, real AWS/Cloudflare account provisioning, new expenses, Global Worker activation, provider effect or automatic resend.

## Why this block exists

The previous A152 gate verified a documentary allowlist of allowed AWS S3 actions. However, a complete IAM policy document can introduce authority through NotAction, NotResource, Principal, unexpected Conditions, wildcard Action or Resource, or other roles. A153 checks a deliberately *very narrow* static proposed S3 writer/reader policy shape and rejects changes, including changes that could permit deleting retained versions, policy changes, assuming roles, or unversioned object reads.

**This is NOT a general evaluator of AWS IAM semantics.** A syntactically matched policy is merely an untrusted document and cannot establish true effective permissions, authentic account identities, Object Lock, immutable retention, current-head freshness, or separate administrative custody.

## Artifacts

- tools/aion_p0_a153_iam_document_boundary_lab.py — offline syntax/type/action/resource restriction and ambiguous JSON rejection.
- docs/aion/evidence/aion_p0_a153_synthetic_iam_scope_candidate_no_go.json — illustrative accounts and S3 names only, no real credentials or pricing.
- tests/test_aion_p0_a153_iam_document_boundary_lab.py — 48 attack and boundary tests.
- tests/run_aion_a153_counted_lab.py — exactly 48 with no skipped tests.
- .github/workflows/aion-p0-a153-iam-proposal-boundary-lab.yml — Windows and Ubuntu target: earlier A145-A150 259 cases, A151 16, A152 55 and A153 48 = **378 per OS**, plus document/crosswalk command gates. Verify final CI before declaring success.

## Candidate permissions, not deployed

The modeled D2 writer has only S3 PutObject for a fixed synthetic prefix. The modeled D2 reader has version listing, Object Lock configuration reading, object retention reading and version-pinned GetObjectVersion. Executor D0 and synthetic D1 Cloudflare runtime have empty AWS policy statements in the fixture.

Denied document mutations include:
- Wildcard Action/Resource, s3:*, iam:PassRole and s3:DeleteObjectVersion.
- Unrestricted prefix, other buckets, NotAction, NotResource, Principal.
- Altered reader listing condition or unversioned GetObject.
- Nonstandard Policy Version, unexpected JSON fields and duplicate JSON keys.
- Same account identifiers, overlapping admin labels and fabricated approval/spending fields.

The fixture has deliberately artificial account numbers and administrator labels. **Even distinct-looking account numbers and names prove nothing about real independent account administration**. The auditor never signs in to AWS or checks resource policies, actual attached role permissions, bucket policy, KMS, SCP, permission boundaries, cross-account STS, CloudTrail or Cloudflare.

A passing output MUST include all no-authority flags false, 0 homologated P0, zero authorized spend, and HARD_NO_GO_E1_AWS_IAM_UNENROLLED. A successful CLI exit code means only the static proposal matches the narrow template, not that IAM is safe or effective.

## E1 proof required in a real future environment

1. Inventory D0 executor, D1 custodian, D2 anchor, root/SSO/recovery identities and all IAM/KMS/bucket/retention recovery powers under independently validated account ownership.
2. Evaluate EFFECTIVE permissions with provider-native tools and independent human reviewer; prove executor cannot mutate witness or anchor and cannot bypass via CI, backups, restore, rotation, assumed roles, policy updates or key/retention administration.
3. Use genuine separately enrolled witness signing keys, current-head remote readback and rollback/restore/fork adversarial evidence; static JSON cannot attest any of these.
4. Independently verify supplier effect and terminal no-effect fencing for first uncertain operation, without automatic resend.
5. Quote global AtlasQuant monthly spending (R$200 current ceiling, optional R$250 only with explicit separate approval), and obtain consent before any account/retention provisioning.

## Historical blockers remain open

A152 still records the historical 6,895-test Quality baseline (51 FAIL and 34 ERROR) and 32 external-producer-proof errors (23 enrollment, 8 committed-effect receipts, 1 terminal no-effect fence). Static proposal tests never waive these requirements.

**HARD NO-GO; ZERO_AUTO_RESEND; 0/6 P0; Worker OFF; NO NEW COST.**
