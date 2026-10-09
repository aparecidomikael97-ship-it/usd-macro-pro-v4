# AION V2 — authenticated GitHub GET preflight URL guard and redirect suppression

**9 October 2026. Stacked Draft above #1149. Strict NO-GO for real paid models, owner-key enrollment and operational deployment.**

## Gap closed

#1149 made all 21 *write* HTTP requests to GitHub Contents/Actions API validate the fully interpolated REST URL locally and pass `allow_redirects=False`. However prior credential-bearing **`requests.get`** reads were still using Requests' default redirect behavior, including when they fetch the SHA used for a subsequent GitHub write. A GitHub API redirect could unintentionally cause a credential-bearing request to another URL, or a misconfigured dynamic URL could bypass the source's assumed origin. We make **no claim that such credential leakage has actually occurred**.

The following **27 existing authenticated GitHub GETs across 12 existing Python modules** are now subject to the same fixed HTTPS GitHub URL validator and to explicit `allow_redirects=False` at the Requests callsite:

- AION memory, flight recorder, research evidence, shadow persistence: 1 each.
- Autopilot V107: 2 (read + compare-before-write).
- Currency News V1061 / V1062 / V107: 3 each.
- Market Map V10: 1.
- Master Panel V102: 2.
- Twelve Data budget V1108: 1 GitHub budget-state read.
- USD Macro Pro Cloud: 9 GitHub content/history/config/scanner reads, including SHA-read-before-write.

**Important distinction:** unrelated public/vendor market data requests to Twelve Data, NewsAPI, Google RSS, FRED, translation and EODHD are NOT modified. Those are a separate provider egress/security review; no paid or public API call is made here. The Global Worker activation code's four GitHub writes remain write-protected from #1149, and there were no direct `requests.get` sites in those two modules in this inventory.

## Actual source changes

- Reuse the exact allowlisted `https://api.github.com/repos/OWNER/REPO/contents/PATH` or `/actions/variables[/NAME]` grammar through newly named `guard_github_token_read_destination(url)`, implemented as a call to the hardened #1149 URL guard. It is stdlib-only, no network, and rejects off-origin domains, userinfo, port changes, percent-encoded ambiguities, query, fragment, dot-traversal, malformed/unbounded path segments and suspicious control/Unicode syntax.
- At each of the **27 actual `requests.get` callsites**, wrap only its first URL argument in `guard_github_token_read_destination(...)` and add explicit `allow_redirects=False` while preserving the original `headers`, `params={"ref":...}`, `timeout`, status and return contract. HTTP Requests' normal automatic 3xx redirect chasing is disabled for these **specific GET requests**.
- New `atlasquant_aion_v2_github_token_read_no_redirect_audit.py` inventories all 27 exact file/function/GET callsites. This fail-closed AST CI gate requires import from the pinned guard module, exactly one wrapped URL, one literal `allow_redirects=False`, and original explicit header/ref/timeout arguments. It finds new `requests.get(...params={"ref":...})` functions in these audited modules and fails until reviewed. It never imports inspected modules or makes network requests.
- Adversarial mutation tests alter source code, remove or replace guard/import/redirect controls, duplicate GET calls, inject new ref-scoped sites and use malicious hosts/path encodings; validation must fail. The real full-tree suite and prior #1149 two billable model/TTS POST fixed-denies remain prerequisites.

## Scope / residual risks

- This is **real source-level request protection** for the 27 GitHub token-bearing `requests.get` calls, not a proof of real DNS/TLS/certificate pinning, origin of `requests` module or resistance to malicious monkeypatches/proxies. It does not guarantee credentials in existing repository token configuration are scoped minimally. Calling the helper alone never issues HTTP; runtime behavior depends on the existing Requests client.
- A redirection with HTTP 3xx will no longer be automatically followed by Requests at these callsites; existing caller status handling may fail on a non-200/404 response. Some callers handle failures by returning a safe default; that behavior is unchanged. The scan does not assert the 3xx status is independently checked everywhere.
- Source inventory is not a full static proof against arbitrary `Session.get`/dynamic imports, third-party SDKs, JS/TS or shell/curl. The quoted counts apply to **the checked-out audited Python locations**, not all possible runtime network traffic. Follow-up: branch/repository configuration custody, credential/proxy protections, dynamic-language egress and external trust enrollment.
- No real owner IdP/FIDO2 enrollment, noncolluding external witness roots, monotonic remote once-only CAS, actual FinOps reserve, vendor POST idempotency/invoice or UNKNOWN_OUTCOME reconciliation. Hard-deny for paid text and TTS calls remains enabled on stacked Draft and cannot be treated as unlocked by green CI.

**No real provider/OpenAI call, third-party API, GitHub write, Global Worker activation, paid usage, real secrets, owner PC/TPM, cloud provisioning, merge or deploy.** Frozen Core V1/`main` untouched; temporary infrastructure cost ceiling R$200/month and owner approval remain mandatory.
