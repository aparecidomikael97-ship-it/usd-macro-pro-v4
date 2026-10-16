# A119 — RED→GREEN local evidence, offline only

**Date:** 2026-10-16. **Base:** lab H0-GW-01 initial 16/16 green. **Scope:** simulator only.

## RED (old `gateway.py` + new `test_witness_hardening.py`)

`python -m unittest discover -s labs/h0_gateway_offline -p 'test_*.py' -v`

- 24 tests executed; **5 FAIL** (`17`, `18`, `19`, `21`, `23`), 19 PASS.
- #17 version preserved at 2 while SQLite state `UNKNOWN -> PREPARED`, `issued_count` reset: a second fake call was possible.
- #18 SQLite version 2 while toy witness was artificially made stale at version 1: check incorrectly permitted the row.
- #19 after issued intent, opening same SQLite with missing witness allowed new issue after tampered row.
- #21 deleted intent row could be re-`PREPARE`d although surviving witness had already observed v2.
- #23 same-version forged delivery boundary and provider operation ID were invisible to version-only witness.

## GREEN (hardened `gateway.py`, unchanged RED tests)

- Same command: **24/24 PASS** on local Python 3.13/Linux.
- The original 16 tests were not modified.
- All code is fake/no provider; SQLite and in-process witness are not independent, audited production systems.
- No hosted CI or Windows results claimed; positive historical Outbox/Saga tests and 84 Quality diagnostics were not rerun.

## Required protection boundary

HARD NO-GO. The local shadow witness does not prove independent current-head antirollback, account separation, authenticated real provider effect/no-effect, human authorization, or protection against late delivery. Worker OFF, ZERO_AUTO_RESEND, no external sends, account, provision, merge, deploy, or spend.
