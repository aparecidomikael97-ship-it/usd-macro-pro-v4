# A190 G29 — Real ExecutionOutbox semantic and authorization RED CI

Date: 2026-10-24. **Exact tested code SHA:** `c8e50805f180f215a74d2d238336d2d3378b428a`.

## Executed evidence

- [GitHub Actions run #40122511595](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40122511595): **completed SUCCESS**.
- Ubuntu job `120956929572`: **20/20** distinct test cases.
- Windows job `120956929821`: **20/20** distinct test cases.
- Total **40 test executions** of **20 distinct tests**.
- Actual `ExecutionOutbox` + `SQLiteChatStore`, using synthetic temporary local SQLite databases and `enqueue/get/list`; G13 digest is computed for comparison.
- **No** `dispatch_claimed`, Worker, provider calls, operational effects, real customer data or production trust roots.

## RED reproductions: observed staging behavior, not dispatch authorization exploits

| ID | Observed real staging behavior | What this **does not** establish |
|---|---|---|
| `G29_POLICY_REPLAY_RED` | Same `intent_ref` + changed `policy_version` returns `IDEMPOTENT` and old policy decision | Dispatch gate independently checks policy at send time; no send was tested |
| `G29_AUTH_REPLAY_RED` | New `authorization_ref` does not replace the stored one | No actual authority bypass proven |
| `G29_EXPIRY_REPLAY_RED` | Replayed shorter `valid_until` returns old expiry | No expired-authority dispatch tested |
| `G29_REAUTH_REPLAY_RED` | New `requires_reauth=True` returns old decision lacking reauth | No actual reauthentication or dispatch |
| `G29_REAUTH_REF_REPLAY_RED` | Changed `reauth_ref` returns previously stored reference | Current dispatch has separate revalidation |
| `G29_CALLER_ALIAS_RED` | Two different caller `intent_ref` values for same action, aggregate and payload produce two distinct local reservations | Not two external sends |
| `G29_REDACTION_ALIAS_RED` | Different values of a `token` field map to `[REDACTED]` and same Outbox key | Credential values in this scenario may not be business-semantic; only information loss demonstrated |
| `G29_G13_DIGEST_REDACTION_RED` | Distinct raw credential-bearing payloads produce the same G13 semantic operation digest | G13 pin is synthetic, no independently verified issuer |

These cases become security-critical if replay metadata or redacted fields are used as authoritative permissions or business identity. A fail-closed operational design must not silently assume either.

## Positive controls

- Same `intent_ref` + genuinely changed non-redacted `amount_minor` denies as `intent_ref idempotency collision`.
- Different action / changed transaction risk binding likewise deny idempotency collision.
- Default injected true-returning evidence and first-attempt callbacks are **quarantined**.
- Scope separation works as observed for another workspace.
- No effects were created; the tested staging API exposes `executes_action=False`.

## Engineering gate proposal (NOT implemented)

1. Keep an independently attested semantic business operation ID separate from caller request IDs.
2. On identical `intent_ref` with changed authorization, policy, expiry or reauth contract, return **explicit pending reapproval/conflict** rather than silently representing the old decision as acceptance of new terms. Do not infer that replacing the existing decision would be safe.
3. Separate redacted *display/storage projection* from a privacy-preserving authoritative semantic commitment, with explicit allowed source fields, tenant scoping, domain separation, key custody and resistance to low-entropy guessing. Simply hashing sensitive raw data is not a safe substitute.
4. Require external monotonic first-send reservation and verified provider receipt before any operational SEND/RETRY decision. Persist uncertain outcomes with no blind auto-resend.
5. Use additional synthetic fault injection for the remaining Codex hypothesis: rollback exceptions and connection recovery (not covered by G29).

## Scope

Passing tests are successful reproduction of RED observations, **not** remediation or P0 homologation. No provider, Worker, merge/main, deploy, active customer data, real authentication, external trustworthy custody, canonical Quality/Security rerun or actual H0 recovery proof.

**0/6 P0 homologados · HARD NO-GO · UNCERTAIN · ZERO_AUTO_RESEND.**
