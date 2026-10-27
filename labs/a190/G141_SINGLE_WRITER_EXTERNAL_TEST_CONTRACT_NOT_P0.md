# A190 G141 — Single-writer custodian review and future external tests T9–T13 (LAB)

**27/10/2026. Draft LAB only. 0/6 P0 homologated; HARD NO-GO; UNCERTAIN / ZERO_AUTO_RESEND.** Parent G140 #1632 at SHA e01331193e73db16fdf83325c83b1031a71caf3c. Issues #1486 and #1477. This adds no external provider, production code, Worker or SEND.

## What this genuinely checks

G127 specifies independent authority requirements; G140 rejects self-attested dossiers. This **offline paper-design guard** catches new configuration mistakes. It cannot authenticate customer claims, a provider, cloud-account administrator, KMS key root or database native VFS. Even a document with all "safe" assertions returns DESIGN_REVIEW_ONLY_EXTERNAL_PROOF_MISSING_HARD_NO_GO. All operational flags stay false.

1. Pilot initially uses **one authoritative writer region**. If that region fails, suspend new first effects until an independently proven epoch/fence allows recovery. DynamoDB MREC global tables reconcile competing changes by last-writer-wins, not a global unique first reservation. MRSC is a separate future design needing qualification.
2. Canonical business event ID must come from independently verified original identity, not request ID. DynamoDB ClientRequestToken idempotency expires after **ten minutes**; no reliance on it alone.
3. Never perform actual effect/SEND inside Firestore transaction callback, which may rerun on contention.
4. S3 Object Lock COMPLIANCE protects object versions; a new PUT can create a new version. The authoritative immutable version must be independently pinned; delete markers/current-key lookup are not provenance.
5. Missing ACK, host restore, offline authority, self-repinned root and region failover without authenticated fence all mean **UNCERTAIN / NO_FIRST_SEND / ZERO_AUTO_RESEND**.

## Five precise future REAL acceptance scenarios

These names are pinned in the LAB module as REQUIRED_REAL_TESTS but are NOT executed against any genuine service yet. The green G141 unit suite does not satisfy any of them.

| ID | Real hostile scenario | Minimum actual proof |
| --- | --- | --- |
| T9_MULTI_REGION_SAME_ECONOMIC_EVENT | Two competing writer regions, different request IDs, identical original economic effect | Globally only one authenticated original reservation; if unprovable, block multiwriter |
| T10_TRANSACTION_CALLBACK_REEXECUTION_NO_EFFECT | Transaction handler reruns two or more times under real contention | No effect in callback; one separately authorized causal provider admission after commit |
| T11_WORM_VERSION_AND_DELETE_MARKER_PROVENANCE | Same-key new version and delete marker while protected original remains retained | Trusted head/version/history cannot be replaced by current-key illusion |
| T12_SHORT_TOKEN_EXPIRED_WITH_HOST_ROLLBACK | Token's documented dedupe expires; restore host; new request for same original | Independent service refuses new reservation and no automatic resend after lost ACK |
| T13_REGION_OUTAGE_FAIL_CLOSED_NO_AUTO_RESEND | Primary region unavailable, stale or inconsistent replica available | No first effect until independent epoch/fence; diagnostics may remain read-only |

## Actual executable LAB boundary

The review_custodian_proposal_lab function takes a STRICTLY TYPED **untrusted declaration**, rejects multiwriter, unfenced failover, client-renamed business key, non-atomic reservation, finite token only, effect in transaction callbacks, unpinned WORM version, ACK retry, offline first-effect or caller-controlled root. An apparently safe candidate remains **REVIEW_ONLY/HARD_NO_GO**.

Exactly 19 design-level tests run with:
python -B -m unittest -v labs.a190.test_g141_custodian_proposal_guard_lab

All outcomes have externally_verified=False, p0_homologated=0, allows_worker=False, allows_provider_send=False, allows_retry=False, safe_to_install=False. No production path imports the LAB helper.

Original G122 five actual external/native acceptance tests and G125 canonical suite remain untouched. Until an independently administered custodian, authentic HUMAN_OWNER enrollment, provider causal receipt/fence, restored native SQLite VFS and budget approval exist, G122 remains RED and AION remains HARD NO-GO.

## Primary provider documentation reviewed 27/10/2026

- AWS short client request token: https://docs.aws.amazon.com/amazondynamodb/latest/APIReference/API_TransactWriteItems.html
- AWS regional transaction constraints: https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/globaltables-CoreConcepts.html
- AWS last-writer-wins risk: https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/BestPractices_ImplementingVersionControl.html
- Google Firestore callback re-execution: https://docs.cloud.google.com/firestore/native/docs/manage-data/transactions
- AWS S3 Object Lock version semantics: https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lock.html

Budget history: R$200 initial operating target; R$250 current ceiling with specific HUMAN_OWNER approval for any additional spend. No region, vendor, cloud account, KMS, retention lock, provider, deployment or cost has been selected or activated.

**Draft-only. Never merge/deploy or operate SEND, Worker, funds, customer data, external keys, accounts or devices without separately authorized real evidence.**
