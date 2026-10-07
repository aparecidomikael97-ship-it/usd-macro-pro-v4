# AION Chat — Postgres Migration + Health Fail-Closed Contract V1

## Purpose

Define how future production schema migrations and storage-health behavior must
work before a real Postgres chat adapter is allowed.

This is design/CI-only. It does not connect to Postgres or execute SQL.

## Migration rules

Production migrations must be:

- explicitly versioned;
- checksum-bound;
- serialized by a single migration writer/lock;
- tested against an isolated copy first;
- preceded by a recoverable database point;
- additive-first in V1;
- free of destructive V1 changes;
- compatible with an explicit schema version;
- equipped with a roll-forward remediation plan;
- executed only as a separate HUMAN_OWNER-authorized protected action.

The application must not silently auto-migrate production on startup.

## Health rules

Production chat durability is fail-closed.

Before a production chat host claims a durable turn:

1. database health must be known;
2. schema version must be compatible;
3. required scope/RLS policy health must be known;
4. the user turn must be durably persisted before any paid/external model call;
5. assistant persistence must be confirmed before the UI claims the response is saved.

If the database is unavailable or persistence outcome is unknown:

- do not report “saved”;
- do not silently fall back to session-only storage;
- do not fall back to the staging SQLite host;
- show an explicit degraded/unavailable state;
- retry only through idempotent keys and verified outcome handling.

## Why user persistence precedes provider calls

This ordering avoids paying for a model call when the system already knows it
cannot preserve the conversation turn. It also keeps audit/replay semantics
coherent.

This contract does not itself enable any provider.

## Maximum state

`READY_FOR_POSTGRES_MIGRATION_HEALTH_DESIGN_REVIEW`

## Next allowed step

`DESIGN_PRODUCTION_CHAT_POSTGRES_ADAPTER_CONTRACT`

No SQL, DB connection, migration, provider call, billing, deploy, Worker or
external-action authority is granted.
