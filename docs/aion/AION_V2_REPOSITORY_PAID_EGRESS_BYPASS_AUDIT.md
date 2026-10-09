# AION V2 — repository-wide Python paid-provider egress bypass audit

**9 October 2026.** Stacked Draft on #1146 (actual paid POST hard deny). NO production activation, no paid API calls.

## Why

#1146 source hardens `atlasquant_aion_provider.execute_openai_answer` with a fixed hard deny. That alone cannot rule out a *different* file importing another AI provider SDK, calling `requests.post`, creating an HTTP client or sending directly over `httpx`. A single protected entrypoint is not enough if an unreviewed second entrypoint becomes available.

This Draft installs a **source-only Python AST audit of all production `.py` files** (including the existing B2B and worker code, excluding explicit tests, generated environments and ordinary test fixtures). It NEVER imports inspected modules, initializes secrets, invokes SDKs or opens sockets. It uses a strict allowlist of **one known risky outbound HTTP callsite** in `atlasquant_aion_provider.py::execute_openai_answer -> client.post`, and verifies that site's **source-fixed hard deny** remains a single literal `True` assignment and a blocking return before the send site, with all paid authority booleans FALSE. Any unknown candidate callsite fails CI. This creates a concrete regression constraint: a new direct vendor SDK model invocation or outbound HTTP POST cannot silently join the codebase without independent security review.

## Exact checked sink forms

- Any Python source call with `.post(...)`, including `client.post`, `requests.post`, `httpx.AsyncClient().post`, without allowing arbitrary second files.
- `.request()`, `requests.Session().send()`, or imported-alias versions, relevant `.put`/`.patch`/`.delete` with HTTP imports.
- Imported vendor SDK constructors and model calls from OpenAI, Anthropic, google.generativeai/google.genai, litellm, Cohere, Groq and Mistral. Unscoped `.responses.create` / `.chat.completions.create` / `.messages.create` / `.generate_content` model methods are rejected even when client type is unknown.
- Direct `urllib.request.urlopen`, urllib3 PoolManager and aiohttp ClientSession constructors.
- Non-parsable Python source fails closed; lock missing, duplicated or disabled, a gate moved after POST, wrong block return state or permissive auth flag in the deny return all fail.

The scanner reports file relative path, line number, safe call expression and count. It does **not** dump key material, prompt strings or entire source in its report.

## Scope, caveats, and no-go

This is **static source analysis only**, not runtime/supply-chain proof. It does not establish the actual vendor endpoint, TLS trust, installed SDK behavior, dynamic imports, reflected `getattr`, `eval`/`exec`, compiled Python, ctypes, monkeypatching, subprocess `curl`, shell, containers, JavaScript/TypeScript, minified/generated assets, or code pulled from external packages. In some of these cases, additional manual and automated analysis is required; a green result is not an absence proof for every language or malicious code execution. The scanner excludes tests and fixtures on purpose to avoid mistaking synthetic HTTP/TLS tests for production egress.

Additionally, source and CI on a **Draft branch** do not protect the already deployed `main` or any live provider infrastructure. Any source-editing attacker able to disable CI/source policy is outside this gate; repository protections, code signing, trusted CI and deployment rules require separate owner-controlled configuration.

## Validation and next tasks

`tests/test_atlasquant_aion_v2_repository_paid_egress_static_audit.py` runs synthetic mutation cases against temporary miniature trees, including new direct SDK/HTTP clients, alias imports, missing/false/duplicated hard deny, unexpected second post, false authorization return and syntax errors. A final integration test scans the **actual checked-out repository tree** and requires the sole known paid sink to retain its source hard deny.

GitHub Actions Windows and Linux: compile scanner/test, execute source scanner as hard gate, run mutation tests and full inherited #1146→V1 provider security battery (includes synthetic HTTP and HTTPS loopback), no live cloud. Any new potential sink fails CI with a report, not an automatic allowlist expansion.

**Release remains NO-GO** until HUMAN_OWNER enrollment/physical presence, independently trusted IdP session, protected primary/secondary witness roots, durable remote one-shot dispatch CAS, genuine provider response and billing reconciliation and owner-approved live deployment. Do not set `_PAID_MODEL_DISPATCH_HARD_DENY=False` just to allow a provider call. The infrastructure cap target remains R$200/month. Frozen Core V1 and `main` unchanged; no merges/deploys, paid calls, real keys, owner computer/TPM or cloud provisioning.
