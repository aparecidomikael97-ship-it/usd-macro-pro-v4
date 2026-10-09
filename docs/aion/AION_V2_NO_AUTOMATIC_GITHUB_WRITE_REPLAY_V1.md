# AION V2 — one GitHub write attempt per invocation (no auto replay)

9 October 2026. Source-only stacked Draft following #1153; **not merged or deployed**.

## Concrete finding
Three real legacy data/evidence stores in #1153 still automatically replayed a GitHub Contents PUT on a reported 409. The real `autopilot_v107.gh_put_bytes` allowed up to three successive writes. A remote status alone is not trusted authorization for another write. Both are code-level gaps, not evidence of an actual duplicate.

## Applied to four real production write functions
- Flight Recorder `persist_records`; Research Evidence `persist_research_evidence`; Shadow Mode `persist_shadow_samples`: **one** existing guarded `requests.put` maximum per function call regardless of the old `retry_conflict_once` argument (retained for caller compatibility). Reported HTTP 409 now returns `CONFLICT` / `REPORTED_CAS_CONFLICT` / `reconciliation_required=True` / `safe_to_retry=False` without replay. 422 remains `VALIDATION_REJECTED` / `REPORTED_HTTP_422` without replay. Ambiguous timeout or 302 returns `UNKNOWN_OUTCOME`; no automatic resend.
- Autopilot `gh_put_bytes`: previous three-attempt loop replaced with exactly one guarded GET followed by at most one guarded PUT. On 409/422 returns a distinct `REPORTED_GITHUB_HTTP_*_NO_AUTORETRY_RECONCILE_FIRST`; on exception after attempted PUT returns `UNKNOWN_GITHUB_WRITE_OUTCOME_RECONCILE_NO_RETRY:<ExceptionType>`; before PUT returns `PRE_WRITE_GITHUB_READ_OR_VALIDATION_FAILED:<ExceptionType>`. Existing tuple return signature preserved, and exception messages/credentials are not echoed.
- No-network tests run the AST-extracted **actual** `gh_put_bytes` function in an isolated namespace with mocked requests (never importing live Autopilot or starting its tick). They assert exactly one PUT for 409, 422, 302, timeout and successful 200, zero PUT for failed GET, URL/status guard + no-redirect parameters. AST checks all three evidence writers pin `attempts=1`. Inherited tests separately exercise those real modules. Ubuntu and Windows CI inherits 21 write and 28 GET guarding and paid provider POST denials.

## Remaining strict limits
One HTTP PUT per **invocation** is not end-to-end idempotency. A caller/worker could call the same function again or write with another client, and 200/201 does not independently establish a durable, provenance-authenticated receipt; real owner trust, external witness, storage CAS, origin/URL/TLS validation and billing reconciliation still require physical certification. Main/Core V1 not touched; no real application API writes or paid dispatches, secrets/keys, install, deploy, Worker activation or cost. Checkpoint Master issue #1117 remains HARD NO-GO.
