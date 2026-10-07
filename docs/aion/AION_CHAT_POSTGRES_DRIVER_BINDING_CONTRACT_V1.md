# AION Chat — Real Postgres Driver Binding Contract V1

## Purpose

Define how a real Postgres driver may later be introduced without coupling
secrets, environment access, provider logic or production authority into the
chat store.

This contract installs no driver and opens no connection.

## Planned binding

V1 plans a synchronous **psycopg 3** binding because the current Streamlit and
AionChatStore paths are synchronous. The exact pinned version must be selected
and security-audited in a future implementation PR.

The store remains driver-agnostic. A composition root will eventually receive a
safe descriptor and construct the binding.

## Secret boundary

- platform-managed secret injection only;
- no secret read at module import;
- store never reads environment variables;
- no DSN/password in source, logs or UI;
- descriptor contains a secret reference only;
- credential rotation does not require a code change.

## Network and connection posture

- internal/private endpoint only by default;
- public/external endpoint default-deny;
- no automatic public fallback;
- TLS required;
- no SQLite production fallback;
- autocommit disabled;
- bounded connect and statement timeouts;
- explicit application name;
- least-privilege non-superuser role;
- no auto-migration on connection/startup;
- health, schema compatibility and scope-policy health before use.

## Observability

Allowed: state, latency, error class and safe internal scope identifiers.
Forbidden: message content, DSN, password and secret material.

## Maximum state

`READY_FOR_REAL_POSTGRES_DRIVER_BINDING_IMPLEMENTATION_REVIEW`

## Next allowed step

`IMPLEMENT_DRIVER_BINDING_WITH_NO_PRODUCTION_CREDENTIALS`

That step may add a pinned driver and non-production factory, but still may not
receive real production credentials or connect to a real production database.
