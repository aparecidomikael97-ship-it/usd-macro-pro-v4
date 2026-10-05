# AION Tool Governance Gateway P1

Status: **staging hardening / authority-free preflight**.

## Objective

Create one governance chokepoint immediately before any tool executor without
creating a second executor or bypassing the existing AION security layers.

The gateway composes the existing:

- Tool Hub preflight;
- closed tool supply-chain registry;
- sandbox / egress profile;
- Guardian proof of safety;
- trusted tenant/workspace scope;
- trusted granted scopes;
- explicit human approval references;
- cumulative authority budget evidence;
- rollback / recovery reference;
- execution receipt obligation.

## Non-execution boundary

The gateway does not:

- call a tool;
- call a connector;
- resolve a credential;
- call a provider;
- open network sockets;
- start a subprocess;
- mutate production;
- merge or deploy;
- trade;
- execute a payment.

`READY_FOR_EXECUTOR` means only that an immutable handoff envelope can be
constructed for a later executor.

It does **not** grant authority.

The executor must revalidate the envelope and all live gates immediately before
the external boundary.

## Trusted scope

The gateway receives a trusted:

- owner_id;
- tenant_id;
- workspace_id.

A tool whose declared workspace differs from the trusted workspace is blocked.

This prevents a tool approved in one workspace from being silently reused in
another workspace or tenant context.

## Scopes

Required tool scopes come from the closed Tool Hub contract.

Granted scopes come from a separate trusted host input.

A missing required scope blocks the handoff.

The gateway cannot expand scopes and tool output is never authority.

## Transport binding

Supported transport labels are:

- LOCAL;
- NATIVE;
- API;
- MCP;
- FILE;
- WEBHOOK.

A local tool must use LOCAL.

An external connector-bound tool must match the connector protocol recorded in
the normalized Portable Core.

Transport mismatch blocks before an executor.

## Tool Hub state

Only `READY_FOR_EXECUTOR` from the existing Tool Hub may proceed.

`REVIEW` remains human review.

The governance gateway must never upgrade a Tool Hub `REVIEW` state into an
executor-ready state.

## Sandbox and supply chain

The tool contract must remain supply-chain VERIFIED and its sandbox plan must be
READY.

The gateway preserves the existing rules for:

- contract/schema pins;
- owner/version pins;
- connector binding;
- credential boundary;
- egress allowlist;
- SSRF controls;
- local no-egress tools.

## Side-effect tools

A tool is treated as side-effecting when:

- its contract declares `external_side_effects=true`; or
- its kind is WRITE, PUBLISH, FINANCIAL, PRODUCTION or SECRETS.

Before a side-effect tool can produce a handoff, all are required:

- `approved is True` exactly;
- at least one approval reference;
- at least one evidence reference;
- rollback or recovery reference;
- authority budget reference;
- verified cumulative authority budget evidence bound to the same transaction,
  owner, tenant and workspace.

Truthy strings such as `"true"` do not count as approval.

## Financial / production / secrets

FINANCIAL, PRODUCTION and SECRETS are critical tool kinds.

They additionally require an authenticated administrator context before a
handoff can even be produced.

The gateway itself still does not authorize or execute the action.

Any action classified CRITICAL by the cumulative-authority budget remains
blocked by the separate human gate already defined by that component.

## Authority budget binding

Budget evidence must prove:

- allowed=true;
- grants_authority=false;
- executes_action=false;
- exact transaction_id;
- exact authority_budget_ref;
- exact owner/tenant/workspace scope;
- policy version;
- policy digest.

The gateway never records authority spend. Confirmed effects continue to be
recorded by the existing durable authority ledger at the execution/outbox
boundary.

## Handoff digest

A deterministic SHA-256 handoff digest binds:

- policy version;
- transaction;
- tool and kind;
- transport and connector;
- trusted scope;
- required/granted scopes;
- tool contract hash;
- sandbox profile;
- authority budget ref;
- approval refs;
- evidence refs;
- rollback/recovery ref;
- side-effect posture.

Changing an approval reference, scope, tool contract, transport, budget or
recovery reference changes the digest.

## Receipt obligation

Every `READY_FOR_EXECUTOR` handoff has `receipt_required=true`.

The existing Action Receipt / receipt bridge remains the receipt system.
The gateway does not mint a fake execution receipt before execution.

## Fail-closed summary

The gateway blocks on:

- invalid trusted scope;
- invalid transaction;
- unsupported transport;
- Tool Hub BLOCK;
- Tool Hub REVIEW;
- workspace mismatch;
- missing scope;
- transport mismatch;
- sandbox failure;
- missing approval/evidence/recovery data for side effects;
- missing or mismatched authority budget evidence;
- source without command authority;
- Guardian proof-of-safety block;
- unverified supply chain;
- any evidence that the preflight itself already executed a tool/connector.

## P1 explicit non-goals

This P1 does not enable a real MCP server or external connector.

It does not replace:

- Tool Hub;
- Tool Supply Chain;
- Credential Proxy;
- Execution Outbox;
- Saga Coordinator;
- Cumulative Authority Budget;
- Guardian;
- Action Receipt.

It is the governance composition layer above those contracts.
