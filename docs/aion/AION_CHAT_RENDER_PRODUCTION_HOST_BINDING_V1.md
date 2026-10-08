# AION Chat — Render Production Host Binding V1

Status: IMPLEMENTATION SAFE / ACTIVATION OFF BY DEFAULT  
Date: 2026-10-07  
Depends on: Render Production PostgreSQL Composition V1  
Deployment status: NOT DEPLOYED by this change

## Purpose

Connect the real Streamlit host composition to the reviewed production
PostgreSQL store without changing the default behavior until an explicit
activation flag is enabled.

The production binding has priority only inside the AION area and only when:

`AION_CHAT_PRODUCTION_PERSISTENCE_ENABLED=true`

If that flag is absent or false, the production binding returns `None` and the
existing staging/default path remains unchanged.

## Trusted owner scope

Production persistence requires:

- an authenticated access decision;
- ADMIN role on both access decision and session;
- authenticated username;
- valid credential fingerprint;
- existing `app:read` and `aion:admin` permissions;
- explicit tenant id;
- explicit workspace id.

The two non-secret scope keys are:

- `AION_CHAT_PRODUCTION_TENANT_ID`
- `AION_CHAT_PRODUCTION_WORKSPACE_ID`

No tenant/workspace is inferred from browser input.

## Streamlit configuration boundary

The host is allowed to resolve only the approved AION Chat keys from Streamlit
secrets / process environment.

The store/backend still performs no environment lookup itself.

Approved keys:

- `AION_CHAT_PRODUCTION_PERSISTENCE_ENABLED`
- `AION_CHAT_PG_HOST`
- `AION_CHAT_PG_PORT`
- `AION_CHAT_PG_DATABASE`
- `AION_CHAT_PG_USER`
- `AION_CHAT_PG_PASSWORD`
- `AION_CHAT_PG_SSLMODE`
- `AION_CHAT_CURSOR_SIGNING_KEY`
- `AION_CHAT_PRODUCTION_TENANT_ID`
- `AION_CHAT_PRODUCTION_WORKSPACE_ID`

## Production precedence

When the requested central area is AION:

1. try production binding;
2. if production activation is OFF, try the existing staged binding;
3. if both are OFF, preserve the existing default/session path.

Production and staging are therefore not simultaneously selected.

## Runtime safety posture

The production host runtime context explicitly keeps:

- external provider execution disabled;
- Worker disabled;
- external actions disabled;
- Core mutation disabled.

The production store itself is still protected by its own least-privilege,
forced-RLS and health gates.

## Activation boundary

Saving environment variables with Render `Save only` does not activate the
store.

Activation requires all of the following:

1. this host binding and the production store composition are green in CI;
2. required scope values are present;
3. the stable cursor signing key is present;
4. the activation flag is explicitly set true;
5. the code that contains this host binding is deployed;
6. post-deploy health is attested.

The activation flag must remain absent/false until the HUMAN_OWNER separately
authorizes deployment/activation.

## Explicitly absent

This change does not:

- deploy AtlasQuant;
- change Render environment values;
- activate production persistence;
- run a database migration;
- reactivate the sealed migration user;
- activate a Worker;
- execute external provider actions;
- mutate Core V1.

## Maximum truthful state

After green CI:

`RENDER_PRODUCTION_HOST_BINDING_VALIDATED_IN_CI`

This is not production activation.
