# AION Tool Supply Chain / Credential Boundary V1

Status: **staging hardening only**.

This block closes the logical supply-chain and credential boundary identified by
the independent red-team review. It does not activate an external tool.

## Closed inventory

The existing Tool Hub remains the catalog. A tool is not approved merely because
a runtime object appears in `hub["tools"]`.

Every approved tool now has a pinned contract containing:

- tool id;
- owner;
- semantic version;
- workspace and connector binding;
- kind and Guardian action;
- required scopes;
- external-side-effect declaration;
- input/output schema;
- implementation reference;
- eval profile;
- credential reference and credential scopes;
- sandbox profile;
- egress allowlist;
- third-party flag.

The contract is hashed. The closed registry itself also has a pinned digest.
Changing schema, version, owner, implementation, scopes, sandbox or egress
policy without the explicit pin update produces `TOOL_CONTRACT_DRIFT` and
blocks the Tool Hub preflight.

Runtime insertion of an unknown tool produces
`TOOL_NOT_IN_CLOSED_REGISTRY`.

## Staging credential probe

The registry includes one deliberately **DISABLED** staging-only external
contract, `aion.staging.credential_probe`.

It exists only to exercise supply-chain, Vault, proxy and SSRF tests. It is
**not persisted in the default Tool Hub at all**. That preserves historical
Checkpoint Mestre digests and also means the normal AION runtime cannot discover
or plan this probe as a tool.

- its reviewed fixture state is `DISABLED`;
- it is absent from the default runtime Tool Hub;
- no connector is activated;
- no handler is added to the local executor;
- no network client exists in the proxy/sandbox modules.

Supply-chain metadata is a security overlay derived during preflight. The
persisted Tool Hub keeps its compact legacy shape, so older checkpoint digests
remain valid while execution still sees owner/version/schema/hash/sandbox pins.

## Vault least privilege

A `SECRET_REF` can now declare:

- `allowed_tool_ids`;
- `credential_scopes`;
- whether the reference is least-privilege scoped.

The Vault still stores only a locator/reference. It never stores the secret
value.

Unscoped legacy secret references remain representable for compatibility, but
the credential proxy refuses them.

## Opaque credential proxy

The model-facing side receives a short-lived one-shot opaque handle only.

A secret value is not resolved until all of the following pass:

1. tool registry state is VERIFIED;
2. tool contract hash equals its pinned hash;
3. Vault entry is ACTIVE, SECRET_REF and least-privilege scoped;
4. requested scopes fit both the tool contract and the Vault grant;
5. Tool Hub preflight is READY_FOR_EXECUTOR and bound to the same contract;
6. connector activation is present in that preflight when required;
7. sandbox/egress validation passes after DNS resolution.

After secret materialization, the handle is consumed even if the adapter fails.

If the callback attempts to return the secret or a secret-like field, the proxy
raises a credential leak error instead of returning the result.

No real secret backend resolver is implemented in this block. The resolver is
an injected boundary used only by red-team tests.

## SSRF / egress policy

Credential-bearing third-party tools use
`THIRD_PARTY_EGRESS_PROXY`.

The guard requires:

- HTTPS;
- port 443 only;
- exact hostname allowlist;
- no URL userinfo;
- no direct-IP destination;
- no numeric IP aliases;
- explicit post-DNS resolved-IP proof;
- every resolved address must be globally routable.

Therefore loopback, RFC1918/private, link-local, metadata-service,
non-global IPv6 and DNS-rebinding-to-private cases fail closed.

## Local executor

The local executor remains a separate closed handler table and still has no
requests/socket/subprocess/importlib/eval/exec path. Boolean authorization
arguments are now forwarded with exact `is True` semantics rather than truthy
coercion.

The local traceability fingerprint now includes the tool owner/version,
schema/contract hash, implementation reference, sandbox profile, credential
binding and egress allowlist.

## Red-team proof

The new tests cover:

- closed registry digest;
- all default tools supply-chain verified;
- schema drift;
- owner/version/scope drift;
- runtime tool injection;
- schema-hash spoof attempts;
- disabled staging probe cannot execute;
- public allowlisted egress;
- loopback/private/link-local/metadata SSRF;
- DNS rebinding;
- URL userinfo confusion;
- HTTP/custom-port/unlisted-host rejection;
- Vault least privilege;
- opaque handles;
- no secret resolution before preflight + egress;
- wrong/mismatched preflight;
- handle expiry and one-shot use;
- callback credential exfiltration;
- absence of built-in network clients.

## Explicitly still absent

This is **not yet an OS/process sandbox**.

Before any real third-party tool is enabled, production still needs an actual
process/container boundary with constrained filesystem, syscalls, CPU/memory,
network namespace/egress proxy and independently managed credential backend.

Also still disabled:

- real MCP/API external execution;
- real secret resolution;
- production provider activation;
- production persistence;
- autonomous external-action worker;
- deploy/merge/trading/payment authority.
