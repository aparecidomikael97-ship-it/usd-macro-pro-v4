# AION A.53 — secondary activation authority fence (LAB)

Issue #1267. Exact parent A.52 Draft #1268: `60c61d959c81d50f6a9d6b5d1f1f932abf14844d`.
A49 `c1c7f5940eef913d60ff2f77e3bc1de3181db2f2`; A50 `87b4b2726c9de50860df0da313565ac105d967bc`; A51 `8062a5912312bca842e7e05eef77863ece844344` revalidated.

## Defect and limits

`atlasquant_aion_global_worker_activation.write_repository_feature_flag_enabled` was a public/importable flag writer. Calling it directly with a `RuntimeConfig` and `UNSET` or `DISABLED` reached POST/PATCH with `value=1`, bypassing the higher-level approval ceremony. It accepted no authority evidence, human confirmation or independent witness. This is a concrete unsafe activation write boundary, not proof of a live Worker bypass: A47/A48/A51 still deny productive CAS/execution.

The wrapper `activate_global_worker_feature_flag` separately accepted an injectable `flag_writer`. Its real local plan/ticket checks accepted purely local staging without an enrolled external trust root, then invoked that writer. Guarding only the default writer would leave this alternate invocation open.

All demonstration transports and readers were intercepted using local fixture values. No production token, external request, flag change, Worker activation, real signature, enrollment, financial action or provider was used. Local digests are not cryptographic independent approval. This work does not claim owner verification or P0 homologation.

## RED -> GREEN

Test-only remote commit: `1ee2de01bbbd7537041d2a238cc5f3daea664300`; local equivalent tree commit: `f5e335382cb31f52138741d46309cb3a2c7a322c`. Only the activation test file differs from A52 in that RED tree.

Command: `/usr/bin/python3 -m unittest -v test_atlasquant_aion_global_worker_activation.A53IndependentActivationBoundaryTests`.

Before runtime patch: 5 tests, **1 PASS / 4 FAIL / 0 ERROR / 0 SKIP**. Failures demonstrate:

1. Direct UNSET writer reached mocked POST `/actions/variables` with enabled value.
2. Direct DISABLED writer reached mocked PATCH of the named variable with enabled value.
3. Direct writer evaluated caller config descriptors before denial.
4. Real local plan/ticket validation allowed an injected flag writer to run.

The control confirms safety-disable writes only value `0` via intercepted transport.

After patch: all **5 PASS**. Runtime change is confined to the activation module: a shared unconditional fail-closed result at the direct writer and immediately before the wrapper's writer boundary, after existing negative checks. Obsolete enable/rollback tail removed; safety deactivation remains available. No test switch or fake witness unlocks activation. Future enabling requires a separately reviewed independent authority implementation.

All pre-existing activation test class/function AST nodes are identical to parent A52. Saga, Outbox, background executor, their tests, both shared workflows and `atlasquant_aion_core.py` remain byte-identical to A52.

## Reproducible validation and historical RED

`python tools/aion_a53_lab_audit.py focused` runs five A53, seven A50, three A51, three A48, three A47 and three A46 cases: **24 total**. Live requests and socket connections are denied during import and execution; test spies never create independent proof.

`activation` selects the complete pre-existing activation module plus A53: **28 tests / 22 PASS / 6 FAIL / 0 ERROR / 0 SKIP** locally. Six original positive simulations still expect flag activation or post-enable rollback; their assertions are unchanged:

- `test_writer_creates_when_unset_and_updates_when_disabled`
- `test_success_enables_only_flag_and_requires_future_live_evidence`
- `test_runtime_change_after_flag_write_rolls_activation_back`
- `test_failed_post_write_flag_verification_rolls_back`
- `test_uncertain_write_that_observes_enabled_attempts_safety_disable`
- `test_critical_status_when_safety_disable_cannot_be_confirmed`

`security` and `quality` read the exact unittest selections from existing shared workflow steps, without modifying them or executing arbitrary shell. The dedicated A53 workflow targets the stacked A52 branch and checks out the PR source SHA explicitly. Focused, Security and Quality are separate mandatory matrix jobs; a green focused job cannot hide the historical RED jobs. There is no skip, xfail, continue-on-error or permission escalation. All selections return their real nonzero exit on failure.

