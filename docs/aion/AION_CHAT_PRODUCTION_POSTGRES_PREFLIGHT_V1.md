# AION Chat — Production PostgreSQL Preflight V1

Status: DESIGN / CI-ONLY  
Date: 2026-10-07  
Depends on: PR #991 ephemeral PostgreSQL evidence and frozen Core V1  
Runtime/provider effect: NONE

## Purpose

Turn the next production-database step into an explicit fail-closed evidence gate before any provider mutation, migration, application connection, deploy, Worker activation or Core write is allowed.

This stage does not connect to Render or any other provider. It does not create a database, resolve credentials, execute SQL, apply a migration, change application configuration, deploy AtlasQuant, arm a Worker, execute an external action or mutate Core V1.

## Owner cost ceiling

The default monthly infrastructure ceiling enforced by this preflight is:

`R$ 200,00 / month`

A future provider plan may pass this gate only when the current price has been verified and normalized to BRL. If pricing is unknown, ambiguous or above the ceiling, the result is BLOCKED.

The policy itself does not fetch exchange rates and does not claim that any current provider plan satisfies the ceiling. Provider pricing must be freshly verified at the time of provisioning.

## Stage model

The evaluator can produce only four states:

1. `BLOCKED`
2. `READY_FOR_PROVIDER_PROVISIONING`
3. `READY_FOR_ISOLATED_MIGRATION`
4. `READY_FOR_CONNECTION_ATTESTATION`

None of these states authorizes deployment, Worker activation, external actions or Core changes.

### READY_FOR_PROVIDER_PROVISIONING

Requires at least:

- ephemeral PostgreSQL binding validated in CI;
- Core V1 freeze proven;
- provider identified;
- pricing freshly verified;
- normalized monthly cost at or below the owner ceiling;
- persistent production-suitable plan;
- private/internal connectivity supported;
- TLS supported;
- backup/recovery capability supported;
- no repository secret material;
- no out-of-band deploy/Worker/Core mutation.

This state means only that provider provisioning may be considered under the existing HUMAN_OWNER authorization boundary.

### READY_FOR_ISOLATED_MIGRATION

Requires a provisioned database plus evidence that:

- database region matches the application region;
- private/internal connectivity is enabled;
- public access is disabled;
- TLS is required;
- application role is least privilege and non-superuser;
- credentials are injected outside the repository;
- backup is enabled;
- a recoverable point is verified.

Only then may an isolated, separately reviewed migration step be considered.

### READY_FOR_CONNECTION_ATTESTATION

Requires, after migration:

- explicit migration version;
- non-empty migration checksum;
- checksum verification;
- compatible schema version;
- required constraint health;
- transaction health;
- scope-policy health;
- stable injected cursor-signing key;
- verified restore drill.

This state still does not authorize application deploy or production traffic. It means only that a later connection/host attestation may be performed.

## Hard blockers

The evaluator fails closed when any of the following is observed:

- monthly cost exceeds the owner ceiling;
- application DB role is superuser;
- secret material was committed to the repository;
- deploy happened outside this preflight;
- Worker was armed;
- Core V1 was mutated;
- provider/security/migration evidence is incomplete.

## Cursor key boundary

The PostgreSQL cursor implementation added to the ephemeral real-driver path requires a stable signing key of at least 32 bytes.

This preflight only asks for evidence that a stable key source exists after migration. It does not define or resolve the future production secret source and must never store the key in repository code or chat database rows.

## Migration boundary

Production startup must not auto-migrate.

Migration remains:

- versioned;
- checksum-bound;
- additive-first;
- executed through a protected action;
- recoverable;
- fail-closed on unknown outcome.

This preflight does not apply SQL.

## Provider-neutral evidence

The code intentionally uses generic evidence fields rather than a Render-specific API shape. Render remains the currently preferred candidate from the earlier storage decision work, but provider-specific facts such as plan price, region, private networking and backup capabilities must be verified live before they are accepted as evidence.

## Maximum truthful state

This branch may claim only:

`PRODUCTION_POSTGRES_PREFLIGHT_POLICY_VALIDATED_IN_CI`

It must not claim:

- production database provisioned;
- production database connected;
- production credentials configured;
- production migration applied;
- restore drill completed;
- application bound to production storage;
- deploy completed;
- Worker active.

Core V1 remains frozen.

## Next external step

When the HUMAN_OWNER has convenient desktop access, the pending provider-authenticated step can resume:

1. authenticate to the Render dashboard;
2. verify current plan/price and app region;
3. evaluate the evidence through this preflight;
4. only if the gate returns `READY_FOR_PROVIDER_PROVISIONING`, create the database under the owner-approved cost ceiling;
5. stop before migration until the provisioned security evidence is complete.
