# AtlasQuant / AION A190 — G73 store.dump() bounded pre-copy admission

**Date:** 2026-10-25. **LAB:** lab/aion-a190-g73-chat-dump-precopy-guard-20261025. **Draft PR:** [#1559](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/pull/1559), stacked on G72 Draft #1558, NOT main.

## Safety and scope

Only FAKE synthetic data and disposable local SQLite. No customer records, real credentials, provider SEND, Worker, funds, main merge, deploy or additional paid resources. No external P0 homologation or operational authorization is implied.

## Proven cause — real RED first

The chat store serializer `aion_chat/store.py:dump(value)` was calling `redact(asdict(value))`. The dataclass `asdict` recursively copies nested dict/list/tuple graphs *before* the G70 shared redactor checks the cycle, 64 depth or 4096 expanded visits. Thus a checkpoint with cyclic metadata reaches Python `RecursionError` instead of the stable local denial; a compact shared DAG may exponentially expand during the copy before late rejection.

Test file `labs/a190/test_g73_chat_dump_precopy_lab.py` first committed **alone** at **d7966a72c2c004377da46bbf8bfd66a04f4c2248** and run on Windows disposable SQLite against unchanged G72:
- **14 tests: 9 PASS, 5 ERROR**, exit 1. Direct and indirect checkpoint cycles and checkpointer write encountered exceptions during pre-copy; a mock `asdict` sentinel independently detected the forbidden call.
- Some deep/wide and DAG cases *already* passed, but only because post-copy redaction finally denied the materialized object. Those were not counted as proof of bounded preprocessing.
- Benign shared acyclic objects, normal checkpoint, summary, message and conversation serialization passed baseline controls.

Independent Windows Codex CLI prepatch read-only/ephemeral session **01a175c9-0994-7f89-a145-df10d004f2a5** confirmed the unbounded pre-copy path, affected checkpoint and conversation store methods, and recommended shallow dataclass field projection. It made no changes, executed no tests, used no network/GitHub/provider.

## Two-phase correction

1. `aion_chat/store.py`, code SHA **cb0d72e555132a371a43d7ec817afd0feeb3a7d5**: project only declared top-level dataclass fields with `fields(value)` + `getattr`, then invoke existing bounded G70 `redact`, then original UTF-8 JSON dump. No new recursive copy ahead of the guard. Other callers of `asdict(scope)` and the G71 message admission remain unchanged.
2. Codex prepatch analysis cautioned nested dataclasses under arbitrary metadata had previously been implicitly normalized by `asdict`. New tests were committed **before** further source change at SHA **55c3d29e73c360420cf00c4047f4062c8da6b926**. **17 tests: 16 PASS / 1 ERROR**: incidental `TypeError` on a nested dataclass. SHA **d2d88bdeb969037f5b391968a860f605149f1cfa** explicitly rejects unsupported nested dataclasses with stable `G73_UNSUPPORTED_NESTED_DATACLASS_DENY` at JSON default handler instead of restoring unbounded recursive conversion.
3. Independent Codex postpatch read-only/ephemeral session **01a175cf-b3c2-7823-909f-81a26cab84eb**, inspected source+workflow SHA e65d6ba. It confirmed bounded pre-copy, ordinary flat model compatibility, valid previous checkpoint pointer retention and G72 hygiene unchanged by static inspection only. It found **three additional gaps**: nested dataclasses under masked sensitive keys could bypass the JSON default, dataclass **classes** could be accepted where `asdict` had required instances, and CI workflow path triggers omitted shared privacy/model and hygiene dependencies.
4. Expanded adversarial tests were committed **before** their fixes at test-only SHA **ac4f43da360c843a695bdfc13064a1d39900ad55**. Actual Windows G73 **20 tests: 17 PASS / 3 FAIL**: two hidden-dataclass bypasses (including checkpoint pointer rollback) and dataclass-class input were reproduced on unchanged source.
5. Additional runtime corrections:
   - `aion_chat/privacy.py` code SHA **1a001a902b34af25798205f757d714c3fe65cad7**: reject unsupported nested dataclass instances/classes at the **bounded G70 redactor traversal**, even in a masked sensitive field, before JSON. Preserve existing G70 cycle/depth/node guards and benign sensitive string/list redaction.
   - `aion_chat/store.py` code SHA **02adbca349fbd14f7d3515a565a63acd306d3740**: require a dataclass **instance**, explicitly denying dataclass classes and non-dataclass inputs. No arbitrary object-to-string fallback.
   - Full G73 local specific suite now **20/20 PASS**, including explicit nested denial under `password` and `secret`, prior checkpoint immutability (same id, message count, storage health) after failed attempt, ordinary flat checkpoint, summary and message compatibility, and sentinel that `asdict` cannot execute before bounding an expanding DAG.
6. The narrowing is deliberate and fail-closed: **previously implicit nested dataclass normalization under arbitrary metadata is no longer supported** without a separately designed bounded validator. Legacy database records were not migrated or rewritten.

## CI provenance

Final code+workflow SHA **77f1cfda83ab23ac9d31e63ca3749c70a4bc07e9**:
- `.github/workflows/aion-a190-g73-chat-dump-precopy-lab.yml` runs **719 distinct G30–G73 focused synthetic tests per OS** and separately **2 repository credential fixture-hygiene tests per OS**; includes paths for store.py, privacy.py, models.py, G73/G71 tests and fixture hygiene checker. G72 changes synthetic fixtures only and contributes no extra G numeric tests.
- Initial Windows run on older SHA e65d6ba (before the last three G73 cases) showed **716/716 focused + 2/2 hygiene PASS**.
- **Final Windows VERIFIED**: isolated detached clean Windows checkout at exact code+workflow SHA **77f1cfda83ab23ac9d31e63ca3749c70a4bc07e9**: **719/719 focused G30–G73 PASS** (71.756 seconds), **2/2 secret-fixture hygiene PASS** (0.374 seconds), exit 0 and clean Git status. Earlier 716 cases are obsolete for the final patch. [GitHub Actions G73 run #40254497412](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40254497412) is **QUEUED** at this report update; do not claim Ubuntu/Windows cross-OS success before checking both jobs and their logs.
- A final independent Windows Codex CLI postpatch read-only/ephemeral audit **01a175d4-5db3-7400-a631-8ffcb64bcc45**, on SHA 77f1cfd, **COMPLETED**. It inspected both source changes and tests/workflow, WITHOUT editing files, running tests, using network/GitHub/provider. The static audit confirmed the class-vs-instance guard, nested dataclass rejection in both bounded-redaction paths including hidden fields, original identity/cycle checks, compatibility of flat store models and prior checkpoint pointer rollback. It independently counted **20 G73 tests, 719 focused tests and 2 hygiene tests**. Remaining limits are custom Python method side effects, unbounded aggregate scalar text bytes/output size, and non-finite JSON serialization (`allow_nan` unchanged). The workflow's step *label* still refers to G71 despite running G73; this is cosmetic and does not change the executed tests.

## Remaining limitations

- A hostile custom Mapping iterator/property getter may block or run Python-side effects; the bounded redactor accounts for returned nodes but is not a sandbox, and `getattr` on arbitrary non-model dataclasses can execute accessors. The store accepts known models in normal operations.
- Python objects other than supported builtin containers, as well as wide scalar strings and preloaded in-memory objects, do not gain a general CPU/memory sandbox. No entire-store historical cleanup, antirollback or native SQLite P0 certification follows.
- Broader chat Golden Path integration in this Windows environment previously lacked a `pandas` dependency. Passing specific A190/hygiene tests cannot be presented as passing all canonical Quality/Security modules.

**0/6 P0 HOMOLOGADOS · HARD NO-GO · UNCERTAIN · ZERO_AUTO_RESEND.** No main merge, deployment, Worker or real financial provider SEND.
