# AION V2 — Real Requests/urllib3 POST with loopback-only HTTP server

**09 October 2026.** Draft stacked on #1140 (actual POST hardening) → #1139 (audit) → #1138 and earlier. **NO-GO FOR DEPLOYMENT AND PAID API CALLS.** No owner PC access, real API token, cloud service, billing, merge or activation.

## Purpose and exact boundary

The previous #1140 adversarial tests patched `requests.sessions.Session.send`, proving the function calls into that boundary once but **not** exercising the real adapter, urllib3 network retry behavior, TCP connection or server response processing. This step exercises the **actual Requests Session → HTTPAdapter → urllib3 → TCP socket → local HTTP server** in a self-contained GitHub Actions test.

Only a synthetic HTTP server is permitted. It binds to the exact IPv4 loopback address **127.0.0.1 with OS-assigned ephemeral port** on the GitHub CI runner. The test patches `atlasquant_aion_provider.OPENAI_RESPONSES_URL` in-process to `http://127.0.0.1:<ephemeral>/v1/responses`, and the canonical request SHA-256 is computed from that same replaced endpoint. The production constant remains `https://api.openai.com/v1/responses` in the repository and is unchanged by this Draft. **No production configuration flag enabling custom target URLs is added.**

A scoped `socket.socket.connect` guard permits only that exact loopback destination and port during the tested outbound invocation. Any attempted external connection raises an exception and fails the test. Credentials are **fake noncredentials** used only to satisfy offline shape checks. Request and response bodies are synthetic. The local server never logs Authorization or exposes a public binding. It is started and shut down inside each test, never deployed as a service.

**Important distinction:** loopback TCP is a genuine local network call **on the CI runner**. It is NOT a real public internet/provider call, so there are no paid inference or cloud activation charges; it also does not validate TLS certificate or DNS/HTTPS production behavior.

## Tests and expected evidence

`tests/test_atlasquant_aion_provider_real_loopback_http_integration_v1.py`:

- 200 synthetic JSON response yields one real local socket connection, exactly one wire-observed `POST /v1/responses`, correct canonical JSON body, status `ANSWER_READY`; no real model.
- 301/302/303/307/308 responses set `Location: http://127.0.0.1:<port>/redirect-trap` and must yield **one POST only** with `PROVIDER_REDIRECT_BLOCKED`, no redirected path visit.
- 408/429/503/504 with `Retry-After` headers must yield **one POST only** and terminal local `PROVIDER_HTTP_ERROR`; no transparent Requests/urllib3 retries.
- TCP close **after the local server receives the full POST body but before replying** must yield `PROVIDER_NETWORK_ERROR` and exactly one server-observed POST; this is the representative danger of a potentially processed but lost paid request. **It must never be automatically resent**.
- Server delays reply beyond configured **5-second minimum** timeout; the client must stop after one POST and report network error. This test is intentionally slow but contained to one isolated local fixture.
- Missing legacy approval, budget, external feature, exact reviewed digest, caller-injected `requests.Session` or altered endpoint after preflight must **block before any socket.connect**.
- On each outbound invocation a guarded socket connection rejects any attempt to use a non-loopback IP, DNS provider hostname, proxy or nonfixture port. A synthetic successful trace is NOT proof of external provider billing, idempotency or owner approval.

## Claims this CANNOT support

- A single local wire POST does **not** prove global exactly-once delivery to an external provider, billing accuracy, refund eligibility or a trusted externally protected journal.
- Some outbound POST could reach the server before the socket drops; therefore a client timeout must be `UNKNOWN_OUTCOME`, not assumed `NOT_PROCESSED` or safe for an automatic retry.
- This test uses plaintext local HTTP, **not** real HTTPS/mTLS/provider certificates, CDN/load-balancers, proxy layers or DNS. It does not establish how a deployed environment will behave under any service mesh, node restart or remote provider HTTP semantics.
- Direct calls to the hardened adapter still rely on legacy feature/configuration/Boolean approval. Real HUMAN_OWNER Ed25519 enrollment, FIDO2/Windows Hello presence, independently protected primary/secondary monotonic high-watermarks, and globally fenced one-shot dispatch are not implemented by this PR.
- The new tests do not change the actual production execution function: that hardening remains isolated in parent Draft #1140. No real deployments, purchases, accounts, API keys, merges, owner desktop commands or cloud infrastructure.
- The total future infrastructure ceiling remains **R$200/month**, requiring explicit approval for changes or spending.

## Required next work

Before any paid endpoint can be considered, an independently authenticated HUMAN_OWNER must approve the immutable resolved provider request and the system must atomically reserve/consume one-shot dispatch in a durable, externally protected trust domain. Any network result-loss state needs authoritative vendor reconciliation rather than automatic POST. Separate future staging could consider a dedicated loopback TLS fixture and complete end-to-end protocol testing; **this test is no production activation gate**.
