# AION V2 — Existing OpenAI POST transport hardening (Draft only, NO-GO)

**09 October 2026**. Stacked on #1139 → #1138 etc. This change updates the **existing** provider adapter code but remains in an unmerged Draft branch. No real provider request is initiated in CI. Production trust/billing/owner enrollment remains **NO-GO**, regardless of green mocked HTTP tests.

## Specific #1139 finding resolved in source

Before this Draft, `atlasquant_aion_provider.py::execute_openai_answer` performed `client=session or requests`, then `client.post(...)` without explicitly setting `allow_redirects=False`. A caller-injected `Session` could hide mounted POST retries, proxies, custom methods or redirect behavior. One visible `.post` was not proof of one physical attempt.

After this Draft:
- `_sealed_provider_transport()` constructs a **fresh plain `requests.Session()`** per invocation, with `trust_env=False`, `verify=True`, `max_redirects=0`, an `HTTPAdapter` on both schemes carrying `urllib3.Retry(total=0,connect=0,read=0,redirect=0,status=0,other=0,allowed_methods=frozenset(),respect_retry_after_header=False)`. The Session is scoped in a context manager and closed after the send. No SDK auto-retry or caller-mounted adapter is accepted.
- `execute_openai_answer` **rejects any caller-supplied `session`** with `BLOCKED_UNVERIFIED_TRANSPORT`, `called=False`; caller-provided mock or custom `post` override cannot be silently promoted to a production transport.
- The actual `client.post` passes **`allow_redirects=False`**. 3xx responses return `PROVIDER_REDIRECT_BLOCKED`, not `ANSWER_READY` or a second request; any other non-2xx returns `PROVIDER_HTTP_ERROR`.
- A new `transport_policy` object (exact no-redirect/no-retry/proxy/TLS bounds) is **part of the canonical full request material SHA-256** shared by the owner-request preview and dispatch boundary, so the human-reviewed request digest changes if policy changes. Existing digest values from before this branch cannot be reused for this boundary; this is intentional fail-closed behavior.
- Tests using old injected fakes have been migrated **inside the test suites only** to `unittest.mock.patch(..._sealed_provider_transport)`. Production no longer accepts those fakes through the `session` input; tests exercise the post path with inert responses. There is no separate 'testing mode' or bypass exposed in the production adapter.

## What this DOES NOT establish

This does **not** provide globally atomic one-shot provider execution, vendor-enforced idempotency, real invoice settlement, FIDO2 HUMAN_OWNER confirmation, genuine trust-domain enrollment, or remote durable dispatch CAS. A timeout or disconnect after a POST is STILL `UNKNOWN_OUTCOME`; even if the local library is configured for zero retries, a provider may already have processed/billed it, and all upper layers must forbid automatic resend. The existing legacy `request_approved` boolean and local config are NOT an independently authenticated owner signature; this Draft must not be deployed/merged until the separate owner authorization/fencing requirements are satisfied.

The `requests` client uses a fresh built-in transport, but actual physical network behavior, TLS/server certificate validation, DNS/proxy hardening across environments, dependency versions, and library monkeypatching require independent review before a real deployment. HTTP tests hook `requests.sessions.Session.send` to simulate responses; **zero real network calls**.

## New + inherited adversarial tests

- Fresh `requests.Session`: exact no-proxy/no-redirect/zero-retry adapters across HTTP/HTTPS; `Retry` fields are actual integer zero, not boolean false.
- `Session.send` patched at the boundary to track *one simulated physical send* and verify `allow_redirects=False`, `verify=True`, no proxies, exact URL, model POST body/binding.
- 301/302/303/307/308 never followed; 408/429/503, timeout and connection errors do not trigger a simulated duplicate POST.
- Malicious injected session with custom `post`, and regular `requests.Session` with `HTTPAdapter(Retry(allowed_methods={'POST'},total=5))`, both BLOCKED before transport creation.
- Request digest mismatch blocks before constructing a transport; factory failure is conservatively treated as error, no unsourced success.
- Existing #1139 static AST audit now expects the explicit `allow_redirects=False` and removal of the `session or requests` pattern, **but still refuses to certify real physical network behavior**.
- Entire inherited V2/V1 provider suite reruns on Windows and Linux after migrating legacy fake transports to mocked sealed factory.

## Required before any activation

1. Genuine owner signature and presence proof, signed full provider request, protected one-shot outbound dispatch claim and immutable externally witnessed high-watermarks (#1131–#1138), with no gaps from network error to provider billing.
2. Vendor-specific authoritative invoices/usage, exact known response IDs and reconciliation of `UNKNOWN_OUTCOME` without any repeated POST.
3. Validate pinned dependency versions, actual retry/redirect behavior with a local controlled HTTP server and no real billable API, and ensure no alternate callsites bypass the sealed factory.
4. Explicit HUMAN_OWNER approval for merge/deploy, any real credentials, Windows host/TPM enrollment or cloud costs; overall infrastructure cost ceiling remains R$200/month.

**All current code remains Draft/unmerged and cannot be called on live infrastructure in this task. No paid requests, key enrollment, cloud, physical computer, merge or deploy.**
