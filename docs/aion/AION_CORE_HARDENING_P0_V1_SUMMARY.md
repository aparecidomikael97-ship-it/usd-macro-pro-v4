# AION Core Hardening P0 V1 — Acceptance Summary

## Scope

This block hardens the AION Core change path and adversarial safety contracts without enabling autonomous merge, deploy, paid services, publication, billing, banking/government access or real trading.

## Added in this branch

- `.github/CODEOWNERS` for critical AION, runtime, workflow and deployment surfaces.
- `.github/dependabot.yml` for Python and GitHub Actions update proposals.
- `AION Core Security Gate` on every pull request targeting `main`, with no path filter.
- Dependency vulnerability audit with `pip-audit`.
- High-severity static security scan with Bandit.
- Reproducible CycloneDX SBOM generation and validation from the resolved Python environment.
- Adversarial tests for authority boundaries, prompt/tool injection posture, non-delegable sensitive capabilities, workspace-bound delegation and resource budgets.
- Chaos/recovery tests for provider failure, stale heartbeats, loop/error storms, resource exhaustion, policy-integrity failure and recovery approval gates.

## Fail-closed invariants exercised

1. Web, documents, email, tool output and external AI are evidence/content, not authority.
2. Checkpoint and internal memory are context/evidence, not authorization.
3. External AI never receives direct tool authority.
4. Sensitive capabilities remain non-delegable to worker agents.
5. Delegation is workspace-bound and least-privilege.
6. Resource exhaustion blocks new sensitive work.
7. Provider/component failure degrades the system before sensitive work proceeds.
8. Policy-integrity failure recommends emergency stop and does not self-destruct or bypass the independent controller.
9. Checkpoint recovery requires a confirmed current runtime, an eligible historical candidate and explicit administrator approval.
10. Security checks never claim that a tool action, deployment, merge, payment or real trade occurred.
11. Approval, admin authentication, signed policy and risky feature flags accept only boolean `True`. Strings such as `"false"`, `"yes"` and numbers do not grant authority, close a circuit, or restore a checkpoint.
12. A declared tenant id in a payload does not authorize another tenant. Cross-tenant access follows the credential-bound namespace.

## Quality workflow

`test_atlasquant_aion_security_adversarial.py` and `test_atlasquant_aion_chaos_recovery.py` are listed in `.github/workflows/quality-tests.yml`. The previous head `76f34e8c` failed Quality tests only because those files were omitted from that workflow. The security gate itself had already executed them.

## Still requires repository administration

The repository currently reports `main` as unprotected. This branch cannot by itself turn a workflow into an enforced merge gate. Repository administration must activate a ruleset/branch protection for `main` and require the relevant checks.

Recommended minimum ruleset after this PR is green and merged:

- pull request required for changes to `main`;
- required status checks, including `AION adversarial contracts`, `Supply-chain audit`, existing quality/release checks and UI checks used by the project;
- require conversation resolution where supported;
- block force-push and branch deletion;
- require CODEOWNERS review where compatible with the repository plan/settings;
- do not permit bypass for ordinary agent/workflow identities.

## Acceptance for this block

This branch is ready for human review only when:

- the new security gate is green;
- the existing Quality, Release Readiness and relevant UI checks remain green;
- no critical adversarial/chaos test fails;
- no dependency audit or high-severity static scan fails;
- branch remains based on the expected `main` merge base or is safely rebased/reconciled;
- no merge/deploy is performed automatically.

Tracking issue: #325.
