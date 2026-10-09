# AION V2 — persistent reference CAS + independent witness infrastructure decision (09 Oct 2026)

**Status:** Design + disposable SQLite protocol simulation only; NO-GO for real paid model, rollout or owner key enrollment. Parent Draft #1128; isolated new Draft stacked on top.

## Architecture decision for later authorization (NO ACTIVATION)

**Recommended research candidate:** Cloudflare **SQLite-backed Durable Objects** dedicated to a separate witness control boundary, with a short-lived signed challenge-READ, transactionally committed append/monotonic CAS, authenticated tenant/owner scope, public pin registry, and independent second-origin high-watermark checkpoint. It is NOT yet an approved, security-qualified or deployed provider.

First-party documentation verified 2026-10-09:
- [Durable Objects pricing](https://developers.cloudflare.com/durable-objects/platform/pricing/) (page Sep 30 2026): Workers Free supports SQLite-backed Durable Objects; free tiers 100,000 DO requests/day, 13,000 GB-s duration/day, 5 million SQL row reads/day, 100,000 row writes/day, 5 GB storage. Exceeding free-tier thresholds fails the operation rather than charging overage. Workers Paid includes a minimum $5/month, plus usage according to dimensions. Prices in USD. Worker-side requests/add-ons, taxes and actual FX must be included in a separate signed budget review.
- [SQLite DO Storage API](https://developers.cloudflare.com/durable-objects/api/sqlite-storage-api/): transactional/strongly consistent object-scoped storage, `ctx.storage.transactionSync` for multi-statement SQL. Use one object per owner/scope to serialize head and CAS within the object; avoid `await` between head verification and update.
- [DO storage access](https://developers.cloudflare.com/durable-objects/best-practices/access-durable-objects-storage/): SQLite-backed DO storage includes **Point In Time Recovery (PITR)**, meaning privileged restore of the witness object's own storage CAN also revert its head. Cloudflare persistence is NOT immutable antirollback against its administrative control plane. Add a **second trust domain** and separately controlled signed high-watermark checkpoint, e.g. owner-held hardware-backed or separate account/provider append-only controlled registry. This has not been selected or priced.
- Cloudflare account/app security posture still requires review: secret storage, service auth and public key enrollment, RBAC, compromise domain separation, data residency/LGPD, break-glass revocation, audit export, network outage and billing limits.

| Option (no commitment) | Strength | Main limitations | Cost assessment |
|---|---|---|---|
| Separate local SQLite file | simple transactional CAS and tests | restorable together with owner PC; no independent trust | zero new cloud spend; insufficient |
| Cloudflare Durable Object SQLite | transactional single-object state and persist between requests; Workers Free tier offered | provider-admin PITR/rollback possible; secrets, network, separate witness key enrollment and secondary high-watermark still required | Free tier possible for very low usage; Paid minimum US$5/month + usage, exact BRL to verify before activation |
| Other independent managed conditional-write DB + signed read | different operator/account potentially strong failure-domain split | requires vendor-specific CAS consistency, secure signing, uptime and quote | no quote verified; not approved |

**Current decision:** prototype only in existing GitHub CI (R$0 of new provisioned services); **not** create a Cloudflare namespace, service token, billing plan or signing key without separate owner approval. No claim that a single Durable Object suffices for tamper-proof independent witness against provider-admin restore.

## Delivered isolated protocol simulator (not Cloudflare code)

`atlasquant_aion_v2_isolated_sqlite_witness_cas_reference.py` implements a **reference-only** SQLite witness database in a separate disposable file with a pinned immutable synthetic config/genesis, `BEGIN IMMEDIATE` serialized CAS, WAL + `synchronous=FULL`, complete local append chain checking on open, unique operation ID and receipt hash, strict prior sequence/read signature via #1128, and durable idempotency readback across reopen. The module has no signing key, no HTTP client and no Cloudflare deployment code. The fixture signs outside the module with a throwaway ephemeral witness key.

**Distinct, verifiable limitations:**

1. Durable local file != independent witness. A sufficiently privileged attacker may restore BOTH the local hold and simulated witness DB. Even the SQLite witness itself, when fully restored, is internally coherent.
2. `compare_supplied_external_anchor` detects restore **only if** a genuinely independent protected newer head exists. The CI deliberately demonstrates that a stale supplied anchor passes mathematics. Do not represent this as independent production antirollback.
3. A local witness CAS may commit independently of local Chat/V2 hold and paid provider HTTP. Crash/lost response => one-way unknown outcome; do not retry paid call automatically, and do not infer real owner approval.
4. Reference idempotency counts local witness writes only and cannot prove no prior paid API dispatch. A genuine production witness must reserve/claim a globally unique dispatch intent and persist an explicit outcome/reconciliation protocol with protected monotonic epoch.
5. The witness public pin digest and scope config are caller-provided fixtures, **not** verified enrollment. Real owner, witness and collector signing ceremonies and independent root still missing.
6. The immutable local append checks cannot detect complete privileged history rewrite without external anchoring. Attackers capable of editing all DB rows can fabricate a consistent chain. Trust requires separately operated keys and a remote protected high-watermark.

## Admission gates before any production action

- Independent authentic source for witness service ID, public pin, current epoch, and challenge nonce. A second, separately owned/authenticated monotonic high-watermark to survive DO PITR/admin restore.
- Signed owner enrollment + collector/witness proof-of-possession, recovery/rotation/revocation with owner presence; role separation and scopes.
- Transactional witness CAS at remote trust boundary, no user-supplied head used as authoritative current state; race, outage, misrouting/fork and lost-response tests.
- Single use unknown HTTP outcome reservation+dispatch receipts, full-context prompt and model request digest, real billing/pricing/FX limits and physical policy review.
- Monthly maximum cost analysis within R$200 for ALL infrastructure together, not just the witness; no service activation or API payment until explicitly approved.
- Keep Core/`main` frozen; no merge/deploy or activation as part of this Draft.

**All real flags FALSE:** `independent_protected_witness_verified`, `owner_consent_verified`, `real_budget_reserved`, `provider_request_approved`, `model_invocation_authorized`, `provider_called`, `billing_authorized`, `installer_authorized`, `safe_to_resume`.
