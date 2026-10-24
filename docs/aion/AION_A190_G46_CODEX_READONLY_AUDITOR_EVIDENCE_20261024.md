# AtlasQuant / AION A190 — G46 Codex independent read-only and scoped SQLite auditor evidence (2026-10-24)

## State, provenance and authority boundary

Draft PR #1533, stacked on G45 Draft #1532 (itself on G44 Draft #1531). No merge to main, deployment, production Worker, provider, customer data, financial effect or credential changes. This work makes a **standalone, mode=ro G43 diagnostic** less likely to falsely label corruption as OK. It does **not** create authentic financial receipts, independent owner identity, H0 monotonic custody or an exactly-once provider transaction.

The two independent Codex sessions used existing Windows `codex.exe` v0.163.0-alpha.11.2, model gpt-6.1-sol, **read-only, ephemeral**, on the isolated G45/G46 checkout:
- Session `01a17053-9d9c-7591-a672-3be217f81e92`, exit 0, ~55.98s, audited G43/G45 and identified three false-OK classes. Codex ran read-only and produced synthetic counterexample descriptions. Its output did not apply patches.
- Session `01a17058-ebad-7ca0-9f12-106c621a623d`, exit 0, ~40.80s, static review of actual G46. It found no grave error in scoped orphan/strict JSON/attempt type fixes, but noted that comparing the main SQLite file bytes in test 10 is **not** verification of WAL/SHM sidecar write-invariance. No testing or changes were performed by this second Codex session.

## Falsifiable RED -> GREEN on actual code

1. New 10-test `labs/a190/test_g46_readonly_adversarial_lab.py` was committed *before scanner fix*, at SHA `299fe2a2d8bc0541cffe8b235874605a076f1e7a`.
2. Executed on authorized Windows isolated checkout against pre-fix G43: **10 tests; 1 passed, 9 FAILED**, including a foreign owner/tenant/workspace hidden orphan, duplicated `state`/`idempotency_key` (including nested duplicate keys), SQL negative attempts with omitted JSON field, bool-as-int attempts and read-only orphan count expected mismatch. These are intentionally RED, not acceptable final CI.
3. `labs/a190/g43_projection_readonly_auditor_lab.py` fixed at SHA `724b3e21f405a871dbb0112def3acd5fbd171f19`:
   - effect-to-outbox orphan join requires matching owner+tenant+workspace, not just idempotency key;
   - `object_pairs_hook` rejects duplicate JSON keys even nested (`JSON_DUPLICATE_KEY`);
   - independently flags negative or noninteger SQL attempt count (`OUTBOX_ATTEMPTS_INVALID`) and noninteger JSON attempt field (`JSON_ATTEMPTS_INVALID`); historical absence of optional projection fields is not categorically rejected.
4. Reran **identical** adversarial suite Windows **10/10 OK**; inherited G45 **7/7**, G44 **39/39**, G43 **32/32**, total **88/88 local**. Checkout `git status --short` clean.

## Exact GitHub Actions evidence

Workflow + code exact tested SHA: **`b3f1a1860dd0b822a9d960fca7d9022330b6386a`**. This report is added afterwards as an **evidence-only commit**; do not confuse report HEAD with CI-tested code SHA.

- [G46 two-OS workflow run #40144720153](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40144720153) SUCCESS: Ubuntu job `121023502115` and Windows job `121023502218` SUCCESS, 88 targeted tests per system, **176** executions total. Tests include G46 10, G45 7, G44 39 and G43 32 per OS.
- [G45 inherited workflow #40144720017](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40144720017) SUCCESS: Ubuntu `121023501399`, Windows `121023501801`, each executes 7 G45 + 32 G43 + 39 G44.
- [G43 broader inherited dryrun workflow #40144720035](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40144720035) SUCCESS: Windows `121023501541`, Ubuntu `121023501707` passed inherited regression steps including G42-G30.

## Untested/RED and next independently identified priority

No separate physical power loss, sidecar WAL/SHM write protection, hostile-host rollback, independent signed monotonic external custodian, authentic provider receipt/owner identity, canonical full Security clean run, or real first-attempt authorization has been established. Previous A184 Security/dependency audit remained RED, with 48 known vulnerabilities in pypdf and Pillow; this G46 path CI does **not** clear that finding.

The second Codex audit recommended an **unresolved G47 reauthorization-integrity falsification** before any H0 claim: `requires_reauth` and `reauth_ref` stored in decision JSON may not be bound by G44's persisted material; synthetic tests must attempt toggling or substituting these fields and mutating them across callback/reconcile boundaries. This recommendation is not a verified G47 exploit or fix until reproduced and reviewed.

**0/6 P0 HOMOLOGATED · HARD NO-GO · UNCERTAIN · ZERO_AUTO_RESEND.**
