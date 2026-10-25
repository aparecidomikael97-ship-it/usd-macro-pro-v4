# AtlasQuant / AION A190 — G51 G50 candidate consolidation and CI evidence

Date: 2026-10-25. Branch `lab/aion-a190-g51-g50-consolidated-regression-20261025`, stacked **Draft PR #1539** on G50 CAS Draft #1537. Parallel independent G50 Draft #1538 remains open and unmerged. This is LAB-only; **not `main`, not production certification**.

## Question and comparison

G50 #1537 and #1538 both protect a locally confirmed Outbox ledger against a delayed/reentrant synthetic send callback. They differ in error presentation:
- #1537 uses snapshot + SQL conditional compare-and-swap (CAS) for nonfenced post-send outcomes, returning `dispatch_state=G50_STALE_SEND_REPLY_NO_WRITE` and the current persisted state on a stale result.
- #1538 relies on an additional post-callback assertion, raising `RuntimeError(G50_SEND_CALLBACK_CHANGED_NO_OVERWRITE)` in nonfenced cases. The pre-write assertion alone does not add the same SQL CAS against a separate concurrent writer.

G51 **does not merge the two implementations**. It reuses #1537 as source implementation and incorporates the additional *tests* from #1538 with an explicit common no-write contract. No changes to `atlasquant_aion_execution_outbox.py` on G51.

## Reproduction: initial cross-branch RED vs reconciled GREEN

- At commit `ea4a9825efccb46789662d8428ba16622efda6d3`, copied #1538's four `test_g50_send_callback_immutability_lab.py` cases verbatim alongside #1537's seven existing `test_g50_postsend_stale_reply_lab.py` cases.
- Initial Windows test suite: **9/11 PASS; 2 FAIL**. Only two exceptions were expected by #1538 but not raised by #1537; the later stale result returned explicitly instead.
- At `90003ce789dc0c2398a1d33d3947719eb1d779e1`, changed the two *test assertions* to expect the explicit stale no-write response and `state=CONFIRMED`. Retained their checks that the original local ledger reference, exactly-one effect, no requeue, and single synthetic send call remain.
- Post-adjustment G50 11/11 PASS in isolated Windows worktree `C:\Users\apare\AtlasQuant-G51-Combine-LAB-20261025`.
- Regressions `test_g30_*.py` through `test_g49_*.py` all passed: **G30-G50 Windows local 442/442**, no pending working-tree changes.

## Codex independent CI review

The current installed Codex CLI `0.164.0-alpha.11.1`, model `gpt-6.1-sol`, session `01a173cf-b0af-7a40-9819-bf75cc492fd9`, ran with `-s read-only --ephemeral` against the G51 Windows worktree. Scope was **CI YAML/test name quality only**, not authorization exploit work, code modifications or executions.

Review recommendations:
1. `test_g50_*.py` discovers both G50 suites; update workflow from `Ran 7 tests` to `Ran 11 tests`.
2. Include both test filenames in GitHub Actions PR `paths` trigger.
3. Explicitly check expected markers from both suites and retain `shell: bash` on Windows/Ubuntu.
4. Stacked PR workflows depend on workflows and changed-path filters of their base branches; job evidence must be verified at the exact SHA.
5. Codex did **not** access the repository's live GitHub checks, edit code or run tests. A separate earlier unrelated security-review session was blocked by the tool and is **not** represented as complete.

At commit `a6d90bef162a168c470ba96b49d2457f4e663a65`, G51 workflow `.github/workflows/aion-a190-g50-postsend-cas-lab.yml` was adjusted to discover both suites, check 11 tests, include both files in trigger paths, and enforce inherited G30-G49 regressions.

## Verified CI — exact tested code/workflow SHA

Run [GitHub Actions #40210327857](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40210327857) executed against exact **`a6d90bef162a168c470ba96b49d2457f4e663a65`**:
- Ubuntu job `121219981964`: **SUCCESS**, G50 11 plus G30-G49 431 = **442** focused tests.
- Windows job `121219982152`: **SUCCESS**, same **442** focused tests.
- **884 cross-OS test executions of 442 distinct focused cases**, not 884 independent scenarios. Tests use disposable SQLite and in-process synthetic adapters.
- Report-writing is a later evidence-only commit; do not mistake this document HEAD for the CI-tested SHA. Previous G47-G50 path-specific tests may overlap the cases, so don't add totals across runs.

## Limits and mandatory gate

This evidence does **not** prove trusted HUMAN_OWNER identity, external receipt provenance, independent monotonic custody, hostile-host rollback safety, power-cycle H0 recovery, atomic externally verified first-send, provider-level idempotency, physical sidecar resilience, or full A184 canonical Security/Quality clearance. Historical pypdf and Pillow vulnerability findings require separate remediation and verification.

**0/6 P0 HOMOLOGATED. HARD NO-GO. UNCERTAIN. ZERO_AUTO_RESEND.**

No merge to main, deploy, production Worker, real provider callback, customer data, credentials, financial operation, or spending.
