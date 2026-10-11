# AION V2 — authenticated GitHub write HTTP response contract

9 October 2026. **Reference hardening on stacked Draft #1152, not merged, not deployed. HARD NO-GO for production.**

## Why this is needed
The 21 preexisting GitHub HTTP mutations in #1149 already validate the outgoing HTTPS URL and disable automatic redirects. But ordinary Requests `raise_for_status()` does not reject **3xx**, and returns without an error for unexpected 2xx such as **204 on repository file PUT**, potentially causing a legacy caller to report successful write incorrectly. No real attack or credential leak is alleged.

### Applied to actual application source
Each of **21 existing requests.put/post/patch callsites across 14 modules** now immediately wraps its response with `reject_github_write_unexpected_status(requests.<method>(...), "<mode>")`, before original status checks, `raise_for_status()` and response parsing. There are no new HTTP sends.

- Contents PUT (17): accept 200/201 as possible accepted statuses; preserve legacy 409/422 conflict handling (these **do not** signal success).
- Actions variables POST (2): accept only documented 201.
- Actions variables PATCH (2): accept 204; preserve 404 for the existing explicit 'create disabled flag if missing' rollback branch, otherwise legacy exception handling applies.
- All 3xx, ambiguous success statuses and other error codes generate a distinct `GitHubWriteOutcomeUnconfirmedError(RuntimeError)` with `GITHUB_WRITE_OUTCOME_NOT_CONFIRMED_NO_RETRY_AUTHORITY` without claiming the remote write did not occur or automatically retrying.

Status code contracts cross-checked against GitHub REST documentation: repository Contents API PUT (200, 201, 409, 422) and Actions repository variables POST 201 / PATCH 204. These rules do **not** certify the remote side effect, real identity or a durable receipt; a fabricated 201 still requires provenance and read-after-write for actual certification.

Mandatory AST audit checks each exact legacy write site plus pinned wrapper and operation literal. Adversarial tests include spoofed 302 commit JSON, wrong 2xx statuses, mixed-mode status, 404 rollback preservation, import tamper, duplicate write, and no-network mock. Windows and Linux CI inherits 28 GET guard suite, prior 21 write URL guard, Python paid POST egress locks and full owner/witness/TLS reference tests.

## Important residual limitations
This does NOT establish remote write persistence, cross-database CAS, true owner enrollment, independent witnesses, token scoping, proxy/TLS/source integrity, billing reconciliation, real physical sandbox proof or permission to deploy. Status errors after a send may be **UNKNOWN_OUTCOME** — never assume safe retry or auto-refund based only on a local exception. Some legacy code still retries 409/422 exactly as before; a separate future review of automatic retry and actual preconditions is required. No real GitHub application mutation, token, owner PC or paid provider call was performed. Core V1/main remain untouched, #1117 remains HARD NO-GO.

**Exception taxonomy correction:** A first local CI run (Ubuntu/Windows suite under #1152) exposed an unrelated malformed workflow compile command, fixed in a subsequent commit. A second review noticed the three legacy evidence/history/shadow stores interpret **all ValueError** as remote JSON corruption. The new write-response boundary therefore raises a dedicated **RuntimeError subclass**, not ValueError, so an uncertain remote HTTP write cannot be falsely reported as `CORRUPT_REMOTE`. This is a semantic reporting fix; it does not infer the remote side effect or authorize a retry.
