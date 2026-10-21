# AION P0 — Strict Git Content SHA before Checkpoint Master recovery

**2026-10-21 · LAB-only Draft; no restore, deploy, merge, GitHub runtime write, Worker or provider effect.**

## Fault reproduced before patch

`recovery_preflight(current_runtime,candidate)` previously checked `current.sha` only with `str(...).strip()` and a nonempty test. A forged object such as `{"status":"CONFIRMED","sha":"not-a-github-blob","checkpoint":...}` could pass recovery eligibility; `restore_checkpoint_revision(...,approved=True)` would then proceed to `load_checkpoint_revision` despite an unusable GitHub Contents API expected blob SHA. Boolean and numeric SHA fields were also stringified and accepted. Non-mapping envelopes (for example int) raised `TypeError` at `dict(value)` rather than responding fail-closed.

**Real RED-first evidence:** [GitHub Actions #39648785719](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39648785719) on SHA `b430eb0beaf979cbc59423feaf2647924216418d` — **12 FAIL + 2 ERROR in 17 tests on Ubuntu**, including proof that invalid SHA led to calling the history readback stub. Tests use actual `recovery_preflight` and `restore_checkpoint_revision` functions, mocked readback/write endpoints, genuine local checkpoint fixtures. No real GitHub runtime call or state mutation.

## Narrow real-code correction

`atlasquant_aion_recovery.py` now:
- Denies non-mapping `current_runtime` and `candidate` with `allowed=false` and no exception.
- Requires that the current SHA be a real Python `str` matching **exactly 40 hexadecimal characters** (`re.fullmatch`). Truncated, overlong, prefixed, malformed, integer and bool SHAs are denied *before* historical readback or conditional save.
- Preserves a legitimate uppercase/lowercase Git blob SHA; keeps the intended ability to review a different historical checkpoint even when the current checkpoint has a repairable local integrity MISMATCH.
- Does not change selected historical revision parsing, explicit `approved=True` requirement, rebound checksum, GitHub conditional expected-SHA write, read-after-write confirmation or the NO-AUTO-RESTORE/NO-AUTO-RETRY posture.

A rejected SHA is not proof of any external effect. A syntactically valid 40-hex SHA is **only** structurally eligible and must still match the live GitHub runtime value during the conditional transaction. This patch is not an independent nonce/head/receipt witness and does not authenticate HUMAN_OWNER.

## Verification

New `tests/test_aion_p0_recovery_preflight_strict_git_sha_lab.py` contains 17 checks, including malformed type, current blob SHA shape, unchanged normal recovery, selected digest mismatch, same contents, and assertions that invalid CAS cannot invoke `load_checkpoint_revision` or `save_runtime_checkpoint`. The LAB workflow executes these on Ubuntu/Windows, together with original recovery and checkpoint trace-coherence and A79 H0 regressions. Canonical Quality 588 modules / 6,895 tests and Security A74 365 remain unchanged and unwaived; baseline inherited from #1409 = 51 FAIL + 34 ERROR (85 known identifiers).

**Safety boundaries:** HARD NO-GO, 0/6 P0 homologated, Worker OFF, ZERO_AUTO_RESEND. No merge/deploy, real restore, external API, provider enrollment, credential purchase or spending.
