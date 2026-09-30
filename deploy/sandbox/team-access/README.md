# Team Access Physical Sandbox

Isolated non-production environment for the Business Team & Access E2E flow.

## Fixed sandbox stack

- Keycloak 26.7.5
- OpenID Connect
- PostgreSQL 18.6 for Keycloak persistence
- PostgreSQL 18.6 for the AtlasQuant team registry
- versioned registry schema: registry_revisions + team_memberships
- Keycloak Admin REST is the future revocation adapter boundary

This directory is not a production deployment bundle.

## Safety model

- host ports bind only to 127.0.0.1;
- start-dev is intentionally restricted to this local sandbox;
- no real secrets are committed;
- sandbox.env.local is ignored by Git through the repository .gitignore;
- launcher defaults to PLAN ONLY;
- starting containers requires explicit -Apply;
- deleting volumes requires -Apply -DestroyData -ConfirmDestroy;
- no client secret is embedded in the realm import;
- no production host, deploy hook or runtime flag is present here.

## Prepare on Windows PowerShell

From deploy/sandbox/team-access:

1. Copy sandbox.env.example to sandbox.env.local.
2. Replace every CHANGE_ME_... value with a distinct long random value.
3. Keep ATLASQUANT_SANDBOX_ONLY=true.
4. Ensure Docker Desktop / Docker Engine is available.
5. Run the launcher without -Apply first.

Plan only:

    .\Start-TeamAccessSandbox.ps1

Explicit sandbox start:

    .\Start-TeamAccessSandbox.ps1 -Apply

Read-only verification:

    .\Test-TeamAccessSandbox.ps1
    .\Test-TeamAccessRegistry.ps1

Stop and preserve data:

    .\Stop-TeamAccessSandbox.ps1 -Apply

Destroy only the local sandbox data:

    .\Stop-TeamAccessSandbox.ps1 -Apply -DestroyData -ConfirmDestroy

## What success means

A healthy compose stack only proves that the physical sandbox can run.
It does not prove the full Team Access E2E lifecycle.

The next validation must still create sandbox-only test evidence for:

- an individual account;
- strong MFA challenge;
- registry write + exact read-back digest;
- activation-review evidence;
- account disable;
- session revocation;
- inactive registry membership + read-back.

Those results are then supplied to
atlasquant_aion_business_team_access_sandbox_e2e.py.

## Production boundary

Never reuse this start-dev bundle for production. Production remains a separate
architecture and approval gate.

## Registry initialization note

The PostgreSQL official image runs init scripts only when the registry volume is empty. If the local sandbox volume already existed before the schema was added, destroy only the sandbox data with the guarded cleanup command and recreate it. Never do this against production data.


## Baseline evidence collection

After the sandbox is running and the two read-only verification scripts pass,
collect a sanitized baseline package:

    .\Collect-TeamAccessSandboxEvidence.ps1

The file is written under:

    .atlasquant_sandbox_evidence\team-access-baseline-evidence.json

That directory is ignored by Git. The collector writes no password, token,
client secret or authorization header.

Validate the package from the repository root:

    python validate_team_access_sandbox_evidence.py deploy/sandbox/team-access/.atlasquant_sandbox_evidence/team-access-baseline-evidence.json

A valid baseline can only reach:

    READY_FOR_ADMIN_TEAM_ACCESS_SANDBOX_LIFECYCLE_TEST_REVIEW

This does not authorize account creation, MFA enrollment, registry mutation,
session revocation or production. Those lifecycle actions remain manual sandbox
steps and must generate separate evidence for the E2E contract.


## Lifecycle authorization record

After a real baseline has been collected and the lifecycle plan has been built,
the next boundary is an explicit human authorization record. Start from:

    lifecycle-authorization-record.template.json

The record must be bound to the exact plan digest and baseline digest. Generic
phrases such as "ok", "pode seguir" or "vamos lá" are not authorization.

A valid future decision uses the exact token defined by ADR-0067:

    AUTHORIZE_TEAM_ACCESS_SANDBOX_LIFECYCLE_TEST

All acknowledgements must be true and the executor must remain disabled.

## Lifecycle evidence receipts

Each of the ten manual sandbox steps produces only a sanitized evidence digest.
Use the shape in:

    lifecycle-evidence-receipt.template.json

Receipts are chained in order. Step 1 starts from the 64-zero genesis digest;
every later receipt references the previous receipt digest. The ledger rejects
out-of-order steps, duplicate evidence or a broken chain.

The ledger never stores passwords, tokens, raw provider responses or production
credentials.


## Windows operator kit

The recommended local flow is now explicit and guarded.

Prepare a local secret file without displaying secret values:

    .\Prepare-TeamAccessSandboxEnv.ps1

The command above is PLAN ONLY. To create sandbox.env.local explicitly:

    .\Prepare-TeamAccessSandboxEnv.ps1 -Apply

Check readiness without starting containers:

    .\Get-TeamAccessSandboxReadiness.ps1

Run the combined operator in PLAN ONLY mode:

    .\Invoke-TeamAccessSandboxOperator.ps1

Explicitly start and verify the local sandbox:

    .\Invoke-TeamAccessSandboxOperator.ps1 -ApplyStart

Explicitly start, verify, collect and validate the sanitized baseline:

    .\Invoke-TeamAccessSandboxOperator.ps1 -ApplyStart -CollectBaseline

The readiness report is stored under
.atlasquant_sandbox_operator and that directory is ignored by Git.

The operator kit never performs any lifecycle step. Account creation, MFA,
registry writes, account disable and session revocation remain behind the
separate lifecycle authorization and one-step gates.
