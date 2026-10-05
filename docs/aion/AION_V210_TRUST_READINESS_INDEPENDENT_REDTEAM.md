# AION V2.10 — Independent trust-readiness red-team

## Baseline and scope

Repository: aparecidomikael97-ship-it/usd-macro-pro-v4.
Initial SHA: `725956c7bd44afcde2ccd04721e70112159f6a19`.
Branch: `agent/codex-aion-v210-trust-readiness-redteam-20261004`.
PR base: `integration/aion-core-v210-trust-root-readiness-20261004` (Draft #596 head); no main rebase.

This audit tests the existing absence-of-trust-root contract. It does not implement cryptography, a collector, a verifier, key loading, persistence, or a new authority.

## Canonical contract and flow

Caller claims / loaded canonical evidence -> `build_core_health_evidence` / `build_loaded_runtime_health_evidence` -> health snapshot and consistency view -> Master Status Board -> Admin renderer.

At the adapter, Status Board, and now the Admin consistency renderer, `provenance_trust_readiness_view` produces the same canonical blocked preflight. Its optional payload is deliberately not inspected, iterated, coerced, or traversed. No payload fields configure a trust root. Each invocation creates an independent result and blocker list.

`state=BLOCKED`; `origin_authenticated=False`; `snapshot_signed=False`; `signature_verification_available=False`; `trust_root_configured=False`; `signing_scheme_configured=False`; `verifier_policy_configured=False`; `replay_protection_configured=False`; `rotation_revocation_policy_configured=False`; `execution_allowed=False`.

Canonical blockers, in order:

1. TRUST_ROOT_NOT_CONFIGURED
2. SIGNATURE_SCHEME_NOT_CONFIGURED
3. VERIFIER_POLICY_NOT_CONFIGURED
4. REPLAY_PROTECTION_NOT_CONFIGURED
5. ROTATION_REVOCATION_POLICY_NOT_CONFIGURED

SHA-256, snapshot_digest, evidence_epoch and identity_digest are consistency fingerprints, not signatures. A source_ref is not an authenticated origin. Health/consistency CONFIRMED, snapshot_complete=True, checkpoint CONFIRMED, recovery CONFIRMED, memory VALIDATED, approval=True and authenticated_admin=True do not imply trust READY. Health observation and CONFIRMED health never authorize execution.

## Reproduced bug and minimum patch

`test_forged_readiness_board_cannot_hide_blockers_in_actual_admin_renderer` failed on the exact baseline: a prebuilt board containing `state=READY` and an empty blocker list caused `_render_core_consistency_truth` to display `provenance_trust=READY` and hide canonical blockers. Origin/signature flags still displayed False. The normal server-built board and canonical preflight remained BLOCKED.

This is a presentation/truth defense bug at the renderer accepting a forged prebuilt board, not a demonstrated cryptographic authentication bypass or an established remote exploit.

Reproduction checkpoint: `5d15f95d7468457c5777dcfe0accc99232c0ad21`, committed before the patch. Initial executable suite: 1 failed, 399 passed. The minimum production patch adds the existing canonical preflight import and derives renderer readiness from it instead of echoing board readiness. Health and consistency meaning are unchanged. No second authority was introduced.

## Executable attack coverage

New suite: `test_atlasquant_aion_v210_trust_readiness_independent_redteam.py`, 22 test functions, 552 executable parametrized cases.

- Nine flags x hostile/scalar claim types; bool/int/string, lists/tuples, dict subclass/custom Mapping, Decimal/Fraction/IntEnum, NaN/Infinity, bytes, exception-raising coercion/access hooks.
- Nested claims at root, runtime, health, provenance, consistency, snapshot, checkpoint, recovery, memory, mission, system_context, approval, signature and readiness; forged claims with and without snapshot rehashing.
- Source names, Unicode confusable, case/whitespace, NUL, URLs and path-like labels; none grants origin authentication.
- Real Admin boundary uses its existing loader budget, replacing/ignoring caller claims; no new loader.
- Removed, reversed, duplicated and substituted blockers; future/unknown/missing schema, extra fields; nonce/timestamp/signer/key/signature/anchor/attestation labels.
- Returned-object mutation, recycling, deepcopy, order reversal and JSON roundtrip; 10,000 repeated calls and 20 parallel calls with independent blocker lists.
- Million-element list, 100,000-entry mapping, 1.8-million-character string, 10,000-level mapping and cycle; 1,000 preflights each. Fixed output under 4 KiB; preflight does not traverse payload. Measured times are observations, not hardware-independent latency thresholds.
- Existing local executor rejects trust context as a substitute for USER role, explicit authentication and approval. Provider feature/approval gates reject a dict instead of exact True; the budget-context case blocks for missing cost configuration before network access. That case does not certify every provider budget path.
- Maximum technical fixture simultaneously shows health CONFIRMED, consistency CONFIRMED, snapshot_complete=True, snapshot_atomic=False, origin_authenticated=False, snapshot_signed=False and provenance_trust=BLOCKED. Trust blockage neither degrades Core integrity falsely nor disappears behind green technical health.
- Output excludes actual keys, signatures, secrets, credentials, tokens and trust-anchor material.

## Side-effect proof and limits

Fixtures and imports are prepared before instrumentation. With guards active, the resident evidence adapter -> snapshot/Status Board -> both Admin status renderers chain records zero attempted builtins.open/Path reads or writes, rename/replace/mkdir/unlink, socket, subprocess, HTTP, journal store construction/recovery, taskgraph persistence/recovery, provider invocation, checkpoint restore, worker arming/approval, feature activation or staged arming persistence. Input/returned-object independence tests also verify no payload mutation.

These are executable local guards for the tested paths, not an OS-wide syscall audit. Real Admin loader-budget tests retain the existing runtime loader behavior; they do not claim the complete Admin page performs zero reads. Bounds prove the preflight ignores hostile payloads, not that all arbitrary malformed inputs to every domain validator have constant cost. Concurrency proof covers the stateless preflight, not every Core runtime component. No real provider, billing, broker, worker, recovery, external execution or cryptographic verification is exercised.

There is still no trust root, signing scheme, verifier, replay-protection or rotation/revocation policy. Real authenticated provenance, signed snapshots, anti-replay, revocation, hostile authenticated signer behavior and distributed runtime guarantees are NOT proved. Absent or noncanonical domain evidence remains UNKNOWN; the audit adds no evidence wiring to eliminate UNKNOWN. The maximum fixture is synthetic canonical test evidence, not a statement about production runtime health.

## Validation

Isolated new suite: 552 passed in 12.79 s. Baseline reproduction: 1 failed, 399 passed. Immediately patched checkpoint plus existing V2.10 suite: 451 passed (earlier 400-case version plus 51 existing cases). Final related block: 1,402 passed, 2 subtests passed in 27.97 s (new V2.10, existing V2.10, V2.9, V2.8 cross-contract/global snapshot, V2.6 adapter/wiring, observability, Status Board, Admin runtime and runtime bridge). Broad available AION/Core regression: 198 test files; 4,558 passed, 4 skipped, 737 subtests passed in 180.71 s. All four skips are existing Windows symlink limitations (developer intelligence, journal store, journal governance and V2.7 durable crash isolation). No failed tests and no relaxed tests.

No workflows, Trader interface, provider, billing, executor, approvals, stores, worker/feature production code or cryptographic architecture changed. No merge or deploy. ZERO real provider, billing, paid API, real order, external execution, worker arm, auto-repair or unproved cryptographic trust claim. GitHub push/Draft PR publication is delivery activity, not runtime communication.
