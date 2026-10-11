# AION V2 — Enforced hard-deny of legacy paid provider dispatch (NO-GO)

**9 October 2026.** Draft stacked on #1145 → #1144 → #1143 and existing AION reference chain. **A direct security fix in the existing provider adapter**, not an identity service, cloud deployment, owner enrollment or production approval.

## Observed risk, before this Draft

`atlasquant_aion_provider.execute_openai_answer` could initiate a real `requests.Session.post` when five host-controlled conditions lined up: `external_feature_enabled=True`, `request_approved=True`, a permissive local budget, configured provider API credentials and a caller-supplied matching full-request SHA256. The transport was hardened in #1140/#1141/#1142 (zero retry, no redirection, TLS tested locally), but **the host's `request_approved` bool and SHA256 were NOT independently verified HUMAN_OWNER signature or remote fenced once-only dispatch**. A user/admin/backend misconfiguration could therefore reach a paid provider with no genuine enrollment. The #1143–#1145 additions are mathematical references; they are NOT invoked by that legacy production entrypoint and cannot be assumed to authorize it.

## Actual code change

In `atlasquant_aion_provider.py` this Draft adds a **source-fixed `_PAID_MODEL_DISPATCH_HARD_DENY = True`**, with the gate placed *after* existing input privacy, shape, legacy approval, budget and full-request SHA256 validation but **before any caller transport inspection, bearer-header creation, `_sealed_provider_transport()` construction or `client.post()`**.

When those legacy preflights would otherwise permit a call, the production exported `execute_openai_answer` now returns:

```
state = BLOCKED_INDEPENDENT_TRUST_NOT_ENROLLED
called = False
paid_dispatch_authorized = False
model_invocation_authorized = False
provider_called = False
safe_to_retry = False
```

The gate **cannot be disabled** by environment variables, URL arguments, caller-provided session, exact approved request hash, signed-looking JSON, budget limit, user role or legacy boolean. It does not expose any new runtime option for spending or provider activation.

The hard-deny constant **is not a cryptographic root of trust nor a defense against arbitrary code execution**. If an attacker already controls the Python runtime/source, they can patch any in-process policy; source integrity, code signing and deployment governance are independent requirements. This Draft must stay OPEN/DRAFT until separately approved; it does not protect a deployed `main` until explicitly merged and deployed.

## Preserving prior transport tests honestly

All previous positive HTTP/HTTPS tests were laboratory simulations. They now suspend the source lock **only within scoped `unittest.mock.patch(provider._PAID_MODEL_DISPATCH_HARD_DENY, False)` fixture contexts**. Their fake Sessions and exact `127.0.0.1:<ephemeral>` HTTP/TLS socket destination constraints remain intact. This deliberate laboratory escape is **not** a host-supplied production argument, environment configuration, API token, deployment flag or trusted enrollment. It must never be copied to runtime callers.

The new **production entrypoint tests do not patch the lock** and trap `requests.Session.send`, the sealed factory and `requests.post`: they verify no network even when feature, budget, API-key-shaped test data, legacy approval and exact digest all appear valid. Negative controls include caller-injected custom/mounted-Retry sessions, plausible `AION_OWNER_ENROLLED=true` / `AION_REMOTE_FENCING_COMPLETE=true` environment spoofing, reasoning lane, SHA256 mismatch, disallowed budget, missing legacy approval, privacy-sensitive inputs and AST assertion that the literal lock is in the exported function above the actual HTTP POST.

## Formal requirements for real activation (NOT YET SATISFIED)

Before **any** change to the fixed lock, require a separately reviewed and owner-approved implementation with evidence for each item:

1. **Owner identity:** independently enrolled HUMAN_OWNER public key / credential custody, trusted FIDO2 or Windows Hello presence where applicable, exact V2 Ed25519 signed full HTTP request and source persisted chat turn. A string claim of `ADMIN` or caller-passed pin is not sufficient.
2. **Independent host session issuer:** authenticated verifier root pinned outside caller-provided data, trusted clock/session not-before+expiry, anti-replay challenge consumption, revocation and audience/tenant scope enforcement. No synthetic host `access` dictionary can be elevated.
3. **Separate signed witness roots:** PRIMARY_WITNESS + SECONDARY_ANCHOR operate in separate enforced administrative domains; each has a separately protected monotonic epoch and public key registry, independently anchored so the user/chat DB and both head stores cannot all be rolled back together.
4. **Atomic protected dispatch fence:** one-time authoritative CAS/high-watermark key tying HUMAN_OWNER/tenant/workspace/conversation/message/nonce/policy/model/full POST SHA/request budget. The fence and any successful server-side claim cannot be rolled back with local SQLite. Fail closed after CAS failure, timeouts, partitions, fork, missing receipt, or retained UNKNOWN_OUTCOME. Never automatically re-POST.
5. **Actual budget and billing evidence:** payment instrument and API keys kept in secret manager, invoice/rate/usage receipts from the vendor, ongoing quota/circuit breaker, signed immutable audit log with evidence of no duplicate vendor charges. Tests use no paid keys and cannot certify this.
6. **Deployment release gate:** separate explicit HUMAN_OWNER approval for merge/deploy, key enrollment, real API consumption and infrastructure costs; pinned dependencies, no SDK retry, TLS/proxy/DNS in actual environment, red-team and read-after-write verification. Total infrastructure ceiling R$200/month, and no Worker/Render changes without permission.

A future trusted admission protocol **must be a new reviewable contract**, not a bool such as `request_approved=True` or simply setting `_PAID_MODEL_DISPATCH_HARD_DENY=False`. Do not remove lock until every required proof exists and owner explicitly approves. Unknown POST outcome remains UNKNOWN; HTTP 404/timeout does not imply free or safe retry.

**NO-GO remains:** Frozen Core V1/main unmodified. No real owner device/TPM, FIDO2 enrollment, vendor HTTP GET/POST, production spend, cloud provision, secrets, release, merge or deployment in this Draft.
