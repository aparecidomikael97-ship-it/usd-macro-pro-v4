# AION / AtlasQuant A190 — G50 post-send stale callback CAS (LAB)

Date: 2026-10-24 (Cuiabá). Evidence for stacked **Draft PR #1537**, branch `lab/aion-a190-g50-postsend-stale-response-cas-20261024`, based on G49 Draft #1536. **Not main, not merged, not deployed.**

## Security claim, narrowly stated

In an isolated disposable SQLite Outbox, a synthetic send callback can reenter the same local store and change the previously reserved attempt before returning a reply or raising. On the prepatch G49 code, a later accepted/rejected/error reply (under opt-in synthetic callbacks) could overwrite the newer local row, even if already CONFIRMED with a ledger entry or REVOKED. This is a local state-coherence error; **it is not a demonstration of a real provider effect or an external exactly-once guarantee**.

### Before change (falsifiable RED)

- New tests `labs/a190/test_g50_postsend_stale_reply_lab.py` committed first at `599be1070d6cd8c48e7c80881254b01ce850e976`.
- Actual Windows execution before application-code patch: **7 tests, 5 failed, 2 passed**.
- Failures: earlier local CONFIRMED overwritten after delayed negative response; REVOKED overwritten by positive response; new local claim generation or claimant overwritten; exception after inner confirmation damaged confirmed state.
- All tests are disposable synthetic SQLite files; no provider, Worker, customer data, credentials, network send or financial amount execution.

### Implementation and broader regression

- Initial G50 CAS implementation `865395d79c394ba0f04d267644573a2cf02e0ef4`: record post-getter pre-send local snapshot; compare reply to local state; require exact SQLite update CAS (phase, claim generation, lease owner/deadline, effect reference) for success/rejection/exception; pass expected snapshot into confirmed-effect transaction.
- The initial targeted G43-G50 set **131/131 PASS** on Windows.
- An **expanded** G41 historical run then surfaced 3 regressions in expected strict fencing behavior/error precedence. These were **not concealed**. Follow-up candidate `3019592f816966a7079d73a9cd70a81a795d013a` preserves G41's historical error contract while keeping G50 CAS for the nonfenced path.
- Follow-up tested in independent clean Windows worktree `C:\Users\apare\AtlasQuant-G50-PostSend-LAB-20261024`: G50 **7**, G49 **7**, G48 **11**, G47 **18**, G46 **10**, G45 **7**, G44 **39**, G43 **32**, G42 **28**, G41 **18**, G40 **36**, G39 **28**; **241/241 PASS**.
- Wider regression also passed on the same exact code SHA: G30 **23**, G31 **18**, G32 **20**, G33 **24**, G34 **16**, G35 **18**, G36 **20**, G37 **34**, G38 **24**; additional **197/197 PASS**.
- Total: **438 Windows tests PASS**, covering G30-G50. These are local synthetic checks; counts are executions not P0 gate certifications.

### Continuous integration status and reproducibility

Path-specific GitHub CI with Windows/Ubuntu matrix now includes all **438** cases per OS at workflow-only commit `770eaddf4d27cc705e4ff75868476962f5d4fd2a` (`.github/workflows/aion-a190-g50-postsend-cas-lab.yml`). This evidence document is written **after** the tested source commit.

**As of report authoring, GitHub commit workflow lookup returned no pull_request workflow runs for either workflow SHA or earlier G50 SHA. Thus Ubuntu CI is NOT VERIFIED; do not claim 876 successful cross-OS runs.** Other CI and the canonical A184 dependency/Security suite have not been rerun here.

### Codex boundary

Connected Windows Codex CLI 0.163.0-alpha.11.2, gpt-6.1-sol, read-only ephemeral, session `01a1707f-8ae9-7cc3-9f04-c7f3558cfc0e` was invoked to review G49 post-send/reconciliation behavior. The Codex run **ended unsuccessfully with a tool security restriction**; its partial observations do not count as an independent successful review of G50. We did not bypass the restriction. Tests and corrections described above were executed and verified directly, not attributed to that incomplete Codex review.

There is a separate contemporaneous stacked **G50 Draft PR #1538**, focused on related callback reentry. Both proposals touch the same Outbox area. **Do not merge either without reviewing overlap/conflicts and verifying all relevant CI and no-go gates.**

## Nonclaims / hard gate

The test-only `unsafe_allow_synthetic_lab_callbacks` flag never authorizes a real provider; default callbacks remain blocked. This work does not prove external HUMAN_OWNER identity, third-party receipts, independent monotonic custody, hostile-host rollback safety, real provider idempotency, physical restart H0 availability, complete A184 Quality/Security green or the six P0 gates.

**0/6 P0 HOMOLOGADOS · HARD NO-GO · UNCERTAIN · ZERO_AUTO_RESEND. No main, merge, deploy, Worker, real SEND, customer data, credentials or spending.**
