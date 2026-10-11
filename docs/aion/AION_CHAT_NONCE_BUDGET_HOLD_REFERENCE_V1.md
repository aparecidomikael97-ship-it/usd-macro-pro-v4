# AION Chat — Single-Use Nonce + Budget HOLD Reference V1

**Review date:** 2026-10-09. **Stack:** #1119 model preflight → #1120 scoped pending user turn → #1121 mathematically signed consent → this CI-only Draft.

## Why this is required

A valid Ed25519 signature from #1121 proves **only mathematical integrity
against the host-supplied public key**, not that the key belongs to the
HUMAN_OWNER. That verifier accepts repeated valid signatures, because it has
**no durable replay or budget reserve**. Before connecting Chat → LLM, both
single-use and financial controls must be atomic and reconciled.

This module adds a **reference-only, actually persisted SQLite hold**, not a
production payment or a real security witness. Its caller must supply the
`Scope`, authenticated access, **already persisted** user message from
#1120, exact final prompt, signed envelope from #1121, separate public pin,
host quote and a fixed reference budget policy. The function recomputes the
signature check itself and refuses any claimed boolean `verified` from a
client. It **never calls `execute_openai_answer`** or produces an assistant
reply.

## Durable local reference semantics

- SQLite `BEGIN IMMEDIATE`, `PRAGMA synchronous=FULL`, WAL and unique
  constraints reserve **nonce globally**, **signed intent digest**, and
  **one hold per scoped user message**; repeated identical approval sees
  the previous hold, not a second debit.
- The transaction stores **the maximum amount explicitly signed**, not the
  lower estimated quote. `host_quote_micro_usd` is only a checked
  precondition and must not exceed the signed maximum.
- Fixed per-file tuple: owner, tenant, workspace, month identifier, expected
  policy generation, injected host public pin SHA-256 and maximum USD
  microunits. A changed configuration on reopen is rejected: no automatic
  reset, policy downgrade, month rollover or refund. This is conservative
  by design and not a finished subscription/billing engine.
- A row count + sum check detects some corruption of the *reference*
  tables; it is not an independent tamper-proof ledger.
- Two distinct signed intents competing for a remaining cap serialize:
  when the total would exceed the immutable reference cap, the later
  transaction blocks.
- A commit followed by lost response may safely be **read back** as the
  same held intent. An uncommitted failure rolls back and can be retried
  against the same reference store. No external API call is retried.

## Limitations that prevent any production use

1. **A local DB restored with an old copy resets every hold and nonce.**
   Restoring both Chat DB and this reference file allows replay. A system
   administrator with file control can change both. This is NOT the
   independent protected monotonic witness designed by #1116, and even
   #1116's runner witness is RAM-only.
2. The public key pin is provided by the caller; no independent enrolled
   HUMAN_OWNER identity/custody or authentication is proved. An attacker
   controlling both the pin and its signing key can produce mathematically
   valid signatures. Reopening the same file with a *different* pin blocks,
   but rolling back or replacing the file also defeats that.
3. The reference period is configured by the caller, not trusted time.
   There is no secure rollover, cancellation, refund, release, charge
   settlement, currency conversion or live pricing. A signed microunit USD
   number **does not** prove compliance with the R$200/month infrastructure
   goal.
4. Chat user records and this reference ledger are **two separate SQLite
   transactions**. There is no distributed exactly-once; the already
   persisted user message is re-read at candidate review, but could
   theoretically change between preflight and commit if host storage is
   compromised. No trusted host provenance is attested.
5. The reference `REFERENCE_HELD_UNTRUSTED` flag reports only that the
   disposable ledger reserved a number. It must NEVER be passed to
   `request_approved=True` or interpreted as real monetary funds or
   HUMAN_OWNER consent. Real provider POSTs can be billed even after a
   timeout; the final execution protocol requires a durable attempt
   ledger and `OUTCOME_UNKNOWN` reconciliation without blind retry.
6. The 35+ tests use synthetic messages, ephemeral keys, offline
   disposable SQLite and fake transport only. **No provider, card, bank,
   collector, host `am12`, Windows security setting or production store
   is touched.** The implementation is not wired to Streamlit.

## Mandatory GO/NO-GO prerequisites for real AION model inference

- Independently enrolled HUMAN_OWNER key with possession/consent, scoped
  to one exact final sanitized prompt, model, cost limit and policy.
- Protected independent monotonic nonce witness anchored against full
  DB restore, signed state reconciliation and safe loss/recovery policy.
- Transactional real budget reservation + settlement with verified
  tariffs, USD/BRL conversion where relevant, owner-approved cap,
  verified month rollover and refund/unknown-outcome handling.
- Production scope isolation, data-protection/PII policy and provider
  data processing approval, pre/post audit and no tool authority from LLM
  text.
- Explicit approval for paid API keys/use, production DB activation,
  deploy and, separately, eventual Windows host actions.

**Always false**: `trusted_human_owner_consent`,
`independent_witness_protected`, `hardware_antirollback_verified`,
`real_budget_reserved`, `model_invocation_authorized`,
`provider_called`, `real_billing_authorized`,
`installer_authorized`, `safe_to_resume`.

NO MERGE, NO DEPLOY, NO REAL OWNER KEYS, NO COSTS, NO PC ACCESS.