Cloud local Python 3.13.5 has requests/cryptography but lacks pandas/pytest/pypdf/streamlit and other project dependencies. Security locally: 349 tests /345 PASS/2 FAIL/2 ERROR, including one missing-pandas import ERROR. Quality local exploratory results are incomplete and cannot replace exact-HEAD CI. A temporary path-to-module conversion defect in the audit script was detected and corrected before publication; its unsuccessful attempts are not evidence of project test behavior. Git source snapshot was reconstructed by content-hash verification (1,676 blobs; tree `a5d630f2f6fb90a0ee345b613161d1f8a5339719`). Only the base commit was obtained, so LAB accurately marks that boundary shallow. Exact-HEAD CI URLs/counts are reported in #1267/#1190 and the Draft PR after completion.

## Call-site and authority map

| Entry / callee | Trust material | Effect boundary / status |
|---|---|---|
| Admin activation UI -> activation wrapper -> flag writer | Host access mapping, local plan/ticket digests, readiness and reactivation data | A53 denies before writer; direct import denies before config/HTTP |
| Autopilot scheduled workflow -> `run_global_worker_once` | Runtime config, flag, checkpoint delegation and local digests | A47 denies before first CAS/executor; GET-only checkpoint observation can precede denial |
| `_persist_runtime_checkpoint_cas` direct import | Config, caller checkpoint, local metadata | A48 denies before config properties/PUT |
| `worker_tick` -> `_execute_due_local_work_authorized` | Local armed state and digest | A51 denies ARMED_WORKER before handler/receipts |
| Global Worker -> same internal kernel | GLOBAL_WORKER and local digest | A51 denies direct/global paths; A47 earlier denies production boundary |
| Manual `execute_due_local_work` / internal HUMAN_CLICK | Authenticated access mapping, confirmation boolean or digest | Manual read/draft path remains; direct HUMAN_CLICK relabelling is a residual proposal requiring the reserved background executor, not patched here |
| `handle_runtime_intent` -> data-only Core | Host session/typed scope; supplied runtime evidence | Local data processing, no external execution; source observations are not independently reauthenticated |
| `execute_local_tool` / command orchestrator proxy | Tool Hub preflight, source_kind, authenticated_admin, access | Closed READ/SEARCH/DRAFT handlers; caller assertions are not independent owner/witness proof |
| Outbox dispatch/reconcile and Saga effect sync | Local lease, SQL rows, claimed receipts | Independent producer admission remains blocked; no edits to reserved modules |
| `save_runtime_checkpoint` / write reconciliation | Approval boolean, config, expected SHA, local digest | Manual persistence and content/transport evidence; not independent source or latest-head proof; not modified |
| `execute_openai_answer` | Feature and approval booleans, budget/config supplied by caller | Direct provider approval binding is a separate unclosed surface; inspected only, no provider call/test/patch in A53 |
| Generic durable store / receipt envelopes | Local state, digests, scope records | State/persistence alone supplies no external COMMITTED_EFFECT or terminal fencing proof |

No comprehensive claim that all importable Python functions are secured against a caller with arbitrary code execution. These are application entrypoint boundaries. The selected A53 defect is proven; residual paths are limits/proposals, not claimed fixes.

## Required external contract and blockers

Independent enrollment must bind the HUMAN_OWNER, tenant, workspace, repository, branch, path and permitted action to a root controlled outside this host/GitHub administrator. Approval must bind the current checkpoint digest/revision, expiry, unique nonce and scope, and be consumed without replay. A latest-head witness must attest a monotonic version from independent custody and reject coherent rollback as well as tampering. CAS must enforce the exact expected version and fencing owner/token.

Producer `COMMITTED_EFFECT` must bind causal intent/idempotency key, scoped owner/tenant, effect reference and producer-authenticated outcome. `NO_EFFECT_FENCED` must be a terminal producer-enforced guarantee against late effects before retry/compensation is possible. Local fixture signatures, SQL, hashes or status strings satisfy none of this.

23 historical Outbox ERROR, 8 Saga ERROR, legacy Worker/inflight failures, independent producer/witness/physical owner acceptance remain open. The 45 A12/A16 originals remain 0 recovered/0 executed; no repeated archive search or replacements were created.

**0/6 P0 homologated; first installation 20/20 HARD NO-GO.** LAB Draft only; no merge/main/Core V1 change, deploy, actual flag write, Worker/Render, physical installation, real keys/credentials, accounts/services, costs, trading or commercial effects.
