# AION V2 — Legacy GitHub HTTP write URL provenance review (REFERENCE ONLY)

**9 October 2026. Draft stacked on #1147. No merge, deploy, real credentials, paid calls or owner's PC. Frozen Core V1/main unchanged.**

## Source audit evidence and goal

#1147 proved via a source-only Python AST scan that the branch has two known separately hard-denied **paid OpenAI POST** callsites (Responses and TTS), plus **21 other** pre-existing network WRITE callsites. The latter were previously pinned solely by module/function/method; the code could change the *first HTTP URL parameter* to a vendor endpoint and retain the same AST call signature. This Draft adds a fail-closed **provenance and expected route audit** across all 21 exact legacy callsites: 17 writes must originate from a fixed `https://api.github.com/repos/` literal before any dynamic repository/path interpolation and contain `/contents/` in the static path, and four global-worker flag mutations must originate from fixed GitHub `/actions/variables` source constructors.

### New source-only CI checker
`atlasquant_aion_v2_legacy_github_destination_source_review.py`:
- Reads the **existing exact 21 callsite inventory** imported from #1147, no broad exceptions. Discovers the exact function and exactly one matching outbound method call in the checked-out source.
- Traces the first positional HTTP destination: a local `url` assignment, a canonical fixed-host f-string, or one of four allowlisted GitHub REST helpers (`_url`, `_contents_url`, `_variable_collection_url`, `_variable_url`).
- Forbids untrusted caller-supplied `url` arguments, duplicate or mutated assignments, arbitrary URL factories, unknown helper names, HTTP scheme downgrades, GitHub lookalike hostnames, mismatched REST API routes, missing source files and syntactically invalid files.
- Strictly checks global Worker feature-flag subresource path is constructed via `_variable_collection_url(config)` followed by a `FEATURE_FLAG_NAME` **percent-encoded with `quote(..., safe="")`**. The Worker remains deactivated and no state is changed.
- Rejects explicitly enabled `allow_redirects=True` or caller-driven redirection configuration at any of the 21 calls. **Currently omitted redirect settings remain an explicitly unverified residual risk**; this Draft does not change behavior of legacy GET/PUT/PATCH calls.
- Reports counts and source identifiers only, never prints credentials, request bodies or real prompts. Returns all operational authority flags `False`, including `github_writes_authorized`, `network_called` and `safe_to_deploy`.
- Uses the Python AST only, does not import/execute the inspected production modules or create real HTTP connections.

## Adversarial tests

`tests/test_atlasquant_aion_v2_legacy_github_destination_source_review.py` injects fake network writes and malicious URL rewrites into disposable temporary Python source trees: OpenAI host substitution, `api.github.com.evil.invalid` homograph-style suffix, plain HTTP, repo query-route changes, missing `/contents/`, direct user-controlled URL, duplicate URL reassignment, duplicate or missing send, call to arbitrary URL helper, mutable redirect toggle, rewritten worker Actions flag origin, absent percent encoding and duplicate helper. Also asserts the **full exact 21-callsite current branch** passes and that no inspection executes injected code. Windows and Linux GitHub Actions run the new URL provenance checker as a separate fail-closed step, the mutation tests, and the inherited #1147 paid provider locks/577-file AST/TLS/owner/witness security suites.

## What passing does NOT establish

- The first HTTPS origin string is fixed at `api.github.com` in the inspected source, but **dynamic repo and path interpolation are NOT independently validated**, and query/fragment/userinfo path injection protection is not proven. Repo/path values may still be supplied from configuration. Auth token scope, GitHub branch controls and target file permissions need their own audit.
- The scanner is not live DNS/TLS resolution or runtime network interception. Defaults of Python Requests may follow redirects unless separately disabled; redirect handling, proxy behavior, user credential leakage, endpoint pinning and retries are **NOT certified**. Vendor domain string checks do not establish that a call is safe or free.
- Source AST cannot prove all data-flow or reachability paths. It does not scan JavaScript/TypeScript, shell/curl/subprocess, dynamic imports, compiled extensions, third-party SDK internals or malicious in-process code alteration. It does not implement independently protected monotonic remote CAS or owner enrollment.
- The 21 calls are **existing operational GitHub writes** — documenting their origins is **not authorizing them**, invoking them, approving Worker activation or installing a new egress policy. The source-only audit does not alter deployed `main`.
- Model/TTS hard-deny flags on #1146/#1147 remain true on this stacked Draft. No real billable provider activity can be enabled by the checker.

**Production remains NO-GO:** Requires separately enrolled HUMAN_OWNER/FIDO2 key custody, genuine independently authenticated IdP session, noncolluding remote witness roots and monotonic CAS, real budget reserve and vendor usage/billing reconciliation, and explicit approval for real infra spend, merge and deploy. Budget target R$200/month, no unauthorized external service, owner PC or secrets.
