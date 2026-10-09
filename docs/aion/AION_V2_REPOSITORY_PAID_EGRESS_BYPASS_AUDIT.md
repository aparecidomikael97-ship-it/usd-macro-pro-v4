# AION V2 — real two-path paid AI egress audit and deny (Draft NO-GO)

**9 October 2026. Draft PR stacked on #1146. No changes to deployed main/Core V1.**

## Critical finding confirmed by whole-tree CI

The initial AST inventory of this repository detected an **additional real billable OpenAI POST** that bypassed the text model adapter's #1146 hard deny:

- **Text model provider:** `atlasquant_aion_provider.py::execute_openai_answer` invokes `client.post("https://api.openai.com/v1/responses")`. It is already source-fixed `_PAID_MODEL_DISPATCH_HARD_DENY=True` on this Draft branch, with the gate before HTTP header/session/POST and no environment toggle.
- **Neural TTS:** `atlasquant_neural_tts.py::generate_neural_speech` invokes **`requests.post("https://api.openai.com/v1/audio/speech")`**. Before this Draft it accepted a supplied API key and validated voice/transcript but had **no independent owner/trust/budget/remote one-shot admission**, and was not covered by the text-model lock. This Draft adds independent source-fixed `_PAID_TTS_DISPATCH_HARD_DENY=True` checked before any audio POST, raising a controlled runtime error without connecting. The UI already displays the transcript and does not automatically fall back to a device voice.
- The pending source and UI behavior remain **Draft only**, not on main or deployed. The TTS voice identity (e.g. model/voice/intonation) is unchanged. This blocks new real paid audio rather than changing the approved voice design.

This finding is a **substantive safety gap**, not a mere missing test. **No real external provider calls** or actual billing have been made to verify it; the code path and its endpoint were verified from repository source.

## Source inspection protocol

`atlasquant_aion_v2_repository_paid_egress_static_audit.py` is an AST-only, stdlib script over the checked-out production Python tree. It does **not import or execute** inspected files and therefore cannot invoke a provider. It identifies:
- Generic `.post` sends, network-origin `.request`, `requests/httpx/urllib3` PUT/PATCH/DELETE/send, direct urllib urlopen, known SDK constructors/creation, OpenAI/Anthropic/Gemini chat/responses/messages/generate content invocation.
- Exact source guards and their order/return for the **two actual vendor paid POST callsites**. Both source locks must remain exact module-scope literal True with one unconditional fail-closed return/raise before the only allowed `POST`; missing, duplicate, changed, moved or permissive guards fail CI.
- An explicit, narrowly pinned baseline of **21 other existing write operations** (mostly GitHub checkpoint persistence, feature flags, snapshots), preserving exact module/function/method and requiring that each appear once. These writes are **not certified as vendor-safe** from source AST, so the scanner reports them as *preexisting other network writes requiring independent audit*. Unknown additional POST/PUT/PATCH sites or a newly added duplicate of a baseline site **fail**.
- Two `requests.post` methods in `atlasquant_aion_global_worker_activation.py` were classified as **GitHub repository Actions variable operations**, not AI inference: both target `_variable_collection_url(config)`, which currently generates `https://api.github.com/repos/{config.repo}/actions/variables`. They remain in the narrow other-network baseline, not exempted from review of Worker activation. This Draft does not invoke, enable or deploy any Worker.

The scanner's output is designed to contain only relative source path/line/sink kind/count and NO request body, bearer token, secrets or prompt text. Any unknown callsite, missing locked POST, mutation of the source guard, missing baseline write or malformed production source makes the CI gate fail.

## New security tests

- Static mutation tests against temporary mini-repositories: new `requests.post`, `requests.request` alias, raw urllib, httpx, vendor SDK, nested model invocation, missing/duplicated/disabled/hollowed source locks, model `called=True`, untrusted third POST site, changed TTS gate, invalid Python source. The scanner must **not execute/import** malicious fixture source.
- `tests/test_atlasquant_neural_tts_paid_post_hard_deny_v2.py`: calls the actual audio entrypoint with a fake noncredential API key and approved-looking model/voice configurations; traps `requests.post` and `requests.sessions.Session.send`. Even with forged environment hints, speech generation fails before network. Empty/malformed text, missing key, alternate endpoint still fail in existing earlier preflights; the fixed voice identity and cache key remain offline.
- Both Windows and Ubuntu jobs run source scan as a fail-closed independent CLI gate, new test suites and all inherited #1146 owner/session/witness, provider full-request SHA, local HTTP/TLS and V1 provider suites. **No real third-party service contacted.**

## Explicit limitations

This is a **static Python** audit, **not complete repository egress isolation**. It does not analyze JS/TS, shell scripts, subprocess `curl`, dynamic imports, reflection, monkeypatches, custom transport compiled extensions, third-party package internals, malicious source modifications after CI, or live HTTPS/proxies/hosts. The 21 preexisting network writes may still carry operational risk and need a separate destination/boundary review; they are not paid AI requests based on currently inspected source, but the AST cannot guarantee immutable destinations.

The new hard denies are **not merged/deployed**, so they DO NOT protect a live main installation yet. Neither source lock is a substitute for enrolled keys, real owner presence, independent IdP, two separately protected monotonic witness domains, durable globally fenced one-shot execution, trusted budget reservations, vendor usage/invoice reconciliation or owner consent. A possible external POST whose reply is lost remains UNKNOWN_OUTCOME; never automatically replay.

**No real API, external provider POST/GET, cloud service, new credential, FIDO2/TPM, owner's Windows computer, paid inference/TTS, expenses, merge or deploy performed.** Future infrastructure target cap remains R$200/month, requiring explicit approval.
