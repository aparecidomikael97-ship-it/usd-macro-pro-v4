# AION V2 — GitHub write URL validation + redirects disabled at 21 legacy callsites

**2026-10-09 — Draft stacked on #1148 → #1147 → #1146. STRICT NO-GO for paid AI, owner enrollment and production deployment.**

## What changed from prior static-only provenance scan

#1148's review showed 21 pre-existing network-mutating GitHub API calls (17 `/repos/OWNER/REPO/contents/PATH` and 4 `/repos/OWNER/REPO/actions/variables[/NAME]`), with HTTPS GitHub origin strings rooted in static Python source. But **that proof did not examine the actual final interpolated URL or disable redirects**. Paths and repository names could be derived from configurations, and `requests` may follow redirects by default.

This stacked Draft changes **actual HTTP callsite source**, not merely a report:

- `atlasquant_aion_v2_github_write_url_guard.py` adds a **stdlib-only, no-network** `guard_github_write_destination(url)`. It takes an already reconstructed URL and returns the SAME string only when all constraints are met. Non-string and oversized URLs fail; it requires exact `https://api.github.com` scheme/host, no userinfo, alternate port, percent-encoding, query, fragment, control characters, whitespace, Unicode, backslash, repeated slash, `.`/`..` segments, or unknown REST path. Repository owner/name and subpath segments must be bounded ASCII literals from a narrow set `[A-Za-z0-9_.-]`. Only existing GitHub `/contents/...` file writes and `/actions/variables[/NAME]` variable operations are accepted; all others throw `ValueError` **before the requests call**.
- Every one of the **21 existing** `requests.put/post/patch` expressions now wraps its **first URL argument** in `guard_github_write_destination(...)` and supplies `allow_redirects=False` explicitly. The four Global Worker feature-flag operations are covered too; no Worker activation or remote API execution is performed by this Draft.
- The previous `atlasquant_aion_v2_legacy_github_destination_source_review.py` now additionally rejects a real checked-out callsite lacking the exact guard call/import or explicit single `allow_redirects=False`. The existing #1148 mutation-fixture tests can still review their original *static source* scenario independently; **the full actual tree and new mandatory mutation tests must enforce both runtime guards**. Production scanner and policy cannot be relaxed simply by providing `require_runtime_guards=False` to the existing CLI: the default full-tree mode enforces it. This is an audit test, not operational approval.
- `tests/test_atlasquant_aion_v2_github_write_url_runtime_guard_v1.py` exhaustively tests valid and malicious URL inputs, fake GitHub hostname, OpenAI origin, scheme/port/userinfo, encoding/traversal, control and Unicode characters, route impersonation, malformed repo/path, no sockets, and source mutations removing one or both protections.

## Security and compatibility boundaries

This is a **real in-process URL syntax check for 21 already existing GitHub write paths**, not merely static analysis. It reduces accidental and simple injection-driven sends to non-GitHub hosts. `allow_redirects=False` prevents **Requests' normal automatic HTTP redirection on these 21 write calls**, including redirects to a second hostname. There is **no new capability to issue writes**; existing GitHub tokens, existing application workflows, budgets, branch gating and purpose remain unchanged. Invalid historic repo/path configurations may now fail before requests rather than silently send HTTP.

The explicit runtime guard DOES NOT guarantee runtime transport cannot be bypassed by monkeypatching Python, malicious environment proxy settings or modified Requests installed package. No live DNS/TLS/certificate pinning was performed. **Prior GET reads used to prepare some writes may still follow redirects**, which needs a later separate review to protect credentials on reads. Additional languages (JS/TS), subprocess curl, code-generating imports and remote dependency internals remain outside this Python scan.

No claim of independent enrolled HUMAN_OWNER/FIDO2 identity, independently verified IdP session, noncolluding protected witness roots, remote monotonic CAS, vendor billing/UNKNOWN_OUTCOME reconciliation, global once-only paid dispatch or production readiness. All provider text/TTS paid POST source hard-denies inherited from #1146/#1147 remain `True`.

## CI evidence requirements

Windows + Ubuntu GitHub Actions perform:
1. Compile the guard, updated source auditor, all 14 changed legacy modules and mutation tests.
2. Run source auditor on **the full actual tree** to demand all 21 URL wrapper imports and 21 explicit no-redirect writes.
3. Run the earlier 578+ Python-file provider/TTS egress scanner to verify the two paid POST source gates remain locked.
4. Run all new URL cases and source attack mutations, previous static destination audit tests and inherited AION owner/session/witness, text/TTS/provider/HTTP/TLS no-execution suites.

Do not call this green until exact-HEAD Windows and Linux complete.

**No merge/deploy, Worker flag mutation, production API token, real paid model/voice call, real GitHub writes, owner PC/TPM or spending. Frozen Core V1 and main untouched; interim infrastructure cost target R$200/month remains approval-gated.**
