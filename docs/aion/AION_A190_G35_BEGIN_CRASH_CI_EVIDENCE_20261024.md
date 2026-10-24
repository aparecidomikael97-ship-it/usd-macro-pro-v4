# AtlasQuant / AION A190 G35 — BEGIN uncertainty and abrupt child-process exit

**Date:** 2026-10-24. **Exact tested code/workflow SHA:** `d4fb4d5ef2e2b94cc3accab3868d6e7656c76f31`.
Branch `lab/aion-a190-g35-begin-ack-process-crash-20261024`, stacked on G34 Draft #1521. Draft/LAB only; not merged or deployed.

## G35 code candidate

- `aion_chat/store.py`: new `_begin_or_quarantine()` for transaction-managed writes and `append_message`. A `BEGIN IMMEDIATE` error may happen *before* or *after* the database acquired a transaction lock; the code quarantines/detaches/closes the store in either case. An error must not be interpreted as evidence the transaction never started.
- `atlasquant_aion_execution_outbox.py`: new `_begin_or_quarantine()` used by the five explicit Outbox BEGIN sites (enqueue/claim/release/_confirm and managed write transitions). Any failed BEGIN creates a sticky local failure, detaches the shared connection and denies retry; no provider dispatch or worker is enabled.
- `labs/a190/test_g35_begin_ack_process_crash_lab.py`: 18 adversarial tests with real local SQLite and faulting connection proxies, plus **disposable child processes** terminated with `os._exit(91)`. The hard exit is executed **only in a spawned test process**, not in CI runner main process or a real AION instance.
- `.github/workflows/aion-a190-g35-begin-crash-lab.yml`: Windows/Ubuntu matrix, G35 tests + full targeted G30–G34 regressions, marker checks and mandatory no-go.

## Verified CI evidence

[**G35 GitHub Actions #40126686451**](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40126686451) **SUCCESS** at code SHA above.
- Windows job `120969538055`: **18 G35 + 16 G34 + 24 G33 + 20 G32 + 18 G31 + 23 G30 = 119/119**.
- Ubuntu job `120969538222`: **119/119**.
- **238 executions of 119 distinct tests.**

Evidence marker interpretation:
- `G35_CHAT_BEGIN_BEFORE_GREEN=STORE_QUARANTINED`: failure before physical BEGIN detaches Store.
- `G35_CHAT_BEGIN_AFTER_RED=TRANSACTION_STARTED_ACK_LOST`: BEGIN succeeded on real SQLite, then wrapper returned error; Store is quarantined rather than trusting the exception.
- `G35_OUTBOX_BEGIN_AFTER_RED=LOCK_ACQUIRED_ACK_UNKNOWN_QUARANTINE`: same case for real Outbox.
- `G35_CRASH_PRECOMMIT_GREEN=UNCOMMITTED_UPDATE_ROLLED_BACK`: after abrupt disposable child exit, an uncommitted state change is absent on a new SQLite connection.
- `G35_CRASH_POSTCOMMIT_RED=UNCERTAIN_STATE_PERSISTED_AFTER_EXIT`: if child committed UNCERTAIN before hard exit, the state is durable and cannot be treated as absent.
- `G35_LOCAL_REOPEN_LIMIT=NOT_INDEPENDENT_FIRST_SEND_EVIDENCE`: new local store being healthy is not external proof of semantic first-send reservation or provider effects.

**These RED markers mean intentionally reproduced limitations, not repaired external custody.** The G35 guard isolates and denies in-process follow-up, but cannot guarantee antirollback after hostile host restores SQLite and witness history. The child exit test is not a physical power failure or fsync fault.

## Wider CI at the same exact SHA — 16/17 successful workflows

- **16 workflows SUCCESS**, including G12, G14, G31–G35, A176–A181, A186/A187 and staged SQLite lifecycle.
- [**A184 six P0 evidence #40126686435**](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40126686435): **FAILURE/RED**, not homologation.
- Candidate canonical Quality job `120969538391`: **6,449 tests PASSED**.
- BASE canonical Quality job `120969538453`: 6,322 tests, **4 failures**.
- Candidate canonical security-unittest and security-pytest passed.
- Candidate security-audit job `120969538450`: **FAILED**, `pip-audit -r requirements.txt` reported **48 known vulnerabilities across pypdf 6.19.0 and pillow 12.3.0**. Base audit also failed; external requirements remain absent; intentional BASE adversarial RED persists.

## No-go and further proof

- The only process terminations are in a synthetic disposable subprocess: **NOT a machine power cut**, adversarial host manipulation, actual disk loss/fsync fault, genuine SQLite corruption, provider dispatch or external receipt.
- A `BEGIN` failure followed by quarantine does not prove whether the transaction acquired a lock, and reopening local SQLite is **not a trustworthy independent high-water witness**.
- Other P0 shortcomings remain: independent trusted HUMAN_OWNER identity, authentic provider receipts, semantic first-send idempotency, external monotonic antirollback H0 recovery, and native SQLite compatibility homologation.
- Next suggested LAB G36: fail-closed cross-process recovery admission with explicit external witness freshness boundary; do not conflate synthetic witness object with independent infrastructure. Also track A184 `pip-audit` and historical failures separately.
- No merge/main/deploy, Worker, provider, customer data, operational keys or spend.

**0/6 P0 homologated · HARD NO-GO · UNCERTAIN · ZERO_AUTO_RESEND.**
