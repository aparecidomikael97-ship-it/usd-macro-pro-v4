# AION V2 — live provider adapter retry/redirect findings + offline GET-only transport gate

**Date: 9 October 2026. Draft on #1138 → #1137 → #1136 → #1135 and predecessors. HARD NO-GO for production.**

## Concrete existing-code audit finding

The current `atlasquant_aion_provider.py::execute_openai_answer` resolves the full provider POST request and checks the digest before calling `client=session or requests`, then `client.post(endpoint,headers=...,json=...,timeout=...)`. There is **no explicit `allow_redirects=False` keyword** at that send boundary, and the injected `session` is not screened for mounted `HTTPAdapter`, `urllib3.Retry`, custom `post` overrides, or transport interception. It is inaccurate to assert the current adapter enforces at-most-one physical provider POST or prevents all redirections.

This is a **source-level finding**; it does not prove that a particular real provider request has ever redirected or retried. The adapter remains disabled by default behind other gates and neither this Draft nor its CI invokes an actual provider.

Official library evidence:
- [Requests Quickstart: Redirection and History](https://requests.readthedocs.io/en/latest/user/quickstart/): by default Requests follows redirects for methods except HEAD; `allow_redirects=False` is supported for POST/GET.
- [Requests Advanced Usage: Automatic Retries](https://requests.readthedocs.io/en/latest/user/advanced/): an injected/custom `Session` may mount `HTTPAdapter(max_retries=Retry(...,allowed_methods={'POST'}))`.
- [urllib3 Retry](https://urllib3.readthedocs.io/en/stable/reference/urllib3.util.html): `read`, `other`, `status`, and `redirect` retry controls; `allowed_methods=None` may permit all methods. Retry of a non-idempotent POST after possible processing can cause duplicate charge. Any total=0 policy should still be tested with the exact installed dependency version.
- [Requests Developer Interface](https://requests.readthedocs.io/en/latest/api/): adapter retry settings; Requests defaults alone are not a certification for injected sessions.

**This Draft does not patch the existing live adapter**, avoiding a deceptive safety claim while the HUMAN_OWNER enrollment, remote dispatch claim/fencing, and device authorization remain absent. The concrete code finding must be fixed in an independent guarded implementation and proved in a future integration test before production. Never infer no retry merely because `execute_openai_answer` contains one textual `.post()`: an adapter may send multiple physical attempts per call.

## New no-network reference

`atlasquant_aion_v2_http_retry_redirect_boundary_reference.py` includes:

1. **AST audit of the real adapter** `audit_existing_provider_source(source)`: parses source without executing code, confirms exactly one visible `.post` site, reports missing static `allow_redirects=False`, caller-injected `session` retry policy not attested, and full request digest presence. AST cannot attest hidden urllib3/TLS/redirect behavior; even 'looks safe' is not production approval.
2. **Strict offline GET transport shape**, accepting only existing untrusted #1138 mathematical capture witness match and fixed provider hostname/path: OpenAI `https://api.openai.com` and `/v1/responses/resp_...`; Anthropic `https://api.anthropic.com` and exactly the batch-status route followed by its `/results` route. No arbitrary path/origin, percent encoding, query/fragment, method rewriting, signed credentials or HTTP libraries. Deliberately rejects standalone Anthropic results without paired batch lookup, sync/generation routes, any POST.
3. Requires **all** proposed transport controls to be explicitly equal with exact types to `method=GET`, `allow_redirects=False`, `trust_env=False`, `verify_tls=True`, `max_attempts=1`, `http_adapter_retry_total=0`, `sdk_auto_retry_enabled=False`, `proxy_configured=False`, `follow_location_header=False`, `allow_method_fallback=False`, finite 1–30 second timeout. No wildcard retries, automatic proxy routing or external redirects.
4. **Offline synthetic trace classifier** blocks >1 attempt per planned path, any GET→POST/HEAD fallback, 30x redirects, second batch results GET after failed first status GET, cross-origin requests, repeated same path, non-GET methods and malformed status events. For one conservative synthetic attempt yielding HTTP 404/408/429/503 or timeout, it still reports untrusted trace and **NEVER permits automatic retry or billing settlement**.
5. All outputs — even a `GET_PLAN` or a valid simulated trace — are only test *data*, NOT permission to perform an actual GET, authenticate a provider, trust an owner, use a billing channel or send a new paid generation POST.

## Explicit counterexamples and residual risk

- A caller can fabricate a #1138 `TWO_SIGNED_CAPTURE_HEADS_MATH_MATCH_UNTRUSTED_NO_NETWORK` result with a plausible path. The reference may produce an offline GET configuration but this has **zero independent signer or provider-ID provenance**.
- Even an AST that sees `allow_redirects=False` cannot verify how an injected/customized HTTP object internally behaves, nor detect hidden automatic POST resubmissions. Traces are caller-provided simulated events; a malicious SDK could omit physical retries from its reported logical events.
- A valid read-only GET by known ID is *not* evidence that the original POST was idempotent, unbilled or safe to repeat. If server-issued response ID never arrived before crash, recovery stays UNKNOWN. If it did, retention may expire and a GET 404 is not proof the provider did not process a request.
- Actual shared Keys/Cloud/Windows identity proof, two noncolluding independently protected monotonic capture+dispatch witnesses, provider-sourced request ID, actual live SDK transport tests, HTTPS verification, DNS/redirect/proxy containment and provider invoice reconciliation are not implemented here.

## Test coverage

CI on GitHub Windows + Linux; isolated synthetic GET trace tests for GET-only host/path/method confinement, 300-range redirects, timeouts, 429/503, automatic retries disabled, `total=0` integer not bool, proxy environment denial, TLS exact configuration, batch ordering, repeated GETs, crafted fallback POST and static audit of **actual existing adapter file**. Inherited #1138–#1125 security, nonce, journal, provider, V1 regression suites run unchanged. All network functions mocked and guarded; this new module imports no Requests/httpx/urllib3 network client at all.

**Status is NO-GO.** No actual API, keys, remote enrollment, credentials, new cloud/billing, Windows computer access, PR merge, deployment or installer. Frozen Core V1 and `main` untouched. Entire infrastructure cost ceiling remains R$200/month and requires separate authorization before real services.

**Next admission milestone:** explicit no-redirect physical POST transport with auditable one-shot dispatch fencing and verified absence of SDK retries, tied to genuine HUMAN_OWNER/dual-independent-monotonic trust; owner approval required before even creating real keys or enabling service.
