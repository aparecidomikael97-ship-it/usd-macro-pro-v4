# AION Secure Agent — Windows Suspended Child Quarantine V1 (08/10/2026)

**Status: Draft / GitHub CI only. No installation, no real AION executable, no owner-PC execution, no positive sandbox admission, no network-denial proof.**

## Why this gate exists

PR #1089 introduced read-only held-process handle verification of `TokenIsAppContainer`, expected `TokenAppContainerSid` and effective `TokenCapabilities`. This still does not establish a safe host launch sequence. On the authorized owner Windows physical probe (earlier stage), an actual AppContainer child launched, but the TCP localhost PowerShell attempt timed out and did not establish OS network denial; a subsequent attempted follow-up was blocked by tooling security and not retried.

This V1 supplies a **narrow, real negative path** on **ephemeral Windows GitHub runners**, deliberately using a normal child that must never be trusted.

## Native CI-only sequence

1. Confirm `GITHUB_ACTIONS=true`, `GITHUB_EVENT_NAME=pull_request`, `RUNNER_OS=Windows`, `GITHUB_RUN_ID` present. This is a guard against accidental local execution, **not** a cryptographic runner identity.
2. Create an ephemeral scratch directory and Windows Job Object with `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`.
3. Launch exactly the runner's own absolute `sys.executable` via `CreateProcessW` with **CREATE_SUSPENDED**, **CREATE_NO_WINDOW**, a minimal explicit environment and **bInheritHandles=false**. The toy child contains a harmless canary-writer intended only for this scratch directory. If the process resumes improperly, the test must detect the sentinel file.
4. Assign the suspended child to the Job Object before any token trust decision. If assignment fails, fail closed and terminate it.
5. Query the already-held process handle via #1089's `inspect_windows_process_handle`, with a constrained ephemeral expected profile name. The normal runner child must return `TOKEN_NOT_APPCONTAINER`. Fail closed on anything else.
6. **Never call `ResumeThread` or any process-resume API**, including success-case token output (there is no success-case launcher in this PR).
7. In unconditional cleanup, `TerminateProcess`, `WaitForSingleObject`, close Job Object/thread/process handles, check no canary file, then remove all scratch files. Fail if any control fails. The Windows Job Object limits scope synthetic child termination; not a full resource or privilege sandbox.
8. A separate pure policy rejects any missing or false observation, token claims of real proof, extra fields, wrong token status or assertions of build/install/deploy. Even a complete synthetic negative observation only reaches `NORMAL_CHILD_QUARANTINED_AND_TERMINATED`. All authority flags remain FALSE.

## Automated verification

- Windows: tests in GitHub-hosted Windows runner with actual `CreateProcessW(CREATE_SUSPENDED)`, native token readback, Job Object and negative cleanup. Additional CI explicit command repeats the negative scenario with fresh scratch.
- Linux: pure adversarial contract tests. Native Windows case is deliberately skipped.
- All runners: AST gate rejects resumption, profile creation, WFP mutation, use of network libraries and escalation to install/deploy; repository PR-only, `contents: read`.
- On unexpected token output or inability to terminate/clean safely, CI MUST fail; never quietly reinterpret it as evidence.

## What this does NOT do

- Never creates an AppContainer profile, starts a real AppContainer child, authorizes execution, or permits an AION installer.
- Does not sign physical evidence, prove owner identity, validate immutable command/manifest hashes or a real host principal, block external/loopback TCP, UDP, DNS, proxies, IPv6 or IPC.
- The **normal** CI child is a rejection case only. The actual owner PC has not been touched in this block.
- The 16 physical network-surface requirements in PR #1087, and all 12 independently attested sandbox categories in #1049, remain unverified.
- This is not a production Windows process-isolation implementation. Any future positive-path launcher needs independent approved design for AppContainer user profile lifecycle, trusted process-handle custody, signed manifest/source, Job Object, no network capabilities, physical deny tests, evidence verifier, deadlines and automatic rollback.

Governance: all PRs remain Draft, no merge/deploy/Render/Worker, production persistence, app installation, owner Windows mutation or spending. R$200/month provisional infrastructure cap unchanged.

## Reference

- [CreateProcessW CREATE_SUSPENDED](https://learn.microsoft.com/en-us/windows/win32/procthread/process-creation-flags)
- [AssignProcessToJobObject](https://learn.microsoft.com/en-us/windows/win32/api/jobapi2/nf-jobapi2-assignprocesstojobobject)
- [Job Object limits](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_basic_limit_information)
