# AION P0 / H0 — A167: vendor capability falsification before custodian selection

**22 October 2026. Draft stacked on A166 (#1455).**
**Read-only / documentary / offline tests. HARD NO-GO, ZERO_AUTO_RESEND, 0/6 P0.**

## Why this block exists

A166 defined sixteen required items (eight each for two custodian roles).
The next risk is wrongly accepting marketed terms such as "durable",
"consistent", "WORM" or "idempotent" as the exact H0 proof. The official
provider docs show these concepts are **not interchangeable**.

### Four provider capabilities, seven explicit counterexamples

| Counterexample | What current official docs establish | Why this cannot unlock H0 |
|---|---|---|
| S3 protected object version | Compliance mode protects a retained object version, including against AWS root deletion during its retention window | Existence and retention of a version alone do not prove that its digest is the latest authorized external highwater |
| S3 delete-marker GET | An unversioned/current GET can return HTTP 404 when a delete marker hides a still-protected older version | HTTP 404 or empty response is **not proof of no prior record**; read version ID, list versions and verify an independently anchored head |
| Cloudflare DO PITR | SQLite-backed Durable Objects support restoration to an earlier bookmark within the documented recovery window | Strongly consistent *current* reads of a restored state cannot independently prove that later history never existed |
| Cloudflare DO deleteAll | The storage API offers content deletion | "Durable" does not mean admin-resistant immutable/WORM custody |
| DynamoDB PITR | Restoring a historical point creates a **new table**; a strongly consistent read still reads the selected table | A consistent old snapshot does not establish the authentic monotonic head from an independent domain |
| OneSignal same key inside window | Notifications-create idempotency suppresses duplicate creation using the same key during the retention window | Create dedupe does not provide signed causal downstream SMS effect, cancellation, or terminal no-effect fence |
| OneSignal same key after window | The key is retained 30 days; afterward it may be deleted and the same key may create a new message | A lost first result cannot be automatically retried after this window |

Primary vendor sources reviewed on 2026-10-22:

- [AWS S3 Object Lock and Compliance-mode protected versions](https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lock.html)
- [AWS S3 Object Lock delete-marker behavior](https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lock-managing.html)
- [Cloudflare Durable Objects SQLite storage: PITR and deleteAll](https://developers.cloudflare.com/durable-objects/api/sqlite-storage-api/)
- [AWS DynamoDB point-in-time restore](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/pointintimerecovery_restores.html)
- [OneSignal idempotent notification requests and 30-day expiration](https://documentation.onesignal.com/reference/idempotent-notification-requests)

Source links are public documentation, **not** vendor commitments to our
specific account, real external receipts, or owner-approved procurement.
Provider terms and quotas must be rechecked immediately before any real
engagement. No price or production capability is inferred.

## Acceptance consequences for A166

1. **A166/WORM_READBACK** must identify an exact protected `versionId`,
   independently verify its immutable retention settings and version-specific
   bytes, and must not infer any absence from the current/latest object GET.
2. **A166/ROLLBACK_RESTORE** needs an external monotonic head whose read
   path is unaffected by Cloudflare DO PITR, DynamoDB backup restore, local
   snapshot restoration or shared administrators. If the external highwater
   is unavailable, always block.
3. **A166/ADMIN_CONTROL and ACCOUNT_SEGREGATION** require independent
   authenticated control-plane evidence, not different API tokens in one
   master account. S3 Object Lock does not prove administrative independence.
4. **A166/REVOCATION_PROPAGATION and NONCE_TIME** require fresh externally
   retained challenges and independent readbacks after a real adversarial
   key revocation, under outage and rollback.
5. **Producer-effect proof is a separate P0.** OneSignal create idempotency
   is bounded and cannot replace causal `COMMITTED_EFFECT` or terminal
   `NO_EFFECT_FENCED` from the true provider. All 32 historical producer
   proof obligations remain open.
6. **Never promote documentation into external evidence.** The A167 JSON
   is an exact list of documented counterexamples, not a provider endorsement,
   not a signed observation, and not a release or purchasing decision.

## Tests and guardrails

`tests/aion_p0_a167_provider_semantics_lab.py` is in the test-only tree.
Seven synthetic documented scenarios and seventeen denial/mutation checks
confirm that HTTP 404, a retained S3 version, a PITR-recovered table, an
older DO bookmark, a provider-dedupe key or a claimed receipt cannot create
a GO state. The gate has no API client, network, secrets, credentials, vendor
account, storage allocation or production imports.

Run **24 tests** plus A166 and inherited LAB regressions. Expected target:
**1,176 counted tests per OS / 2,352 executions across Windows and Ubuntu**,
subject to actual GitHub Actions completion. A151 runtime-import fence,
A152 documentary E0-E5, A154/A156/A157 deny audits and 32-provider
crosswalk remain required.

**No purchase, sign-up, HSM, provider integration, Worker, merge, deploy,
external receipt or HUMAN_OWNER approval was performed.**
