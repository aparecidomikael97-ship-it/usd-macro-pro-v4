# AION V2 — second independent security anchor, protocol reference V1

**Date:** 2026-10-09. **Base Draft:** #1129 (all Draft stack). **NO-GO for live execution or payment.** This file is a design record, NOT a deployment runbook.

## Decision: two failure domains, not two files

Primary candidate: Cloudflare SQLite-backed Durable Object for the V2 witnessed nonce/cost head (still needs real enrolled signer, privileged operator threat review and authenticated READ/CAS).

Secondary candidate for independently owned high-watermark: AWS DynamoDB conditional-writing item in a *separate vendor, account and IAM administration trust domain* controlled by independently enrolled anchor credentials, distinct from primary/owner/collector keys. Use DynamoDB `GetItem(ConsistentRead=True)` on a base table (not default eventually consistent read, not GSI), `UpdateItem` with condition on **exact previous epoch+sequence+receipt/snapshot digest**, ideally `TransactWriteItems` only for items in SAME account/region. Confirmed by AWS docs below. These are **technical candidates**, no AWS/Cloudflare provisioning, secrets, funding or code clients in this Draft.

Official public evidence rechecked 09/10/2026:
- Cloudflare [SQLite Durable Objects Storage API](https://developers.cloudflare.com/durable-objects/api/sqlite-storage-api/): transactional strongly-consistent object storage **and** Point-in-Time Recovery (PITR) to an earlier database state (up to 30 days). It cannot alone prove irreversible historical monotonicity against privileged administrative restore.
- Cloudflare [Durable Objects pricing](https://developers.cloudflare.com/durable-objects/platform/pricing/): Workers Free offers SQLite-backed DO subject to free quotas and fail-on-limit; Paid has a minimum Workers subscription and metered overages.
- AWS [DynamoDB read consistency](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/HowItWorks.ReadConsistency.html): strongly consistent table/LSI reads with `ConsistentRead`, NOT automatically via a GSI.
- AWS [conditional update expressions](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Expressions.ConditionExpressions.html): single-item conditional update/compare-and-swap capability.
- AWS [transactional writes](https://docs.aws.amazon.com/amazondynamodb/latest/APIReference/API_TransactWriteItems.html): atomic only inside an account/region, **never across Cloudflare/AWS**. `ClientRequestToken` idempotency window is limited; cannot replace a permanent per-turn nonce and unknown-outcome journal.
- AWS [pricing](https://aws.amazon.com/dynamodb/pricing/): on-demand billed by request; AWS free-tier quotas reference **provisioned capacity**, do not assume on-demand queries are included at zero cost. Taxes, AWS region, transfer, logs, IAM/CloudWatch and USD/BRL exposure need separate quotation.

**Budget posture:** current action costs **R$0 new services**; user budget remains R$200/month for ALL infrastructure, not R$200 extra for the anchor. No exact BRL monthly amount can be responsibly certified before real expected request rates, model operation count, regional unit quotes, exchange rate, fees/taxes, alert thresholds and existing monthly spend are measured. Neither signup nor payment is authorized.

## New reference contract (mathematics only)

`atlasquant_aion_v2_secondary_anchor_reference.py` strictly compares two *independently signed* challenge-bound READs:

- Witness signer = `INDEPENDENT_WITNESS_ED25519` (from #1128).
- Second-anchor signer = `SECOND_DOMAIN_ANCHOR_ED25519` with **distinct schema/purpose/domain**, signed anchor service ID, scope, witness pin SHA-256, owner pin digest, policy period/generation, challenge, minimum epoch, and COMPLETE latest head (epoch, sequence, signed receipt SHA-256, local ledger snapshot digest, hold count/amount and budget cap).
- A matching pair of signed heads is **`TWO_SIGNED_HEADS_EQUAL_MATH_ONLY_UNTRUSTED`**, NEVER independent enrollment, real freshness or provider authority.
- Primary head behind secondary -> **BLOCKED_ROLLBACK**; ahead -> **BLOCKED_UNANCHORED** (crash after primary CAS, before secondary write); same sequence with different hash/counters -> **BLOCKED_FORK**; signer/nonce/scope/epoch mismatch -> BLOCKED.
- Secondary CAS precheck accepts ONLY a strictly one-step primary advance, same epoch/scope/pin/policy/month, exact previous secondary state, +1 hold, increased held signed-cost and unchanged cap. Produces uncommitted proposal only; no remote CAS or I/O. Real AWS service must read/check/advance **inside DynamoDB conditional write**. Clients must never supply `current_anchor_head_for_fixture` as authority.

## Failure cases and explicit negative controls

1. Save complete old Cloudflare witness state, advance witness+second anchor, restore old witness: a NEW authentic secondary read should detect the witness is **behind**.
2. Crash after primary witness CAS, before secondary publish: primary is **ahead** and paid dispatch MUST STOP. Do not silently move the anchor to local state or assume the primary was never billed.
3. Same primary sequence, forked receipt/snapshot/cost -> BLOCK; race to update single anchor -> only one conditional update succeeds when performed by service.
4. Restore **both** security domains or substitute **both** enrolled trust pins: mathematical comparison can pass. Therefore independent administrative custody, immutable audit logging, cross-domain permission split, signing key proof-of-possession, emergency revocation and independently verified hardware/offline recovery are still prerequisites. Two cloud accounts controlled by one admin credential are **not** independent.
5. Lose second anchor / GSI only eventual read / network outage / witness PITR or lost CAS response: FAIL CLOSED. Fresh signed READ from each authenticated domain and pending operation journal are required; never authorize a second paid provider call based solely on equality.
6. No two-phase commit or cross-vendor atomicity exists here. Production needs durable `PREPARED → WITNESS_COMMITTED → ANCHOR_COMMITTED → DISPATCH_CLAIMED → UNKNOWN|CONFIRMED` state model, explicit resumption/reconciliation and one-shot dispatch lease. Any transition absent verified evidence must stay BLOCKED.

## Gates needed before production

Independent AWS IAM role/control separate from Cloudflare admin and PC; server-side signature verification, pinned service identity, sensitive scopes, enrollment and rotation of HUMAN_OWNER, collector, witness and second anchor; trust key fingerprints out of restorable storage; external monotonic anchor protected from admin restore and deletion; cost alerts and quotas; resilience, crash/race/PITR/fork tests, LGPD logs; host-bound installation tests only with explicit owner presence. Treat an AWS-admin deletion/restore as incident requiring owner re-enrollment and manual chain recovery.

**No live tokens, keys, Cloudflare/AWS resources, spend, installs, merges, deploys, provider calls or production data. All authority flags remain FALSE.**
