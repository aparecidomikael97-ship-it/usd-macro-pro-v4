# H0-GW-01 — Offline Synthetic Gateway Laboratory

**DESIGN TEST ONLY — HARD NO-GO. Not a product, not a sender, not H0/F1/T1/F2 proof.**

Source: [RFC H0-GW-01 in #1327](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/issues/1327#issuecomment-6218926750).

## Usage (Python standard library only)

From repository root:

```bash
python -m unittest discover -s labs/h0_gateway_offline -p 'test_gateway.py' -v
```

No third-party packages, provider accounts, credentials, network connections, SNS, SQS, SMS, email, worker, deploy, or access to production Outbox/Saga. `FakeAdapter` is the **only permitted** adapter type. The gateway cannot activate a production worker (`production_worker_eligible` always returns `False`). Local tests do not contact GitHub/AWS/Twilio.

## Threat model and invariants tested

1. Thirty-two independent processes race on one SQLite logical-intent ID; a single local `ISSUE_ONCE` grant, maximum one fake call.
2. Crash after grant-before-call: durable `UNKNOWN`, zero calls, never retries.
3. Crash after fake call-before-response: `UNKNOWN`, never retries, including simulated expiry of external dedupe period.
4. Race PRE-HANDOFF-FENCE vs ISSUE: strictly one successful transition.
5. Exclusive credential assumption and trusted fake adapter only: fail closed.
6. Exact immutable intent binding (`logical_intent_id`, tenant, owner, workspace, channel, destination/payload digest, epoch and key): mismatch denies.
7. Restored/older SQLite file diverges from retained **toy** high-water: deny/quarantine.
8. Synthetic receipt signature/issuer/key/epoch/sequence/nonce integrity + replay guard.
9. `DELIVERED` followed by `FAILED`/old event cannot become no-effect.
10. Fake timeout/429/5xx leaves `UNKNOWN`; late authenticated *synthetic* receipt can record a narrowly typed observed boundary; no resend.
11. Cancel after grant cannot establish provider-side `NO_EFFECT_FENCED`; a late fake delivery is still possible.
12. Missing signer/replaced test key blocks receipts.
13. Policy requiring strong transactional reads rejects weakened eventual-reader configuration (no cloud DB involved).
14. No lookup by logical intention after lost operation ID => `UNKNOWN`, no create retry.
15. Both source/F1/T1 and H0, plus F2 ownership, must be independently proven; production Worker remains disabled unconditionally.
16. Zero-new-spend budget blocks even fake charge without bypassing gate/audit.

## Critical limits — intentionally not claimed

- SQLite is the local **test oracle only**, not the independent external custodian; its file and journal may be rolled back by an administrator. The in-process witness can be killed/modified or updated non-atomically with the ledger. Test #07 assumes it survives storage rollback and **does not demonstrate true antirollback**.
- `SimulatedPolicy(...assumed=True)` is a harness switch, not verified administrative independence, a secret store, enrollment, real source proof or HUMAN_OWNER consent. Tests using it cannot authorize anything.
- The fixture HMAC key is held by the test process, not a trusted provider. Synthetic `DELIVERED` and `CARRIER_ACCEPTED` prove only parser/state-machine behavior, not a network event or recipient delivery.
- The one fake API call property **does not constrain provider retries, carriers, alternate paths, or later delivery**. No terminal `NO_EFFECT_FENCED` can be issued after `ISSUE_ONCE` in this simulator. Fencing before grant is only a local state outcome, not independent H0.
- Multi-process SQLite locking is not proof of distributed DynamoDB/HA correctness, independent witness custody, crash-durable cross-service transaction, AWS administration boundary, or live supplier guarantees.
- Intent rows have no TTL/automatic deletion. Restoring a snapshot without a separate, trustworthy and available high-water can reintroduce risk; real H0 requires non-bypassable external antirollback and exclusivity.
- Positive historical Outbox/Saga integration tests and all **84 historical diagnostics remain outside scope**, not waived or modified. No product module, canonical Quality manifest, PR A118, main branch, CI gates, rollout, budget or account are changed by this laboratory.

**Go/no-go:** synthetic green is a **local design signal only**. HARD NO-GO, `ZERO_AUTO_RESEND`, Worker OFF, no merge or deploy or paid provision or external test. Human-owner authorization must precede any later new infrastructure or provider interactions.
