# AION V2 — dispatch-journal dual signed high-watermark and fencing reference

**9 October 2026.** Draft stacked on #1133 → #1132 → #1131 → #1130 → #1129 and predecessors. **NO-GO for real paid provider calls, enrollment, merge or deployment.**

## Why #1133 alone cannot protect money

The local one-shot journal in #1133 prevents repeated `DISPATCH_CLAIMED` transactions only as long as its SQLite file is not rolled back. That PR deliberately proves a privileged actor restoring the old `PREPARED` snapshot can locally claim again. Even two signed witness heads will not help unless the dispatch journal's *own* sequence and full content hash are pinned to independent, fresh, enrolled remote monotonic trust anchors.

This reference defines precise **signed READ** requirements for that journal head and a **mathematical one-step claim fence**, without creating a cloud service or trusted signer.

## Reference code

`atlasquant_aion_v2_dispatch_journal_dual_witness_reference.py`:

- `local_journal_intent_commitment` reads the whole local SQLite journal and a scoped exact signed V2 intent in **one `BEGIN IMMEDIATE` transaction**; it recomputes the same canonical snapshot digest as #1133 and returns the journal sequence, SHA-256 digest, this intent's `PREPARED|DISPATCH_CLAIMED|UNKNOWN_OUTCOME|CANCELLED` status, claim sequence and full signed request digest. It performs zero network and zero writes.
- `unsigned_journal_head_candidate` constructs the closed, domain-separated signed HEAD payload for synthetic test keys. A production witness would need to sign freshly after server-side authenticated READ, not simply trust a caller-supplied value.
- `review_dual_witnessed_journal` mathematically checks two separate Ed25519 roles, `PRIMARY_WITNESS` and `SECONDARY_ANCHOR`, each bound to owner, tenant, workspace, policy generation, month, immutable key registry roster SHA-256, scoped nonce, distinct READ challenge, minimum witness epoch, journal sequence, journal snapshot hash, exact intent signed hash, full resolved request hash, status and claim sequence.
- The comparison blocks primary behind secondary, primary ahead, equal-sequence fork, local journal behind, local ahead, stale/malformed signed READ and any mismatch in scoped message/hash/status. A matching `PREPARED` or `CANCELLED` state still **blocks**, never authorizing execution. Matching `DISPATCH_CLAIMED` or `UNKNOWN_OUTCOME` yields the explicit **`DUAL_WITNESSED_DISPATCH_STATE_MATH_ONLY_UNTRUSTED`**, never permission to send, retry, refund or bill.
- `review_one_step_claim_fence_preflight` compares previously signed PREPARED heads against new *separately* signed DISPATCH_CLAIMED heads, requires exactly +1 journal sequence, new claim sequence equal to that new sequence, same epoch/scope/nonce/owner registry and provider request hash. Result is **`ONE_SHOT_FENCED_CLAIM_PRECHECK_MATH_ONLY_UNTRUSTED`**; **NO** real fencing-token allocation or remote compare-and-swap.

### Important hardening in #1133 inherited journal on this branch

Each opaque evidence digest append now also consumes a unique durable journal sequence, exactly like PREPARED, CLAIMED, UNKNOWN or CANCELLED transitions. SQLite integrity checks verify evidence event sequence, contiguous/gap-free local journal events, and the full snapshot digest. This avoids creating a new journal snapshot under the **same high-watermark sequence** whenever evidence is appended. Existing CI tests are rerun on Linux and Windows.

**This changes the local reference schema** for evidence rows: old #1133 fixture databases require explicit migration if ever adopted; none exist in production and this Draft does NOT silently migrate or import old DBs.

## Crash/recovery security truth table

| State / attack | Math-only result | Real authority |
|---|---|---|
| PREPARED with both matching signed heads | BLOCK; no claim witnessed | NO-GO |
| CLAIMED with both matching signed heads | Comparison candidate, never a dispatch ticket | NO-GO |
| Restart/lost provider HTTP reply after claim | Conservatively UNKNOWN; never auto-retry | NO-GO |
| Local journal restored to PREPARED, heads retained newer CLAIMED | **BLOCK** local rollback | NO-GO |
| Primary witness committed CLAIM but secondary still PREPARED | **BLOCK** ahead-of-anchor / reconciliation required | NO-GO |
| Same sequence, different signed digest / status | **BLOCK** fork | NO-GO |
| New evidence changes snapshot after claim, old heads unchanged | **BLOCK** unanchored new sequence | NO-GO |
| Both witness and anchor heads restored alongside journal | Attacker-supplied stale math may match again | NO-GO |
| Caller replaces key pin and matching signature | Math may pass; owner enrollment not proven | NO-GO |

## Production blockers

This module neither connects #1133 to a **real** external witness nor provides the actual external CAS. Both signed READs are fixture data; signing keys and expected public pins, challenge freshness and minimum epoch are caller-supplied. A stolen or substituted pair of keys and matching old heads can still make mathematical equality pass. No distinct administrative custody, durable high-watermark, independent rollback resistance or crypto enrollment is established.

The real system needs an atomically durable claim/fence reservation in an independently protected primary witness and an externally anchored **second trust domain** with exact conflict/recovery semantics, plus the signed owner enrollment and revocation roots (#1131–#1132). The cross-provider prepare/commit is **not atomic**: crash between primary and secondary means **BLOCK** and manual reconciliation, never auto-send. Vendor-side payment/result reconciliation, provider idempotency semantics, quotas and actual cost verification remain unresolved.

**All production authority flags remain FALSE:** owner identity and consent, independent read freshness, witness CAS, cross-cloud atomicity, billing, provider invocation, installer and safe-to-resume. No model credentials, genuine keys, Cloudflare/AWS services, paid API, owner Windows computer, TPM, deployment or spending. No merge, Core V1/`main` unchanged.
