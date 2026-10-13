# AION V16-A.35 — external producer and independent witness feasibility

**Review date:** 2026-10-13 (official public documentation only).  
**Status:** NO-GO, research/architecture comparison, no enrollment, no provider chosen.  
**Exact parent:** V16-A.34 [Draft #1247](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/pull/1247), HEAD `0f3afbc082302cdff1dee954286df799748efc63`.  
**Related:** #1190 Checkpoint Mestre, #1178 source/antirollback, #1117 owner-first-install.

## Definitions: evidence levels must not be conflated

1. **Request deduplication** means a provider recognizes retries under a key within its documented scope and retention. It does NOT prove a terminal fence of every asynchronous job.
2. **Resource status** means the provider describes a payment/message object. A status such as queued/accepted/sent is NOT proof that a recipient or financial settlement achieved the exact action required.
3. **Authenticated webhook** means the incoming callback passed the provider's cryptographic request authentication; it is not an AION-bound, independent, current-head attestation of the producer's commit.
4. **WORM history** preserves past object versions; it does NOT ensure the latest head cannot be hidden by a controlled source or that the custodian is independent.
5. **Current-head CAS/strong reads** can track monotonic sequence if scoped and configured correctly; they are NOT sufficient if the same actor can replace the root, change the authorization registry, or restore every trusted reference.
6. **Producer terminal NO_EFFECT_FENCED** requires that the effect-producing service durably commits *no effect and no future effect from any old queued, parallel, delayed or replayed attempt*, using the same scoped account, intent digest, idempotency key and epoch. A signed statement from an uninvolved cache or a 404 is insufficient.

## A. Providers for outbound effects — findings verified in official docs

| Candidate and use | Officially documented evidence | Material missing/undemonstrated for AION's strong P0 | Outcome |
|---|---|---|---|
| Stripe REST (financial) | Idempotency-Key returns previously recorded status/body; saves even first 500; keys can be pruned after >=24h, then a reused key may start a new request; comparing parameters blocks accidental mismatch. | Endpoint/operation-specific effect commit and authenticated exact causal receipt, independent issuer/current head, replay safety beyond pruning window; durable producer-enforced terminal NO_EFFECT_FENCED for all old attempts **not established by reviewed source**. | **NO-GO for automatic re-send of ambiguous protected payment**; targeted vendor RFI needed. |
| PayPal REST (financial) | PayPal-Request-Id idempotency while server retains identifier; generic guide says *up to 45 days*; advanced checkout Orders API says 6h default and 72h by account manager for its operation. Duration and endpoint must be negotiated/confirmed, not assumed universal. | Lifetime and scope across all flows, causal producer commit and late-effect terminal fencing; no evidence here of receipt satisfying independent AION P0 contract. | **NO-GO for ambiguous automatic financial retry**; endpoint-by-endpoint RFI. |
| Twilio Programmable Messaging (SMS/WhatsApp through Twilio) | POST Message resource creates an outbound object; Message SID and statuses queued/accepted/sending/sent/delivered/undelivered/read; signed status callbacks via X-Twilio-Signature with account AuthToken. Callback for initial Message status is not sent. | No provider-side application-scoped idempotent CREATE-and-terminal-fence contract located in reviewed official pages; signed webhook authentication does not itself prove AION's exact payload intent, or prohibit a delayed queued delivery after an ambiguous create/ACK loss. | **NO-GO for automated ambiguous re-send**; candidate for authenticated observation and manually supervised workflow only after distinct authorization. |
| Meta WhatsApp Cloud API direct | Official normative primary-source text for the exact commit/idempotency/fence guarantee was **not established in this research round**; Twilio WhatsApp support is not evidence for direct Meta API. | All producer-commit, callback, idempotency and terminal no-effect guarantees need direct documentation and/or contractual tests. | **NOT VERIFIED / NO-GO**; do not infer support. |

**Official producer sources (read without creating accounts or sending traffic):**

- Stripe: https://docs.stripe.com/api/idempotent_requests
- PayPal generic request header: https://developer.paypal.com/api/rest/requests/
- PayPal newer guide: https://developer.paypal.com/api/make-api-requests
- PayPal Orders-specific duration: https://developer.paypal.com/api/rest/integration/orders-api/api-use-cases/advanced/
- Twilio Message resource: https://www.twilio.com/docs/messaging/api/message-resource
- Twilio lifecycle: https://www.twilio.com/docs/messaging/guides/outbound-message-status-in-status-callbacks
- Twilio cryptographic callback validation: https://www.twilio.com/docs/usage/security

**Interpretation:** “not established in reviewed public docs” does **not** mean that a vendor categorically lacks the feature under every product/contract; it means AION does not have proof to authorize the protected action. Any first positive enrollment would require separately checked real provider terms and adverse tests, not a synthetic flag.

## B. Independent witness current head / WORM candidates

| Option | Officially documented building block | Failure domain, head or custody gap | Disposition |
|---|---|---|---|
| AWS S3 Object Lock **Compliance** | Protected object versions cannot be overwritten/deleted by account root during retention; S3 WORM operates per version. | Another version or delete marker can be created; a WORM *old version* does not prove which version is the valid latest head. Custody, operator independence, lifecycle/retention, account loss and separate signed latest-head index must be proven. | **Research candidate for immutable history**, NOT current-head witness by itself. |
| Amazon DynamoDB conditional writes + strongly consistent reads | Conditional PUT/UPDATE can reject mismatches; `ConsistentRead=true` reads committed latest in table/local secondary index (not GSI/stream); controls for sequences are technically plausible. | Same AWS administrator/account can mutate/delete table and registry; replication consistency matters; no immutable WORM proof just from CAS. Need independent custodian, signed head and audit/retention chain. | **Research candidate for externally administered head CAS**, not independent by default. |
| Cloudflare R2 Bucket Locks | Retention rules can block deletion/overwrite of objects; platform exposes get/set/remove of bucket lock rules. | Configuration itself can be removed via authorized dashboard/API; same Cloudflare account/operator is not a distinct failure domain for the AION Worker. Cloudflare R2 S3 compatibility explicitly does not support S3 Object Lock request headers. | **Useful potential archive under separate governance**, not accepted as immutable external head/custody on present evidence. |
| Cloudflare Durable Objects / SQLite | Transactional, strongly consistent state for an object, with point-in-time recovery; useful for app coordination. | Same developer/cloud account may operate both Worker and DO; a PITR operation can rewind database content, so external current-head protection needs independently managed root/head. | **Not a standalone antirollback witness**. |

**Official witness sources:**

- S3 Object Lock compliance and version caveat: https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lock.html
- DynamoDB conditional writes: https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Expressions.ConditionExpressions.html
- DynamoDB read consistency: https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/HowItWorks.ReadConsistency.html
- R2 Bucket Locks and removal: https://developers.cloudflare.com/r2/buckets/bucket-locks/
- R2 S3 API object-lock gaps: https://developers.cloudflare.com/r2/api/s3/api/
- Cloudflare Durable Objects with SQLite / PITR: https://developers.cloudflare.com/durable-objects/api/sqlite-storage-api/
- Cloudflare DO lifecycle / PITR: https://developers.cloudflare.com/durable-objects/reference/durable-objects-migrations/

**Potential architecture for future review only:** separately governed *strongly read* head + append-only protected version history, with attestations bound to owner/tenant/workspace/issuer, multi-party root administration, readback and explicit detection of divergence/fork/rollback. Two storage products under the **same fully controlling account** must never be labeled independently custodied. No specific AWS or Cloudflare account, feature, deployment or cost is authorized or claimed here.

## C. Qualification checklist — request real producer and witness evidence

Request from each prospective *effect producer*, including account/product/API version/region:

1. Is deduplication enforced atomically **at external effect commit**, including delayed workers, scheduled messages, queues, parallel/geo-replicated senders and cross-request retries?
2. Are account + tenant + resource + canonical exact payload digest + operation + idempotency key + attempt + epoch/fence generation part of the producer's immutable uniqueness?
3. What precise key lifetime, pruning/reuse and concurrent request behavior are guaranteed? What occurs after pruning or when producer rejects before initial processing?
4. Which response distinguishes **accepted/queued**, **committed effect**, **delivered/settled**, **failed with unknown effect**, and **terminal no effect**? Show authoritative API schema and controlled log lineage.
5. Can the provider issue an **authenticated producer-origin receipt for a committed effect**, with exact request/account/digest/epoch/nonce/current-head bindings and independent readback?
6. Can it issue a **terminal NO_EFFECT_FENCED** receipt that atomically prevents all old attempts and delayed work from causing effects? Where is that fence checked by the actual effect executor?
7. After unknown ACK/timeout/500, can the client safely read by original key **without creating or mutating an effect**? How does it detect 'no record yet' vs 'terminal never will occur'?
8. Do webhook signatures and keys bind the precise event, account and initial idempotency request? Rotation/revocation, retries, out-of-order, replay and recovery?
9. Does the provider furnish independent audit logs/retained receipts across regional failure, queue replay, rollback, account closure and delayed delivery?
10. Provide endpoint-specific rate, unit pricing (BRL conversion basis), LGPD data region/subprocessors, cost ceilings, support/SLA and contractual commitments. **No sign-up, purchase or account changes until separate HUMAN_OWNER approval.**

Request from prospective *witness custodian*:

1. How does AION pin the registry/root and latest sequence/head **out of band**? Who can rotate, erase, rebind or revoke it?
2. Can a party with complete access to AION host, GitHub, Worker, cloud deployment account and local backups roll witness state backward? How would verification detect joint restore?
3. Can a strongly consistent current read be authenticated from a separated operator/failure domain? What happens if an operator serves a signed old head?
4. Does the durable append-only history forbid overwrite/deletion *and* prevent switching the selected latest head? Is there cross-domain signed anchoring?
5. What is the policy on custodian outage, lost keys, incident response, irrevocable revoke, break-glass and backup? None may auto-enable protected AION operations.
6. Real measured availability, retention minimum, operator independence, location/LGPD and all recurring costs must be documented before selection.

## D. Decision gates

**Decision as of 2026-10-13:** no provider meets the **fully evidenced** pre-send + authenticated COMMITTED_EFFECT + terminal producer-enforced NO_EFFECT_FENCED + independent nonrollback current-head contract based on the public materials examined. This is an **evidence gap**, not a claim of categorical impossibility. Therefore ALL productive outbound effects and external reconcile callbacks remain blocked in the AION staging code; no automatic retries of unknown effects.

Safely preparable, without external action: formal receipt schemas, read-only design assessment, source-code review, local immutable test fixtures clearly labeled `SIMULATED_ONLY`, offline training/CRM drafts and owner approval ceremony specification. None is equal to first-install approval.

The 23 historical Outbox Quality errors remain recorded, 37+8 original A.12/A.16 cases remain absent/unexecuted; root/custody, HUMAN_OWNER and physical host are not verified. **0/6 P0 homologated. 20/20 FIRST INSTALL HARD NO-GO.**

No purchase, credentials, external API call to producer, messaging, payment, account creation, signing, Worker/Render, merge, deploy or AM12 changes performed.
