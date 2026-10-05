# AION Core V2.3/2.4 — orchestration and task graph

Base: `e0ae719ee4b66403ea86e66fe4a308dcccd923f5` (V2.2A, PR #560).
One Core, eight internal responsibilities. This additive, opt-in layer composes
`prepare_aion_mission`; existing runtime, durable task lifecycle and public V2.2A
contracts remain compatible. It does not change the Trader interface.

## Architecture and STOP boundary

```text
REQUEST
  ↓
NORMALIZE (bounds, trusted access, owner/tenant/workspace/ecosystem)
  ↓
MISSION (existing V2.2A canonical preparation)
  ↓
EVIDENCE (scoped provenance, confirmation, freshness, conflicts)
  ↓
PLAN (objective, constraints, estimated costs and expected outputs)
  ↓
TASK GRAPH (bounded DAG, deterministic identities and dependencies)
  ↓
ROLE ROUTING (official system matrix)
  ↓
GUARDIAN (existing mission posture plus task policy checks)
  ↓
APPROVAL (explicit bool True, bound action/payload/scope/intent)
  ↓
READY_FOR_GUARDED_HANDOFF (metadata only, future executor gate required)
  ↓
STOP
```

`prepare_aion_orchestration` in the existing mission module lazily exposes
`prepare_taskgraph`. Planning, evaluation, explicit state transitions, handoff
and serialized recovery are pure local operations. Only
`persist_taskgraph(store, plan)` explicitly writes a local snapshot using the
existing V2.1D immutable journal store. It never writes Checkpoint Mestre,
promotes memory or starts a worker. No executor, provider or connector is called.

## Official matrix

`official_role_authority_matrix()` is authoritative; each of its eight rows
contains `role`, `capabilities`, `allowed_inputs`, `allowed_outputs`,
`forbidden_actions`, `requires_approval`, `escalation_target`, `audit_requirements`.
These are internal roles, not eight independent agents or models.

| Role | Capabilities | Escalation |
| --- | --- | --- |
| orchestrator — Orquestrador/Núcleo | route, coordinate, summarize | guardian |
| architect — Arquiteto/Estrategista | analyze, design, propose | guardian |
| guardian — Guardião/Auditor | audit, block, review | HUMAN_OWNER |
| prime — Prime/Execução | prepare_guarded_execution, draft_action_plan | guardian |
| shadow — Shadow/Pesquisa e Triagem | research, triage, cross_check | guardian |
| sentinel — Sentinel/Monitoramento | observe, alert, incident_triage | guardian |
| commercial — Comercial/Leads e CRM | qualify, draft_followup, crm_context | guardian |
| educator — Educador/Treinamento | explain, train, draft_learning_material | guardian |

All rows accept scoped request, scoped confirmed evidence and task dependencies.
Outputs are their capability proposals, local artifacts and audited proposals.
Forbidden actions are existing `CRITICAL_ACTIONS`: external_execution,
critical_approval, memory_promotion, automatic_checkpoint_write, merge_main,
deploy_production, spend_money, read_credentials, real_trade. Approval is required
for external intent, paid intent and scope change. Audit carries mission/task IDs,
scope/payload digests, transitions and approval digest. Prime prepares; it does
not execute. Guardian policy checks do not certify an external execution.

## Decomposition and deterministic routing

The commercial automation example decomposes into diagnóstico → levantamento →
proposta → configuração local proposta → plano de testes → revisão de aprovação →
handoff de implantação futura. The final CRM write intent starts disabled and
requires bound approval; the whole DAG can be inspected while blocked.
Configuration and tests are proposed tasks, not automatically performed actions.
Other objectives use a seven-task local template. Callers can supply bounded task
specifications with key, capability, title, dependencies, payload, evidence refs,
priority (0–100), estimated cost, and expected output. Roles, risk and approval
policy always come from the system catalog; freely supplied role and approval
fields are ignored. This is deterministic template decomposition, not an LLM or
a distributed scheduler. Priorities are metadata; DAG ordering is lexicographic.

Task IDs bind canonical mission ID, ecosystem and task key. Intent digest binds
the complete normalized request, evidence, constraints, specs, access role,
budget and flags. Identical logical requests preserve IDs and graph regardless
of specification ordering. Replay via `prior_plan` returns the exact prior state;
changed payload, scope or policy is rejected. Creation timestamps and inherited
V2.2A durable references are observational metadata, not logical identity.

## Mission and task lifecycle

Mission states remain PREPARED, WAITING_EVIDENCE, WAITING_APPROVAL, BLOCKED and
READY_FOR_GUARDED_HANDOFF. READY never means executed. Mission status summarizes
current unresolved task gates; recovery restores the stored status unchanged.
Explicit evaluation rechecks temporal evidence without mutating stored state.

Task states: PLANNED, QUEUED, RUNNABLE, WAITING_DEPENDENCY, WAITING_APPROVAL,
BLOCKED, COMPLETED, FAILED, CANCELLED, SUPERSEDED.

| From | Allowed next states |
| --- | --- |
| PLANNED | QUEUED, CANCELLED, SUPERSEDED |
| QUEUED | RUNNABLE, WAITING_DEPENDENCY, WAITING_APPROVAL, BLOCKED, CANCELLED, SUPERSEDED |
| RUNNABLE | COMPLETED, FAILED, WAITING_DEPENDENCY, WAITING_APPROVAL, BLOCKED, CANCELLED, SUPERSEDED |
| WAITING_DEPENDENCY / WAITING_APPROVAL | QUEUED, RUNNABLE, BLOCKED, CANCELLED, SUPERSEDED |
| BLOCKED / FAILED | QUEUED with explicit recovery reason, CANCELLED, SUPERSEDED |
| COMPLETED / CANCELLED / SUPERSEDED | terminal |

RUNNABLE and COMPLETED require satisfied gates. COMPLETED records a supplied
bounded local output, never executes a task; external intents cannot become
COMPLETED. Waiting states require their corresponding gate. Failure/blocking
requires a reason. Every mutation requires the current integer revision and adds
a bound audit entry; bool is rejected as a revision. Task state and revision must
match reconstructed audit history. EXECUTED and RUNNING are not valid states.

Cycles, missing dependencies, duplicate task keys/references, failed, blocked,
cancelled and superseded dependencies fail closed. Dependent tasks are eligible
only after local predecessor completion. There is no automatic scheduling.

## Approval and guarded handoff

`approve_task` requires `approved is True` and exact `approved_scope`.
`"true"`, `"yes"`, `"approved"`, `1` and other truthy values are rejected.
Receipt digest binds mission ID, task ID, capability, approval class, payload,
scope and complete intent. Changed payload, action or scope invalidates approval.
Repeated valid approval does not change state or audit.

Handoff fields: mission_id, task_id, capability, role, payload_digest,
scope_digest, approval_state, budget_state, risk_state, evidence_state, created_at,
idempotency_key, requires_downstream_execution_gate and false execution flags.
The risk label is `SYSTEM_POLICY_CHECKED_PLAN_ONLY`: system checks are not human
sign-off on actual execution. Handoff is allowed only for a RUNNABLE task with
satisfied gates. Repeated handoff returns the same logical object with no second
audit or dispatch. Replay rechecks gates, including evidence expiry and task
cancellation. A future executor must authenticate its caller, independently
recheck policy and enforce this idempotency key; none is connected here.

Trusted `access`, flags, budget and approval calls must originate in authenticated
application code, never be forwarded from arbitrary request JSON. Client
`authorization_context.role` and `source_context` role/system overrides are not
trusted. This module does not introduce or modify authentication/RBAC. SHA-256
digests detect changes and bind intent; they are not signatures and do not
authenticate an attacker who controls a whole document. Standalone recovery
requires an independently trusted `expected_digest`.

## Evidence and ecosystem isolation

Routes accept TRADER, NEGÓCIOS (canonical `NEGOCIOS`) and INVESTIMENTOS. Evidence
must explicitly match ecosystem, owner, tenant and workspace. Untagged legacy
evidence is excluded, not silently promoted. Cross-ecosystem or tenant evidence
is rejected. Commercial capabilities and CRM/email/WhatsApp intents are limited
to NEGOCIOS; real-order/broker intents are limited to TRADER. No shared memory
lookup or cross-context import happens automatically.

Required refs from both canonical mission and task must be individually
CONFIRMED under the existing truth engine. A reference alone, hypothesis, unknown
or stale evidence does not satisfy a gate. Conflicting evidence blocks the
mission. Freshness is checked again on explicit transitions and handoff replay.
Nothing in this layer independently verifies a caller's factual claims: evidence
must be supplied by the trusted provenance boundary.

## Budget, flags and invariants

Budget modes: ZERO_COST_LOCAL (default), FREE_TIER, PAID_ALLOWED, PAID_BLOCKED.
PAID_ALLOWED requires exact `paid_authorized is True`; otherwise it becomes
PAID_BLOCKED. Nonzero estimated total cost also needs an authorized limit covering
the whole graph and per-task bound approval. Free tier permits zero estimated
cost only. Estimates and authorization never trigger billing.

All nine future flags start False: provider_calls, external_email, whatsapp,
crm_write, calendar_write, payment_action, real_orders, broker_execution,
biometric_approval. Only exact True enables planning an intent past its feature
gate; it never enables execution or implements biometric authentication.

Across plans, tasks, audit and handoffs: external_action_executed=False,
execution_allowed=False, executes_provider_call=False, executes_billing=False,
real_orders_enabled=False, automatic_resume_executes=False.

## Recovery, storage and bounds

`export_taskgraph` / `recover_taskgraph` validate complete document digest, scope,
request fingerprint, official routing, policies, DAG, audit chronology and handoff
binding. Changed request action, attachments, evidence or mode is rejected.
Every task state, waiting approval, output, blocker, receipt and dependency is
restored exactly. No transition, approval, queue conversion or execution occurs.

`persist_taskgraph` stores explicit versioned snapshots as bounded base64 chunks
in `TASKGRAPH_CHECKPOINT` journal events. Encoding is transport, not encryption.
The established V2.1D chain and durability checks remain authoritative. Namespace
adds ecosystem to request ID. New process recovery reads the latest complete
snapshot; incomplete latest snapshot or quarantined journal blocks recovery and
never falls back to an older state. Stale snapshots and changed intent are
rejected. Local store root remains a trusted, access-controlled resource.

Limits: 32 tasks, 64 evidence rows/refs, 128 task audit entries, 128 KiB document,
4096-byte payload/output, 5 nested payload levels, 2000-character payload strings,
140-character request ID, 160-character conversation ID, 16 attachments.
Existing journal capacity remains 256 events; explicit persistence fails closed
when full. No compaction or automatic checkpoint rotation is added.

Real blockers include canonical mission policy, missing/unconfirmed/stale or
conflicting evidence, unmet/failed/superseded dependencies, disabled features,
paid budget, missing approval, malformed bounds, revision conflicts, corrupted
or incomplete recovery. Resolve them through new trusted input or explicit local
review; no hidden fallback invents evidence or grants authority.

## Validation

`test_atlasquant_aion_unified_taskgraph.py` covers system routing, forged context,
DAGs, transitions, bool-exact approval, modified payload/scope/request, duplicate
request/handoff, nine flags, budgets, all ten recovery states, local persistence
across store instances, stale/incomplete snapshots, freshness on replay,
structural forgeries, bounds and forbidden dispatch. Existing Core regression
and the Unified Core, Security Gate and Quality Tests workflows remain required.

Windows pytest temporary roots should use the `\\?\` extended path prefix for
existing journal-store tests. Some legacy tests require POSIX `/tmp`; authoritative
workflow execution remains Ubuntu. No test expectations are relaxed.
