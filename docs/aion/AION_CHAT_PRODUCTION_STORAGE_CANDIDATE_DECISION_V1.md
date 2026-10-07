# AION Chat — Production Storage Candidate Decision V1

Status: **RECOMMENDED_CANDIDATE_NOT_PROVISIONED**

Date: 2026-10-07

## Decision

Recommend **Render Postgres (paid, managed)** as the first production storage
candidate for AION Chat durable history.

This is a design recommendation only. It does not create a database, load a
secret, enable billing, change `render.yaml`, deploy, migrate data, or authorize
the Global Worker.

## Why this candidate is preferred

The current application already runs on Render. A managed Render Postgres
instance therefore minimizes operational surface and can be placed in the same
region as the application.

Current official Render documentation establishes:

- managed PostgreSQL;
- encryption at rest using AES-256;
- encrypted external connections using Render-managed TLS certificates;
- optional TLS for internal connections;
- continuous point-in-time recovery for paid instances;
- on-demand logical backups;
- private-network connectivity when colocated in the same Render region;
- flexible storage that can be increased over time.

For a production AION chat store, the final implementation must still prove the
full #978 attestation contract.

## Mandatory conditions before acceptance

Render Postgres is only a candidate until all of the following are proven:

1. paid/non-expiring production instance;
2. same-region placement with the AtlasQuant service;
3. encrypted transport for the application-to-database path;
4. owner / tenant / workspace scope binding in schema and queries;
5. default-deny authorization behavior;
6. migrations tested before production application;
7. health check and fail-closed behavior;
8. PITR available and a restore exercise actually tested;
9. retention and audit policy defined;
10. secrets injected outside source control;
11. no provider/model activation implied by storage readiness;
12. no deploy or Worker authority implied.

## Why not a Render Persistent Disk as the primary production record

Render persistent disks preserve filesystem changes across deploys/restarts and
are inexpensive, but the current AION durable chat implementation is SQLite and
the production contract requires explicit backup/restore, transport, isolation,
migration and operational attestations.

A persistent disk remains useful for local/self-contained workloads, but it
would leave more database operations in application ownership. Managed Postgres
is the safer default for the production conversation record.

## Alternatives retained

### Neon Postgres

Keep as a strong alternate for a low-cost/serverless Postgres path. It is not
selected in V1 because using the same Render platform reduces integration
surface for the first production activation.

### Supabase Postgres

Keep as an alternate when bundled platform capabilities become useful.
The current AION requirement is narrower than the extra platform surface.

## Cost posture

Use the smallest paid Render Postgres compute/storage configuration that meets
the attestation and workload requirements. Do not overprovision.

Pricing must be rechecked immediately before provisioning because infrastructure
prices can change.

## Required next step

`PROVE_RENDER_POSTGRES_ATTESTATION_WITHOUT_PROVISIONING`

That review must map Render Postgres evidence to every required field in:

- #978 Production Storage Attestation V1;
- #976 Production Chat Activation Contract V1.

Only after that evidence review may a separate owner-authorized provisioning
step be proposed.

## Non-authority statement

This document does **not** authorize:

- database creation;
- credentials/secrets;
- billing;
- migration;
- model/provider activation;
- deploy;
- Worker arming/activation;
- external actions;
- trading;
- Core writes.
