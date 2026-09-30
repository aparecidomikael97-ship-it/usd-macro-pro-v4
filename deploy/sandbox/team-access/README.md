# Team Access Physical Sandbox

Isolated non-production environment for the Business Team & Access E2E flow.

## Fixed sandbox stack

- Keycloak 26.7.5
- OpenID Connect
- PostgreSQL 18.6 for Keycloak persistence
- PostgreSQL 18.6 for the AtlasQuant team registry
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
