# A190 G28 — Signed global-ledger tip CI and Codex parallel static audit

Date: 2026-10-24. **Exact tested code SHA**: `7f12775a497e44ad937a5fef52fe39171097a37d`.

## Verified LAB CI
- [GitHub Actions #40122102170](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40122102170): completed SUCCESS.
- Ubuntu `120955701336`: **18/18**.
- Windows `120955701088`: **18/18**.
- **36 executions** of 18 distinct tests.

### Positive boundary
`G28_CROSS_KEY_ROLLBACK_GREEN=GLOBAL_ANCHOR_DETECTS_MISSING_OTHER_INTENT`: a synthetic retained global tip records two different intents. When local SQLite is rolled back to the older one-intent snapshot, comparison against that retained tip fails closed. This addresses a limitation of solely per-semantic-key checks **in the laboratory only**.

### Deliberate REDs
- `G28_NONATOMIC_GAP_RED=LOCAL_COMMIT_AHEAD_OF_ANCHOR_DENIED`: if local reserve committed but external update did not, recovery denies; there is no atomic two-system first-attempt reservation.
- `G28_CO_ROLLBACK_RED=HOST_CAN_RESTORE_DB_AND_ANCHOR`: a host able to revert both the SQLite file and the synthetic anchor can present consistent old evidence.
- The simulated anchor is another object **in the same process**, with ephemeral signing keys and **no independent monotonic custody**.
- Global ledger tip reads in the LAB are not explicitly serialized with concurrent writers across the entire snapshot. This is not a production atomicity claim.

## Parallel Codex review — read-only, disconnected from G28 patch
- Codex CLI `v0.163.0-alpha.11.2`, model `gpt-6.1-sol`, using `exec -s read-only` in isolated local checkout `C:\Users\apare\AtlasQuant-G18-Windows-LAB-20261024`.
- Review is **static, from that checkout**, NOT an independent G28 CI run, not necessarily latest main, not real-provider behavior.
- Codex did not edit repository files. The following are investigation candidates, not five independently reproduced exploits:

| # | Static finding | Path / indicative lines | Scope |
|---|---|---|---|
| 1 | Backup/restore does not prove independent freshness | `aion_chat/store.py:568` | P0 rollback and forgotten intents; no external reexecution |
| 2 | Idempotency key includes caller-supplied `intent_ref` | `atlasquant_aion_execution_outbox.py:346`; `labs/a190/g13_signed_semantic_outbox_bridge_lab.py:65` | Semantic alias with different caller reference |
| 3 | Idempotent replay may return prior decision without comparing changed policy/authorization/expiry fields | `atlasquant_aion_execution_outbox.py:344,369-374` | Dispatch has separate checks; not proof of unauthorized effects |
| 4 | Digest is computed after redaction, which may collapse different semantic payloads | `atlasquant_aion_execution_outbox.py:344`, `labs/a190/g13_signed_semantic_outbox_bridge_lab.py:36` | Depends on what redaction removes |
| 5 | SQLite rollback exceptions not always isolated and can mask original failure | `aion_chat/store.py:713`, `atlasquant_aion_execution_outbox.py:451` | Failure injection needed to prove state leakage |

Codex review did not independently validate production code SHA, apply changes, or run tests. Its conclusions guide a **separate LAB fault-injection and semantic-alias matrix**; no P0 is closed by the review.

## Guardrails
No merge/main, deploy, Worker, real provider, first-send external atomic reservation, independent external signer, durable hostile-host antirollback, customer data, secrets, or budget increase. Canonical Quality/Security not rerun. No operational AION changes.

**0/6 P0 homologated · HARD NO-GO · UNCERTAIN · ZERO_AUTO_RESEND.**
