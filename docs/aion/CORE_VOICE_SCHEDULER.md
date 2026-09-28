# AION Core — Voice + Scheduler Adapter V1

This block connects AION Core Intelligence to two capabilities that already
exist or are needed in the AtlasQuant runtime:

1. the official AtlasQuant neural voice status/preparation path;
2. a persisted schedule registry stored in the Checkpoint Mestre.

The block intentionally does not connect a background executor.

## Voice adapter

The Core receives the status of the existing AtlasQuant neural voice layer.

When the provider is not configured:
- VOICE stays UNAVAILABLE;
- no browser/device voice fallback is activated;
- text remains available.

When the provider is configured:
- VOICE becomes available to the Core;
- the exact transcript is validated locally;
- a deterministic cache digest can be prepared;
- no provider call is made by the Core;
- audio generation remains on the existing explicit AtlasQuant voice button.

The Core adapter never calls `generate_neural_speech`, never performs network
I/O and never changes trading state.

A configured provider means **ready for explicit use**, not that a paid call
has already happened.

## Scheduler adapter

The scheduler supports persisted definitions for:

- ONCE;
- HOURLY;
- DAILY;
- WEEKLY.

Every schedule records:
- title;
- prompt/instruction;
- cadence;
- timezone;
- hour/minute;
- weekday when applicable;
- one-shot timestamp when applicable;
- authenticated creator;
- state;
- digest.

The application clock uses the same `ATLASQUANT_TIMEZONE` policy already used
by AION. Invalid timezone names fail back to the existing application default.

## Due-state semantics

The scheduler can calculate:
- next run;
- whether a schedule is due/overdue.

It does **not** execute the prompt.

A newly-created recurring schedule is not considered overdue for an occurrence
that happened before the schedule was created.

A one-shot schedule must be in the future when it is staged.

## Persistence

Schedules are stored under:

`aion_core_scheduler_v1`

inside the existing Checkpoint Mestre.

Creating a schedule only changes the working checkpoint. External durability
still requires the existing explicit **Salvar Checkpoint Mestre no runtime**
flow and Guardian checks.

The schedule namespace:
- has its own digest;
- participates in master checkpoint integrity;
- participates in the checkpoint source/conflict digest;
- is carried by the existing version history and rollback path.

A tampered scheduler bundle changes the master checkpoint integrity to
`MISMATCH` and blocks the save gate.

## Execution boundary

This block deliberately reports:

- `execution_adapter = UNAVAILABLE`;
- `automatic_execution = false`;
- `execution_authorized = false`;
- `external_action_executed = false`.

Therefore "scheduled" means the AION has a durable time definition and can tell
when work is due. It does not mean a worker is running in the background.

A future executor must be a separate adapter with:
- authenticated authority;
- Guardian approval;
- idempotency;
- retry policy;
- observable receipts;
- explicit external-action rules;
- no trading/payment/publication authority by default.

## Cost and safety

No new paid service is activated by this block.

The scheduler performs no network calls, subprocesses, deploys, publications,
payments or market operations.

The voice adapter performs no provider call. Existing neural audio generation
remains an explicit user action on the pre-existing voice surface.

Real trading remains disabled.
