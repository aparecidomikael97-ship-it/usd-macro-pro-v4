# AION A190 G71 — chat pre-copy bounded privacy guard (LAB, 2026-10-25)

## Scope and source
- Isolated stacked branch `lab/aion-a190-g71-chat-precopy-guard-20261025` from G70 SHA `29dd4fb08ebb586420a8534c7736a382495d74eb`.
- Only synthetic fake metadata / disposable local SQLite, no provider, SEND, Worker, customer data, funds, secrets, deploy or main merge.
- Target: `aion_chat.store.SQLiteChatStore.append_message`, where `asdict(message)` recursively expanded nested metadata BEFORE G70 cycle/depth/visit checks.

## Falsifiable RED first
- Test-only commit: `a76f784` (`labs/a190/test_g71_chat_precopy_guard_lab.py`).
- Python 3.12 Windows local, 6 cases: **2 passed / 1 failed / 3 errors** (exit 1). Three cyclic graphs crashed recursively through dataclasses.asdict; patched-asdict sentinel independently demonstrated the premature call. A bounded shared DAG and normal masked chat passed baseline controls.
- No actual user data, remote provider calls or external effects.

## Narrow patch and green evidence
- Replace only the admission-time recursive `asdict(message)` with a shallow projection of the **declared Message dataclass fields**, then invoke existing G70 `redact` before constructing the sanitized Message.
- The post-sanitization `dump(message)` path remains unchanged. This is NOT a global dataclass serializer rewrite.
- Six new G71 tests: **6/6 PASS**, covering direct/indirect/hidden cycles, asdict preguard sentinel, shared DAG budget denial and ordinary redacted persistence.
- Full local Windows `python -B -m unittest discover -s labs/a190 -p 'test_g[3-7]*.py' -q` on Python 3.12: **699/699 PASS**, exit 0, elapsed **64.889s**. Includes G30–G71 regression tests; G51 consolidated within G50.
- The transaction count, conversation count and storage health were checked after rejected messages; normal fake-sensitive content persisted as `[REDACTED]` without mutating the input.

## CI and open questions
- A dedicated Ubuntu/Windows G71 workflow runs 699 cases per OS and checks explicit RED-to-GREEN markers. **No CI status claimed until both jobs are observed.**
- Residual: arbitrary user-defined Mapping iterator methods can block/side-effect; opaque objects and bytes/memory limits outside current guards remain unproved; attachments are consulted before redaction; other chat dataclass dump/record paths still use `asdict`. This is not an execution sandbox or universal DLP.
- Stacked Draft LAB only. G70 and all earlier PRs remain subject to their own validation. No external trust root, independent H0 custody, signed real vendor receipt, or exactly-once real first SEND is established.
- **0/6 P0 HOMOLOGADOS — HARD NO-GO — UNCERTAIN — ZERO_AUTO_RESEND.**
