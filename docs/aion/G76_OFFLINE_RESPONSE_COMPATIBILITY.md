# G76 LAB offline response compatibility

Date: 2026-10-25. Workspace: `C:\Users\apare\AtlasQuant-G76-Compatibility-LAB-20261025`.
Base HEAD: `cee950357ee6d6afe3948dedd2e29637fb81632b` (G75).
Existing branch: `lab/aion-p0-external-gate-compatibility-g76-20261025`.
No branch creation, commit, push, merge, deploy, Worker, install or real network.
Only synthetic fixture values were used; no credentials were read.

**P0 = 0/6. HARD NO-GO. ZERO_AUTO_RESEND.** Passing compatibility tests
establishes offline behavior and containment only. It does not establish trusted
external custody, release readiness, provider availability or first-send authority.

## Baseline and original intent

The unmodified baseline ran 23 historical tests under requests/socket guards:
2 failures, 1 error, all caused by intended G75 containment.

- `test_atlasquant_aion_provider.py:221` (baseline):
  `test_successful_response_is_unverified_model_output_and_no_action` failed
  at line 240 because `called` was False. Its meaningful response contract is
  JSON text extraction, unverified model truth state, no actions/orders, and
  secret exclusion. Those assertions remain; response ID and token usage are
  now checked too. Model selection is checked offline.
- `test_atlasquant_voice_profile.py:75` (baseline):
  `test_generation_uses_fixed_neural_model_voice_and_ptbr_instructions` errored
  at line 81 before the mocked POST. Its fixed model, voice, exact transcript,
  Portuguese instructions, MP3 payload and exact audio bytes remain checked
  through pure data construction and response validation.
- `test_atlasquant_voice_profile.py:102` (baseline):
  `test_provider_error_is_sanitized` failed at line 108 because the gate reason
  replaced the expected HTTP 401. HTTP 401 sanitization is now tested on an
  existing response, including exclusion of sensitive provider content/secrets.

Each of these three historical tests additionally checks the G75 blocked entry
point. Historical assertions that a POST occurred cannot truthfully describe G75
and remain replaced with no-send assertions. Follow-up review
`01a175e9-f26b-7273-8b57-37f46b2095f8` identified three LOW coverage gaps
(no high/medium security findings). Exact credential headers are now tested as
pure offline data using FAKE keys only, without reviving a transport route.

## Compatibility contract

`parse_openai_response(response, config=..., model=..., estimate=...)` interprets
an already supplied response. It retains JSON/object/empty-output distinctions,
HTTP error sanitization, output extraction, usage/cost, response ID and
MODEL_OUTPUT_UNVERIFIED semantics. Every offline result has `called=False`;
ANSWER_READY means parsed content only, never an attested provider call or
permission to execute. The existing transport path marks `called=True` only
after its POST, which remains unreachable under the unchanged G75 gate.

`parse_neural_speech_response(response)` retains HTTP 200, nonempty audio and
content-type validation exactly: audio/*, octet-stream and absent content-type
are accepted as before. HTTP errors never expose or read the response body.
It returns only existing bytes and performs no generation or playback.

`build_neural_speech_payload(text, config=...)` extracts existing payload data
construction and validation. It contains no credentials or transport. It exists
to preserve the historical fixed-voice/exact-transcript assertions offline.

`_build_openai_headers(api_key)` and `_build_neural_speech_headers(api_key)`
return exactly the historical two headers: `Authorization: Bearer <key>` and
`Content-Type: application/json`. Their hypothetical transport callers use them
only after the unchanged always-deny G75 gate. Text still passes `cfg.api_key`;
TTS still passes the existing stripped `secret`, so normalization is unchanged.
The dictionaries have no authority semantics; mutating or repeatedly constructing
them cannot authorize a send. Tests use FAKE keys only and confirm blocked calls
after construction and mutation. No gate bypass is used to test headers.

TTS payload tests assert the exact allowed key set
`{'model','voice','input','instructions','response_format','speed'}`, exact values,
default speed `0.96`, configured speed `1.25`, and exclusion of the fake secret.
The workflow path filters now include `atlasquant_external_first_send_gate.py`.

These helpers have no session, environment switch, reservation callback or send
authority argument. Fake response objects are fixtures, never transports. Their
methods/properties must be inert response accessors, as with any response parser;
this is not a sandbox for arbitrary executable response objects.
Production edits are pure helper extraction and delegation only. G75 gate and
preflight checks are unchanged. No helper result is consumed as gate authority.

## Verification

All new G76 tests patch requests and socket entry points to raise on unexpected
network, and assert those guards were never called. Historical affected classes
also have requests/socket guards. Fake caller sessions remain uncalled.
New coverage checks successful JSON and fallback output_text; usage/cost;
invalid JSON, non-object and empty output; sanitized text/audio HTTP 401;
exact audio bytes; accepted headers; rejected empty/wrong-type audio; and
repeated calls after offline parsing/payload construction still blocked.

Executed successfully:

```powershell
python -B -m unittest -q labs.a190.test_g74_operational_first_send_red_lab labs.a190.test_g75_external_first_send_lab labs.a190.test_g76_offline_response_compatibility_lab test_atlasquant_aion_provider test_atlasquant_voice_profile
```

50 tests, 0 failures, 0 errors: G74 4, G75 12, G76 11, provider 15, voice 8.
The follow-up run loaded these same five modules through `unittest` with an
empty patched environment and outer forbidden guards on
`requests.sessions.Session.request`, `requests.post`, `requests.request`,
`socket.socket.connect`, `socket.socket.connect_ex`, and
`socket.create_connection` for the entire run (including imports). Existing
per-test guards and synthetic transport mocks remain in place. No dependencies
were installed and no network or paid API was called.
The G74 RED characterization tests pass under containment; no operational P0
closure is inferred. `git diff --check` also passes.

## Exact changed paths

- `atlasquant_aion_provider.py`
- `atlasquant_neural_tts.py`
- `test_atlasquant_aion_provider.py`
- `test_atlasquant_voice_profile.py`
- `labs/a190/test_g76_offline_response_compatibility_lab.py`
- `docs/aion/G76_OFFLINE_RESPONSE_COMPATIBILITY.md`
- `.github/workflows/aion-g76-offline-response-compatibility-lab.yml`
