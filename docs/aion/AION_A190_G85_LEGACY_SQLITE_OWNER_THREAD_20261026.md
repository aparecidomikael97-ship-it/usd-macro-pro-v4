# AION G85 — Legacy SQLite creator-thread close preservation (LAB)

**Date:** 2026-10-26. **Stack base:** G84 Draft #1575 commit `9166eee61a8434c12fdc4edeeaed872cae97a44b`. **No main merge/deploy or release. 0/6 P0 HOMOLOGATED; HARD NO-GO.**

## Defect reproduced, not silently waived

The staged host previously tried to close a legacy `SQLiteChatStore` held in a UI session when a different worker thread requested a new staged binding or cleanup. SQLite's default connection is thread-affine. Calling `SQLiteChatStore.close()` from the foreign thread raised `sqlite3.ProgrammingError`; the G82 fail-closed behavior correctly detached the logical handle. Unfortunately, the raw native handle could remain physically open and the original owner could no longer call `store.close()` to release it.

**Existing real Windows regression:** `test_foreign_legacy_connection_is_retained_until_owner_can_close_it` in `test_atlasquant_aion_chat_sqlite_lifecycle.py` ended with `PermissionError [WinError 32]` on temporary SQLite file cleanup. Linux could appear clean while the native handle survived longer than intended.

## Genuine RED before production fix

Commit `ae92ad470617d8c10112a8edbc31b858b04e29c0` added five synthetic tests in `labs/a190/test_g85_legacy_owner_thread_preservation_lab.py` plus Windows/Ubuntu workflow. The tests require denying foreign-thread host legacy cleanup **before** attempting SQLite's native close, keeping owner-thread release possible; same-thread migration and thread-independent `OperationScopedSQLiteChatStore` cleanup must remain functional. Retained raw handles are safely closed only by the test fixture on the original thread.

[RED run 40315329696](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40315329696):
- Ubuntu: `Ran 18 tests`, `FAILED (failures=3)`.
- Windows: `Ran 18 tests`, `FAILED (failures=3, errors=1)`. The additional error was the original canonical lifecycle test `WinError 32`, not a fourth independent G85 assertion defect.
- Two G85 controls and the G83/G84 included regressions were preserved in the selector.

## Minimal LAB-only correction

Two production modules modified without altering the G82 fail-closed `SQLiteChatStore.close`:
1. `aion_chat/store.py`: retain a local `threading.current_thread()` marker when constructing `SQLiteChatStore`. This is *only* a conservative local Python thread sentinel, **not** SQLite's native VFS ownership, an authenticated identity, or proof of factory provenance.
2. `atlasquant_aion_chat_host_staging.py`: a single preflight helper refuses legacy `SQLiteChatStore` close on a different thread **before** invoking `store.close` in three host flows: replace old binding, close all staged stores, close one staged store. The session handle remains present until the original creating thread may close it. Operation-scoped handles remain closeable across threads.

The code does **not** retry failed close or rollback, give foreign-thread legacy access, open additional network/provider connections, or bypass security gates.

## Verified GREEN on exact corrected production SHA

**Corrected code commit:** `6fd2ec7ddd81adb164240d3a011d81d16dce2b9e`.

- [G85 focused run 40315536047](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40315536047): **18/18 PASS Ubuntu**, **18/18 PASS Windows**. All five G85 markers confirmed in both job logs.
- [Canonical SQLite staged lifecycle run 40315536112](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40315536112): **both Ubuntu and Windows jobs SUCCESS**. The exact Windows case `test_foreign_legacy_connection_is_retained_until_owner_can_close_it` passed and full Windows lifecycle log stated `Ran 93 tests`, `OK`.
- [G84 inherited run 40315536096](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40315536096): both OS jobs SUCCESS (111-case selector).
- [G83 inherited run 40315536058](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40315536058): both OS jobs SUCCESS (105-case selector).

## Security boundaries unchanged / unresolved

This prevents a *known* host-level foreign-thread cleanup from stranding a default native SQLite handle, but caller-controlled custom connection factories may return handles created on another thread and cannot be certified by the Python constructor-thread marker. Arbitrary direct calls to `SQLiteChatStore.close` outside the controlled host are not intercepted; G82 keeps them logically fail-closed. Native file identity, long-term antirollback, independent monotonic custodian/witness, external owner/receipt authenticity, H0 restart availability, and real first-send certainty remain unproven.

Separate inherited G71 broad test discover workflow still has a `requests` import dependency gap; it is not claimed fixed here. Previous Q2 6,449-case canonical Quality GREEN belongs to a separate G72 stacked branch and must not be represented as the full current G85 canonical result. No Codex independent review was performed this turn because authorized Windows host was offline.

**NO MERGE · NO DEPLOY · NO WORKER · NO PROVIDER SEND · NO REAL FUNDS · 0/6 P0 · HARD NO-GO.**
