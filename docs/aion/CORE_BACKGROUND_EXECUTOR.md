# AION Background Executor V1

This block adds a controlled execution kernel for due AION schedules.

The name "background executor" describes the execution layer that future
workers can call. **V1 is not an autonomous daemon.** It runs only after an
authenticated ADMIN explicitly confirms and clicks the execution control in
the Central AION UI.

## Scope

The executor can run only these local Core capabilities:

- ADMINISTRATION
- MEMORY
- RESEARCH
- VOICE
- CONTENT
- OBSERVABILITY

Every schedule must bind an explicit capability. Legacy/unbound schedules are
blocked rather than guessed from natural language.

DEVELOPER, AUTOMATION recursion, BUSINESS, TRADER and INVESTMENTS are not in
the executor allowlist.

## Guardian

Each due occurrence passes through the existing AtlasQuant Guardian:

- read-only modules use Guardian action `read`;
- draft-only modules use Guardian action `draft`;
- ADMIN authentication is required;
- unknown or non-allowlisted capabilities fail closed.

Prompts containing sensitive intent markers for publication, external changes,
payments, financial changes, deploy or market operation are blocked before the
Core handler is called.

Human confirmation and Guardian are separate boundaries. The checkbox/click
authorizes only the current local batch. It never grants authority for external
or physical actions.

## Idempotency

Each occurrence receives an idempotency key derived from:

- exact authenticated context;
- schedule fingerprint;
- due timestamp.

The schedule fingerprint includes the schedule ID, title, prompt, capability,
cadence, timezone and timing fields.

Once a receipt for an occurrence reaches `SUCCEEDED` or `BLOCKED`, that
occurrence will not be executed again.

A recurring schedule creates a new occurrence key for the next due timestamp.

## Retry policy

Only exceptions from the local Core handler are retryable.

- maximum attempts: 3;
- attempt 1 backoff: 60 seconds;
- attempt 2 backoff: 300 seconds;
- attempt 3 is terminal for retry purposes.

There is no tight automatic retry loop. A later explicit executor invocation
may retry after the backoff expires.

Blocked work is not retried automatically.

## Receipts

Receipts are staged under:

`aion_core_executor_v1`

inside the existing Checkpoint Mestre.

Each receipt contains:

- deterministic receipt ID;
- occurrence key;
- schedule ID and fingerprint;
- due time;
- capability;
- attempt;
- state: SUCCEEDED / FAILED / BLOCKED;
- Guardian action/risk/decision;
- authenticated human principal;
- confirmation digest;
- result status/digest;
- bounded redacted result preview;
- retry-after when applicable;
- safety flags.

Receipt data never changes external systems.

## Checkpoint integrity

The executor namespace has its own digest and is included in the master
checkpoint integrity report.

If executor receipts are tampered with:

- executor integrity becomes `MISMATCH`;
- master checkpoint integrity becomes `MISMATCH`;
- the normal Checkpoint save gate blocks external persistence.

The executor namespace also participates in the checkpoint conflict digest and
therefore travels with normal backup/version history/rollback.

## UI behavior

The Central AION shows:

- number of due jobs;
- receipt count;
- autonomous worker status;
- physical-action adapter status;
- recent receipts;
- maximum batch size;
- explicit confirmation checkbox;
- **Executar trabalhos locais devidos agora** button.

A successful local run stages receipts in the working checkpoint. External
durability still requires the existing explicit **Salvar Checkpoint Mestre no
runtime** flow.

## What V1 does not do

V1 does not:

- start a daemon or cron worker;
- poll continuously;
- make HTTP/network calls from the executor;
- call a model provider;
- generate neural audio;
- execute subprocesses or shell commands;
- publish social/media content;
- publish marketplace content;
- move money or charge customers;
- deploy production;
- merge branches;
- place market orders;
- enable real trading.

All such actions remain outside this executor and require separate, explicit,
auditable adapters and approvals.

## Future autonomous worker gate

A future autonomous worker may call this kernel only after a separate design
adds, at minimum:

- authenticated worker principal;
- durable lease/claim semantics;
- concurrency control;
- crash recovery;
- observable heartbeat;
- bounded retry queue;
- operator pause/kill switch;
- per-action approval contracts;
- cost controls;
- no real trading/payment/publication authority by default.

Until then:

`manual_invocation_only = true`

`autonomous_worker_connected = false`
