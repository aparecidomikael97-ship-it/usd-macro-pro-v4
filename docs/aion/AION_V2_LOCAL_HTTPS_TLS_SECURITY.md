# AION V2 — Real HTTPS/TLS integration on isolated local CI loopback

**Date:** 2026-10-09. **Draft stacked on #1141 → #1140 → #1139.** This is a test-only, disposable HTTPS fixture: **NO GO for live provider deployment, real keys, paid calls or owner device changes.**

## Gap closed beyond #1141

#1141 uses a local **plaintext HTTP** server with the actual Requests→HTTPAdapter→urllib3→TCP stack, and proved zero re-POST in simulated disconnect, redirect, timeout, 429/503. It cannot prove that the client enforces TLS certificate validation.

This Draft introduces `tests/test_atlasquant_aion_provider_tls_loopback_integration_v2.py`, which sends a genuine *HTTPS* POST through the same hardened #1140/#1141 adapter to a local server that is reachable only via `127.0.0.1` on GitHub-hosted Windows/Linux CI runners.

## Exact secure test construction

1. Generate a **disposable P-256 elliptic-curve CA private key and CA certificate in RAM**, and a separate leaf server key/certificate signed by the CA. All test-only private keys are written to a TemporaryDirectory on the CI runner to let Python `ssl.SSLContext.load_cert_chain` use them, never checked into Git, uploaded, logged, exported, deployed or used for the owner.
2. Valid server leaf binds **IP SAN `127.0.0.1`**, not a hostname alias. CA basic constraints, leaf CA=false and server-auth extended key usage are set. Server `ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)` requires TLS 1.2 or newer. Server binds solely to loopback `127.0.0.1:0` and shuts down after the test.
3. In the tests **only**, `unittest.mock.patch(provider._sealed_provider_transport)` returns a fresh production-like sealed `requests.Session`, preserving all no-retry/no-redirect/no-ambient-proxy settings and replacing its `verify=True` with `verify=<temporary CA PEM path>`. This maintains **certificate verification enabled and hostname/IP SAN matching**, rather than disabling it. No change to production code.
4. Test-only `provider.OPENAI_RESPONSES_URL` is patched inside each call to the exact generated `https://127.0.0.1:<port>/v1/responses`. Preview and dispatch digest use the same fixture target; production default remains unchanged and is not externally configurable.
5. A local scoped `socket.socket.connect` guard rejects **any IP or port other than exact 127.0.0.1:<server_port>**. Any external provider/DNS/proxy contact aborts the test. All model request data and API-key-shaped bytes are synthetic and have no external value.

## Security cases exercised with actual HTTPS handshake and TCP

- Trusted temporary CA + proper IP SAN → one HTTPS wire POST with exact synthetic JSON and response ID, no other request.
- Unknown CA using the unmodified production `verify=True` → TLS `SSLError`; the server sees **zero HTTP requests** (TLS handshake rejected), no retry.
- CA-signed certificate with **wrong SAN** → TLS `SSLError`, no HTTP request, no retry.
- CA-signed but **expired leaf** → TLS `SSLError`, no HTTP request, no retry.
- 307/308 with hostile `Location: https://different-host.invalid/evil` → `PROVIDER_REDIRECT_BLOCKED`, precisely one local POST, no cross-origin request.
- HTTPS 503 with `Retry-After` → one local POST, `PROVIDER_HTTP_ERROR`, no retry.
- TLS connection deliberately dropped **after the local server has received the entire POST body** → `PROVIDER_NETWORK_ERROR` with `called=True`; exactly one POST observed, no retry. **The actual provider could have processed/charged it. The result remains UNKNOWN and cannot be safely re-sent.**
- Absent approval / changed signed SHA256 → no TLS attempt, zero connections.

## Explicit limitations and action boundaries

HTTPS to a disposable locally trusted CA on GitHub CI verifies expected **client-side TLS/SAN behavior**; it does **not** prove that the real OpenAI endpoint's cert is trusted or that live TLS/DNS/proxy/CDN environments preserve the same behavior. A local TCP count is not an authoritative vendor invoice or idempotency receipt; no global exactly-once execution or replay-resistant owner authorization is established. Replacing a CA trust file inside the tests is not owner key enrollment, vendor pinning, runtime configuration, or permission to bypass trust store checks.

**Still required for production:**
- Real owner signature/physical presence with trusted enrollment, separately authenticated reviewer, protected one-shot durable dispatch CAS and independent monotonic witness domains.
- Authenticated provider receipt/usage/cost reconciliation for `UNKNOWN_OUTCOME`; no automatic paid POST retry.
- Protected response/batch ID capture and provider-specific GET-only recovery, subject to retention.
- Explicit HUMAN_OWNER consent to merge/deploy, enroll any keys, install local agent, provision remote service or spend; total infrastructure budget target remains R$200/month.

**Frozen Core V1/`main` preserved. No real provider API call, commercial certificate, paid token, cloud environment, owner PC or deploy.**
