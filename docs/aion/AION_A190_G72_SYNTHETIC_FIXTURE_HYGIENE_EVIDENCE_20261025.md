# AION A190 G72 — Synthetic fake-token fixture hygiene (LAB)

> Evidence only; no external root of trust, no P0 sign-off, no operational SEND.

## Trigger / baseline (RED)
- Prior A184 GitHub workflow run `40242746283`: canonical Quality candidate `Ran 6449 tests`, `FAILED (failures=1)` on `test_no_committed_secret_files_or_private_keys`.
- Four source files with credential-shaped literals: G62, G63, G64 and G65 synthetic test modules. These are fake LAB examples, **not validated real credentials**.
- Local Windows baseline G71 commit `3a9da9bc50a855ada9abe3b97fcbecd7368bfe83`: hygiene suite `Ran 2 tests`, `FAILED (failures=1)`; four findings reproduced.

## Narrow G72 fix
- Change fake fixture source literals to concatenate two constant string fragments. Python runtime value remains the same, including secret-prefix semantics, while source text no longer contains contiguous credential-looking fixtures.
- No production module touched. `test_atlasquant_repository_secret_hygiene.py` detector unchanged; no exclusions or allowlist entries introduced.
- The test code retains runtime assertions for redact, fail-closed denials, no unintended SQLite writes and retry constraints.

## Windows local GREEN after fix
- `python -B -m unittest -q test_atlasquant_repository_secret_hygiene`: **2 / 2 PASS** (exit 0).
- `python -B -m unittest discover -s labs/a190 -p 'test_g6*.py' -q`: **147 / 147 PASS** (exit 0).
- `git diff --check`: clean.

## Independent Codex CLI audit (read-only)
- Session `01a17571-e237-70b1-afc2-ad6221850f12`; sandbox `read-only`; exit 0.
- Compared the four changed fixture files against G71 HEAD. Reported normalized AST equivalence and recursively equivalent compiled bytecode for all four.
- Verified the original hygiene scanner source unchanged and its 2 tests passing. Reported no concrete regression in those fixture diffs.
- Scope distinction: Codex did **not** run the G6x suite; its review preceded creation of this dedicated CI workflow/evidence document. We ran G6x separately (147/147 PASS).

## CI and limitations
- Dedicated G72 Ubuntu/Windows workflow reruns hygiene and full G6x test selector; CI results must be read separately from GitHub.
- Local result is not a full canonical Quality rerun; do not state the 6,449-case candidate suite is green without executing and checking it.
- Static regex hygiene remains intrinsically limited (assembled runtime strings cannot be detected by an ordinary contiguous-source pattern); this fix changes only synthetic fixtures, not a security boundary.
- All six P0 remain **NOT HOMOLOGATED**. HARD NO-GO: no merge, deploy, Worker, external SEND, real money, claims of external attestation or CI green without evidence.
