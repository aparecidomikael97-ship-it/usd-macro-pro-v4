# AION Windows — Isolated Localhost Evidence Readiness Contract V1

**PREPARE ONLY.** No owner-PC access, no physical probe, no AppContainer
profile creation/deletion, no network socket, no child process launch, no
WFP/Firewall changes, no installation, merge or deploy.

## Why we built this

A previous, individually HUMAN_OWNER-authorized physical test on `am12`
successfully created and later deleted one temporary zero-capability
AppContainer profile. A synthetic `cmd.exe` child had `TokenIsAppContainer`
verified and exited. A separate PowerShell TCP localhost child did not
terminate within 8 seconds and was killed; the parent positive-control
listener was reachable before and after. **This was TIMEOUT, NOT a verified
network denial.** A second follow-up native probe was blocked by a tool
safety barrier before execution and MUST NOT be represented as completed or
reissued to work around that barrier.

The existing Drafts supply complementary but limited contracts:
- #1087 16-surface fail-closed matrix; no physical 16/16 certification.
- #1088 parent-independent normal-CI-child 127.0.0.1 witness; its
  `NORMAL_CI_CHILD_NOT_APPCONTAINER` token is not a physical deny proof.
- #1089 read-only held-process token/SID/capability report; even a
  matching AppContainer SID and zero capabilities is NOT network isolation.
- #1090–#1091 suspended pinned binary normal-child negative CI; child is
  terminated without resumption, not an OS-denial test.

This new module **correlates** only self-reported synthetic proof pieces
for *one* potential future IPv4 TCP localhost physical test. It does not
collect them, attest their origin, or launch anything.

## Minimum hypothetical evidence required

A candidate must state, in one strictly versioned/closed schema:

1. A unique 256-bit challenge nonce, exact reviewed profile naming scope,
   and fixed `APPCONTAINER_NO_NETWORK_CAPABILITIES` method.
2. Matching pinned/observed **public** binary SHA-256 strings. These remain
   self-claims, not a signature, opened-file identity, verified binary
   provenance or protection from TOCTOU.
3. A complete #1089 token readback result, specifically an untrusted
   matching SID + zero-capability candidate with all authority flags FALSE.
   The input does not independently authenticate the process handle.
4. Normal-context localhost listener witnessed reachable before AND after
   the test, with distinct challenges from the isolated child.
5. Explicit isolated-child start and completion, CONNECT actually attempted,
   child stdout correlated to nonce, token inspection associated with a
   held process handle and child exit code 0.
6. **WinSock 10013 / WSAEACCES explicitly reported** after the connect
   attempt, with no parent-witnessed isolated challenge reaching the server.
   Connection-refused (10061), timeout, startup failure, generic exit
   0xC0000022, or no server hit by itself are **NOT** positive denial.
   Another verified OS denial mechanism would require a new reviewed schema;
   this V1 deliberately favors false negatives to avoid false certification.
7. Explicit reports of terminated child, kill-on-close Job Object,
   closed handles, deleted temporary profile, unchanged Windows Firewall
   and WFP state, and **no external network endpoints**.

Each field is *untrusted input*. Even if all match, the result is
`LOCAL_LOOPBACK_DENIAL_CANDIDATE_UNTRUSTED`. The module always sets
`independent_collector_attested=false`,
`os_network_denial_physically_verified=false`,
`all_16_network_surfaces_verified=false`,
`physical_sandbox_12_of_12_verified=false`, `network_deny_verified=false`,
`installer_authorized=false`, `build_authorized=false`,
`deploy_authorized=false`, `safe_to_resume=false`.
No caller-supplied `verified`, `approved` or unknown fields can bypass
this block.

## Required physical protocol review BEFORE asking for owner approval

- Specify exact process image digest/file identity, signer key source,
  provenance and collector isolation. A hash claim cannot identify
  a physical process or trusted source by itself.
- Produce a bounded **native** connect-attempt report with explicit error
  source and phase. A PowerShell startup timeout cannot be reclassified as
  a WinSock denial. Do not assume a Python child will start in AppContainer.
- Parent-side witness observes a nonce and reaches positive control before
  and after; verify the precise source and process lifetime independently.
- The token must be read from a held verified process handle tied to
  the image and original security capabilities.
- Parent-controlled bounded timeout, Job Object terminate-on-close, cleanup
  and verification of no residual profile, child, policy or unknown process.
- A narrowly scoped new HUMAN_OWNER authorization is mandatory for any
  real `am12` process/profile mutation. If a tool's safety interlock blocks
  execution, **do not work around it**.
- External internet, IPv6, UDP, DNS, SMB and inherited handle tests are
  distinct scopes requiring independent controlled positive/negative
  witnesses and any necessary new authorization.
- Independently signed/anchored physical evidence and trusted collector
  identity are still required; local unsigned receipts cannot certify
  owner-host network isolation.

## CI / owner machine boundary

This PR only runs **pure structural negative tests** on disposable
GitHub-hosted Windows and Linux environments, plus pre-existing pure tests.
It does **not** create an AppContainer, launch a new isolated process,
probe localhost or external destinations, modify Windows settings or
generate a trusted physical attestation.

It is stacked on #1091, NOT #1113; work remains independent of the
Codex antirollback/monotonic-witness task. No change to `main`, physical
#1049 or #1087 gates, installer, Render, Worker, cost or live owner
keys. No release or install permission is requested by this PR.

## Remaining mandatory proofs

All #1049 **12-category physical sandbox controls** and all #1087
**16 network-denial surfaces** require independent positive+negative
evidence on the actual target host, together with real key enrollment
and protected monotonic witness from a separately approved rollout.
CI test success is not a substitute for those proofs.
