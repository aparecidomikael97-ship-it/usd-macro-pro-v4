# AION P0 / H0 — Evidence gates for independently controlled witness roles (LAB)

Date: 2026-10-20. This document defines **future evidence acceptance criteria**, not procurement, enrollment, deployment, verified external identity or authority to perform first effects.

## Verified baseline before this proposal

- Parent Draft #1380 at cc76b539 verified **two Ed25519 signatures under caller-provided keys**, transcript bindings and hostile-input denial. This only establishes mathematical validity under a synthetic fixture.
- H0 custody two-domain SQLite model demonstrates local CAS and how rollback of **both** local domains can erase the apparent high-water mark.
- Canonical Quality baseline on parent remains **52 FAIL / 34 ERROR** (86 historical occurrences); Security A74 365 PASS and H0 A79 64 PASS do not erase Quality RED.
- **HARD NO-GO / 0 of 6 P0 homologated / Worker OFF / ZERO_AUTO_RESEND.**

## LAB authority-control graph added here

The module \`atlasquant_aion_p0_h0_authority_graph_lab.py\` inspects a **proposed**, entirely caller-supplied map of six conceptual roles: executor, reservation signer, readback witness, nonce custodian, head issuer and independent verifier.

The strict model checks for identical declared security domains, accounts, organizations, key fingerprints, direct admin/recovery/deployment/billing controllers and shared **transitive** control roots in delegation chains. Invalid shapes, hostile objects, duplicate identities and cycles fail closed. The conservative six-way role separation is an **adversarial analytical assumption, not an instruction to buy six accounts or six services**; actual infrastructure design must be risk- and cost-reviewed later.

A packet with all distinct identities is merely \`claimed_topology_consistent_lab=True\`. This is **not** \`administrative_independence_authenticated\`. A caller may omit an admin, cloud root, password-reset path, MFA recovery channel, account ownership, reseller or management plane. An internally consistent graph never proves the absence of hidden edges, external enrollment, or trustworthiness of submitted facts. No output allows a Worker, outbox dispatch, auto-retry or any first effect. Do not import the module into an authorization path.

## Independent evidence required outside LAB, in sequence

| Gate | Evidence required | Reject if |
| --- | --- | --- |
| E0 — operator map | Independently inspected legal/administrative account ownership, super-admins, MFA/recovery roots, deployment and billing authorities, explicit transitive delegations, least-privilege grants | Same principal can reset or overwrite both executor and witness, or graph comes solely from executor |
| E1 — issuer enrollment | Owner-approved out-of-band public-key fingerprints, verified account/issuer identity, key epochs and signing scopes in independently protected trust registry | Key pinned by caller in same request, \`verified=true\` flag, or certificate with unverified chain |
| E2 — revocation and rotation | Authenticated current revocation status and key-rotation ordering read from issuer outside rollback domain | Unknown, timeout, missing epoch, unverified old key, fork |
| E3 — challenge custody | Independently generated unpredictable nonce, atomic unique reservation/consumption and off-host durability; request/scope/intent/epoch bound | Duplicate/expired nonce, local-only cache, self-issued challenge or uncertain durable acknowledgement |
| E4 — latest head readback | Authenticated independent **current/latest** high-water/sequence/epoch and precise version ID readback with append chain, fork/gap and rollback checks; trusted freshness | Old signed historical head presented as latest, missing version, partial timeline, expired challenge |
| E5 — first attempt causality | Durable reservation before any producer effect; independent proof of what was submitted and when; effect-originating provider receipts for \`COMMITTED_EFFECT\` or a separately evidenced \`NO_EFFECT_FENCED\` | Receipt from AION itself, timeout interpreted as no effect, write/readback uncertainty |
| E6 — physical recovery | Independent destructive-restore exercises covering local disk, executor, one witness domain, both witness domains, admin/MFA reset and loss of readback service | Any undetected rollback, unsafe fallback, restart enabling a second attempt |
| E7 — final gates | HUMAN_OWNER identity/consent verified separately, original Quality and Security audited, all six P0 closed with independently inspected evidence | Any unresolved P0, quality error without formal resolution, missing review |

## Invariants at every gate

1. \`UNKNOWN\` remains \`UNKNOWN\` until a **provider-originated** causal receipt or equivalent fenced no-effect proof is independently authenticated.
2. A challenge/nonce is a freshness component, not a receipt of an external action.
3. Two different public keys do **not** establish different people, administrative accounts, recovery roots or uncorrelated rollback domains.
4. A signed readback about a historical state does **not** prove it is the latest external head.
5. Detection of missing or inconsistent evidence must **block**. No downgrading to a weaker fallback, and never automatic re-send.
6. Evidence in this LAB is simulation only. No cloud service, new subscription, credentials, deploy, merge, Worker arming, provider call or expenditure authorized.

## Re-test rule

Run the isolated Ubuntu + Windows negative suite, compare with signed-transcript and existing H0 A79/two-domain suites, and only then run the **unmodified** canonical Quality and Security gates on the exact candidate HEAD. Count P0 as closed only with actual external evidence and an independent audit, not with green LAB tests. Current target remains **HARD NO-GO**.
