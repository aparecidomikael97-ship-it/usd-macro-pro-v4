# AtlasQuant / AION A190 — G70 shared redactor bounded native graphs

**LAB date:** 2026-10-25. **Branch:** `lab/aion-a190-g70-shared-redactor-bounded-20261025`. **Draft PR:** [#1556](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/pull/1556), stacked on G69 Draft #1555, NOT main.

## Scope and invariants

Pure synthetic fake data and disposable local SQLite; no customer data, provider SEND, Worker, funds, credentials, main merge, deployment or new spending. These tests do NOT establish identity of HUMAN_OWNER, independent receipt authenticity, external H0 custody, physical SQLite antirollback, real exactly-once first SEND, or canonical Security/Quality approval. `UNCERTAIN` and `ZERO_AUTO_RESEND` remain unchanged.

## Independent Codex before patch

Connected Windows Codex CLI v0.164.0-alpha.11.1 with `-s read-only --ephemeral`, session `01a174e5-1f38-7393-a172-b45324286e60`, independently read G69 privacy.py and chat store.py. Located direct `redact` recursive Mapping/list/tuple without active-ancestor, depth or visit budget. Distinguished the preexisting Outbox snapshot guard from the shared chat/store redactor, and warned that `append_message` performs `asdict(message)` BEFORE redaction. Did not edit files, run tests or use network/provider.

## Actual RED committed BEFORE any runtime change

New `labs/a190/test_g70_shared_redactor_bounds_lab.py` created ALONE at **`086adb88572fb72bc41c682d3df0abdc1fb01f28`**, executed on Windows isolated G70 worktree while runtime remained unchanged from G69:
- **16 tests: 7 PASS, 5 FAIL, 4 ERROR**.
- Four ERRORs: native direct self-referential Mapping/list, indirect tuple-list cycle and cyclic UserDict reached `RecursionError` instead of bounded explicit denial.
- Five FAILs: 65th container nesting remained allowed, the 4097th visit remained allowed, repeated shared DAG expansion not bounded, and finite chat metadata with extreme depth/width was permitted instead of refused.
- Seven green controls included exactly 64 container layers, exactly 4096 list visits, benign shared acyclic data, normal masked chat and inherited string JSON limits.

## Narrow G70 code change, error exposed during patch testing

`aion_chat/privacy.py` LAB commit `af93d421d5a1fc46a23f2ee824f49726733fbd1f`:
- Keeps public `redact(value)` API, routes through a private stateful bounded walker (active-ancestor IDs, shared expanded-visit count). Denies with stable `G70_REDACT_CYCLE_DENY`, `G70_REDACT_DEPTH_DENY`, `G70_REDACT_NODE_BUDGET_DENY`.
- **64 maximum supported container depth** (root native container level 1). **4096 expanded visits**, including mapping key visits and repeated shared acyclic occurrences. Exact 4096 accepted, 4097 denied. Depth and node limits intentionally reject formerly admitted extreme chat metadata.
- Direct nested sensitive values are structurally checked even if the output will be replaced with `[REDACTED]`. A cyclic hidden subtree is **DENIED**, benign sensitive content remains masked.
- Keeps G67 explicit nonstring key denial, G68/G69 text parsing/aliases, G69 262144 UTF-8 preparse cap and 64 JSON string layers. Parsing of a JSON-looking string re-enters the same **visit budget**, with a separate decoded document depth of 1.
- No change to semantic authority, Outbox provider SEND, COMMIT, SQLite schema, or Worker.

First candidate was **NOT GREEN**: `_g70_redact` reassigned input `value` to normalized dict/list and mistakenly called `active.remove(id(value))` for the new object, producing observable **KeyError**. This was caught by running new tests, and repaired narrowly at source SHA **`842dcff5198a53eff7454b31a9af071892b5ffb5`** by preserving original input container ID before replacement.

After that fix, test #11 initially expected cyclic password content to be silently masked, contrary to the explicitly chosen fail-closed policy. A **test-only contract clarification** at `7a6861807547c017569938a02be7ebdfb6c4703a` asserts an explicit G70 cycle denial and adds a separate benign sensitive container mask test (#17). No runtime change to accommodate a weaker hidden-cycle rule. G70 direct suite **17/17 GREEN**; inherited G69 22, G68 21, G67 14, G66 12 also GREEN.

## Full local regression and exact tested SHA

Code+workflow SHA **`29dd4fb08ebb586420a8534c7736a382495d74eb`**, file `.github/workflows/aion-a190-g70-redactor-bounds-lab.yml`:
- Windows detached isolated worktree `C:\Users\apare\AtlasQuant-G70-Redactor-LAB-20261025`: G30–G70 focused suite (G51 folded into G50) **693/693 PASS**, exit code 0, clean Git status.
- Two additional root-level chat suites `test_atlasquant_aion_chat_foundation` + `test_atlasquant_aion_chat_sqlite_write_outcome`: **6/6 PASS** same final source SHA, exit 0.
- [GitHub Actions G70 #40234796692](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40234796692) configured for Ubuntu+Windows **693 distinct synthetic focused tests per OS**. Jobs were **QUEUED** when the report was written; do not claim cross-OS pass without inspecting both completed job logs and markers. Earlier cross-OS G69 run #40233604212 separately remained queued at last inspection. Documentation-only commits added after code+workflow SHA are NOT CI-tested code changes.

## Independent Codex postpatch review — verified and bounded

Second real Windows Codex CLI read-only/ephemeral session `01a174eb-f74d-7732-bc77-7f0518f782cb` inspected the exact updated source and suite, without editing files, executing tests or using provider/network:
- Found the direct shared redactor cycle, 64-container depth, 4096 expanded visit, hidden subtree policy and **original ID cleanup** to be consistent by static inspection; no new high-severity credential-masking false negative found in inspected path.
- **HIGH OPEN**: `SQLiteChatStore.append_message` evaluates `asdict(message)` BEFORE calling `redact`, inside a transaction. A cyclic `Message.metadata` object or compact high-fanout shared DAG can recurse or expand during `asdict` and **never reach G70 guards**. Existing rollback/error handler does not establish bounded preprocessing. G70 tests use *finite* deep/wide metadata, not cyclic raw chat metadata. This is a G71 RED-first target, **NOT** solved here.
- Further open limits: `Mapping.items()` may execute arbitrary user Python or block indefinitely; 4096 returned visits do not cap generator wait, peak bytes or source materialization. Mapping keys and plain prose scalar strings are not subject to an aggregate UTF-8 text budget, and native/string JSON depth budgets are distinct per decoded document. Existing chat Golden Path integration suite is NOT verified locally where `pandas` is unavailable; 6/6 foundation/write-outcome is not equivalent.

## Hard NO-GO

**0/6 P0 HOMOLOGADOS · HARD NO-GO · UNCERTAIN · ZERO_AUTO_RESEND**. No main merge, deploy, Worker, external provider SEND, genuine identities/receipts, funds or client data. Engineering improvement in LAB is NOT operational authorization.
