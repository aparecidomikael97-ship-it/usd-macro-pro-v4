# AION Core Intelligence — application layer

Entry point: `atlasquant_aion_core_intelligence.service.AionCore`.
This is an opt-in local application service, not an executor or an active UI
integration. Existing Core, capability, truth, research-planning, Developer
Engine and observability primitives are reused without modifying their files.
No security-chain module is imported or replaced.

## Scope and availability

The registry reports ADMINISTRATION, MEMORY, DEVELOPER, RESEARCH, VOICE,
CONTENT, AUTOMATION, OBSERVABILITY and three disabled future capabilities.
BUSINESS_FUTURE, TRADER_FUTURE and INVESTMENTS_FUTURE cannot be dispatched.
Voice and scheduling remain unavailable because no adapters are connected.
AVAILABLE means the named local data-only function is implemented, never
that a provider, voice service, scheduler, GitHub feed or deployment is live.

Intents are matched using the existing capability metadata model. Ambiguous
requests require clarification; unknown requests stay UNKNOWN. Administration,
Developer and Content require ADMIN. A request routed to a different domain
returns CONTEXT_SWITCH_REQUIRED instead of reading another task's memory.

## Context and trust boundary

The host must authenticate tenant, workspace, actor and role before creating a
Context. These fields are not credentials and must never be copied from a
model response or an untrusted HTTP body. Task ID and domain are also part of
the exact scope key. There is no implicit cross-task or cross-tenant recall.
ScopedEvidence binds supplied observations to that same scope.

The package cannot authenticate an external source from a URL string. Evidence
classification is a declaration from the caller's trusted ingestion adapter.
Source and reference are required for factual use; timestamps and positive TTLs
are required for temporal evidence. Future timestamps, missing provenance,
stale evidence and conflicts cannot become current confirmed facts. Research
returns a sourced inventory, not a claim that it answered or verified the
whole question. Human approval is not factual evidence.

## Persistent checkpoint

CoreStore opens only the explicit local SQLite path supplied by the host. It
does not create parent directories, access credentials, fetch remote data or
write the legacy runtime checkpoint. Database open errors propagate; there is
no silent in-memory fallback. `:memory:` is explicitly reported as EPHEMERAL.

Records cover decisions, requirements, priorities, current state, completed
tasks, pending tasks and evidence. Each has a source, references, timestamp,
version and origin: USER_APPROVED, SYSTEM_OBSERVED, INFERRED or UNKNOWN.
Updates append versions; older records remain in history. Writes use an
expected checkpoint revision in a transaction to reject concurrent stale
writers. Latest versions are returned on normal reads; historical versions
are available through history/checkpoint export.

USER_APPROVED requires a persisted, unexpired, unused human approval bound to
the exact record content, kind, evidence references and context. Inference
cannot promote itself, and an edited approved record needs a new approval.
Approval consumption and memory append share one SQLite transaction.

The checkpoint digest detects accidental changes; it is not a signature or a
root of trust. A writer with direct database access is outside this boundary.
The host owns database access permissions, encryption, retention and backups.
The journal stores only bounded event metadata, never prompts, code, exception
messages or approval receipt contents. Memory text uses the shared redactor
with additional private-key and credential-URL filtering; arbitrary secrets
cannot be identified reliably and should not be submitted to memory.

`adapters.attach_checkpoint` returns a namespaced export proposal without
mutating the legacy checkpoint. It does not save, restore approvals, or merge
different contexts. Remote persistence stays UNAVAILABLE until an explicit
host adapter saves and verifies it. Legacy memory import proposals remain
UNKNOWN until reviewed, regardless of old CONFIRMED/approved flags.

## Human approval contract

Publication, external changes, payments, financial changes, deploy and market
operations have a shared PENDING/APPROVED/REJECTED/EXPIRED contract. This sprint
implements state recording only. Even APPROVED has execution_authorized=False.
No public method executes an approved action.

No default approval verifier exists. The host must implement HumanApprovalAdapter
and verify an authenticated human receipt bound to context, approval ID, action,
subject digest and decision. Intent text such as "approved" is not a receipt.

## Local service behavior

- Administration reports supplied health, PR/build/test status, integrations,
  changes and errors. Missing sources produce UNKNOWN with a reason. Pending
  tasks are explicitly a scoped inventory, not the complete system workload.
- Developer parses supplied Python with AST, identifies review points, compares
  symbols/syntax and records PASS-to-FAIL evidence only when each test report
  matches the respective source digest. It never imports or executes the code,
  runs tests, or claims that static inspection proves absence of regressions.
- Developer planning calls the existing Developer Engine. The future security
  chain adapter remains UNAVAILABLE; Builder through Probe Result is untouched.
- Research reuses the existing research plan and truth assessment. It performs
  no web or model call and keeps facts, inferences, unknowns and conflicts apart.
- Content prepares a SCRIPT_OUTLINE draft. It does not generate full media,
  verify factual content or publish anything.

## Minimal host example

```python
from atlasquant_aion_core_intelligence.context import Context, Domain
from atlasquant_aion_core_intelligence.service import AionCore
from atlasquant_aion_core_intelligence.store import CoreStore

# Values must come from the host's authenticated session, not user input.
context = Context("tenant-a", "workspace-a", "human-a", "task-a", Domain.ADMIN, "ADMIN")
with CoreStore("aion-core.sqlite") as store:
    core = AionCore(store)
    result = core.handle("AION, qual o estado do sistema?", context)
    # External system status is UNKNOWN until scoped evidence is supplied.
```

## Tests and future integration

Run `python -m unittest -v test_atlasquant_aion_core_intelligence` and the
repository quality suite. The new test is registered in quality-tests.yml.
No test requires a provider, real account, network access or physical probe.

Next application blocks: authenticated UI integration, host human-approval
verification, verified status/evidence ingestion, and legacy checkpoint storage
adapter with backup/restore policy. Voice and scheduling require real adapters
before availability may change. No Business, Trader or Investments work is
enabled by this package. Removing the opt-in facade restores the prior behavior;
existing callers and runtime checkpoint files are unchanged.
