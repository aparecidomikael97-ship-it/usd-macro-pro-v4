# Issue #1190 — first-install security audit, 10/10/2026

## Verdict

**FIRST INSTALL: NO-GO. NUCLEUS: PARTIALLY_CLOSED / HARD NO-GO (#1117/#1178).**
One concrete credential-ordering gap is reduced in the actual readiness CLI.
No enrollment, independent witness, real signing, hardware, activation or durable
remote recovery has been proved. Offline tests cannot grant first-install approval.

## Baselines and preservation

Repository: aparecidomikael97-ship-it/usd-macro-pro-v4.
Current main read from GitHub: 5744b2b7b17c84331e6f27c569064993ff587782.
Current Draft #1188 head/base of this patch: ce7354b4691d177c5508156d75a8eef3b8a205db.
#1188 remains Draft, unmerged, based on #1187 at 70720c13f58978301dd5736bcace6843a4e6a179.
Worktree: .codex-aion-1190-20261010; branch codex/aion-1190-readiness-fence-audit.
All older worktrees and staged changes preserved. Core V1, memory resolver,
Worker, scheduler, CAS/lease/executor, UI and Negocios are not modified.
Local repository is shallow: do not infer full ancestry from missing local parents.
Comparison uses exact trees and GitHub PR metadata, not an assumption of merge.
Published HEAD and exact CI results are recorded in the Draft and issue comments.

## Concrete gap and minimal patch

FILE: atlasquant_aion_global_worker_readiness.py.
FUNCTION: _cli, original #1188 line 561.
REAL PROBLEM: config_from_mapping() runs before independent_worker_source_preflight.
The actual frozen resolver in atlasquant_aion_memory.py:556-579 reads
os.getenv("GITHUB_TOKEN_HISTORICO", "") at line 560 even when source trust is denied.
Existing no-GET tests replace the resolver with a constant config; they prove no
later GET/token lookup but miss this preceding credential resolution.

Reproduction: compile the real _cli and real config_from_mapping bodies via AST;
only getenv, constructor and external effects are synthetic. The secret getter
raises SECRET_RESOLVED_BEFORE_DENIAL. Before the patch: seven new test methods,
nine failing subcases. This is proven unnecessary secret access, not a demonstrated
network exfiltration, privilege escalation or Worker execution.

Patch: _readiness_source_config creates the public repo/branch descriptor with
an empty token. _cli evaluates the unchanged always-denying production source gate
before resolving credentials. The hypothetical admitted branch retains the exact
repo/branch/path descriptor while adding its token; no destination re-resolution.
No new source verifier, crypto reference, fallback, bypass flag or admin approval.
The existing denied CLI still emits BLOCKED and exits 1. No source ownership is
inferred from environment values. Frozen config_from_mapping remains unchanged.

## Main vs Draft: real call-sites, no Worker execution

| Boundary | main | #1188 stack / patch |
|---|---|---|
| Worker source preflight | no independent_worker_source_preflight call in run_global_worker_once | unconditional production deny at 1554, before checkpoint GET at 1567 |
| Checkpoint GET | load_runtime_checkpoint at 1548 | at 1567, unreachable under source deny |
| CAS claim | _persist_runtime_checkpoint_cas at 1681 | at 1700, requires confirmed load and authorized delegation/governor |
| Lease fence | verifies owner/token/fencing_token/TTL after CAS | preserved at 1721-1739; mismatch blocks executor |
| Executor | _execute_due_local_work_authorized at 1732 | at 1751, after verified claim/fence; unreachable with source deny |
| Final CAS | at 1778 | at 1797; unchanged |
| Flag default | global_worker_feature_enabled requires explicit enable | same; scheduled Worker step conditional on repository variable == '1' |
| Readiness source trust | source-owner proof absent in main | runtime_posture and _cli deny without enrolled independent source |

The default is disabled in source. Actual production flag/deployed SHA/heartbeat
were not queried or changed; UNKNOWN operational state must not be described as
verified disabled. A Draft fence is not a deployed-main fence. No Worker tick was
called in this audit, and no claim/executor was run; call-sites were inspected by
AST/source. The CLI tests exercise only readiness with I/O forbidden.

## GO/NO-GO matrix for first installation

All entries below remain NO-GO for installation/activation; none are physical GO.

| Gate | Current evidence and real limitation | Required independent proof |
|---|---|---|
| HUMAN_OWNER identity/enrollment | core_freeze_preflight build_core_freeze_preflight reports inactive signing; source gate has no enrolled provider | separately authorized ceremony, trusted root/pin custody, revocation and signed owner receipt |
| Source ↔ tenant ↔ repo/branch/path/content | URL/status/no-redirect, hashes and source-bound reference checks exist; real source gate denies | authenticated tenant/resource ownership outside the same checkpoint; exact content and credential identity binding |
| Independent witness / restore | protocol and SQLite references; 20/20 external manifest gates BLOCKED | fresh external protected high-watermark under independent administrative custody; rollback/restore/fork proof |
| Real keys/signatures | disposable fixture signature math only; no real signer used | approved enrollment, key custody/rotation/revocation and verifier beyond caller-provided pins |
| Windows installer / physical assent | no authorized installation or host proof; freeze preflight is not a physical installer certificate | separately approved host, manifest and signer identity; explicit owner assent; least privilege and sandbox/network evidence |
| Unknown outcome / rollback | conservative statuses/quarantine and CAS/fences exist | durable operation record and fresh external read-only reconcile after crash/restore; no automatic replay |
| B2B/private data | private-read containment exists in stack; issues #1169 and tenant scope remain open | authenticated membership/resource binding, login/logout and A→B evidence, cache isolation and durable tenant ledger |
| Persistence | SHA/digest/readback and local transactional reference tests | independent causal receipt/durability; old uncertain writes cannot become confirmed from ID presence |
| Capability/FinOps | source hard denies and capacity arithmetic; total cost unverified | actual account/region/usage/route/billing quote and separate owner approval; no paid service provisioned |
| Pipeline/readiness | negative CI can pass; operational readiness must be BLOCKED/nonzero | all independent gates and separately authorized real operational evidence before considering GO |

External manifest docs/aion/evidence/AION_WITNESS_EXTERNAL_ENROLLMENT_GATE_V1.json:
20/20 gates BLOCKED; production_trust_verified/worker_authorized/owner_approved_spend/
owner_approved_deploy remain false. No manifest gate was changed to simulate readiness.
Existing runtime_source_boundary_ref_v1.verify_source_preflight and
independent_worker_source_preflight are separate: synthetic signature math is never
wired to the always-denying production boundary.

## Validation and CI truth boundary

Local: python -B -m unittest test_atlasquant_aion_readiness_credential_fence_1190
 test_atlasquant_aion_global_worker_readiness_no_get_v1
 test_atlasquant_aion_global_worker_readiness_source_gate_v1 -q:
**19 methods PASS** (7 new + 6 existing no-GET + 6 existing source-posture).
A negative control deliberately proves the frozen resolver still accesses the
synthetic secret; its behavior is not weakened to conceal the original gap.
No actual credential, network, Worker, signer or PC hardware is used.

The new Windows/Linux workflow is stdlib-only negative testing, no installation
of dependencies or operational credentials. Its success means denial holds.
Existing .github/workflows/aion-global-worker-readiness.yml remains byte-for-byte
unchanged: set -o pipefail, CLI through tee, no continue-on-error/||true, exit 1
when BLOCKED. Its red result is intentional operational NO-GO and must stay red.
Other historical synthetic-readiness jobs are not an operational PASS certificate.
Initial hosted revision 635d2818a10ea0ed334e93bda6296e206f13a2e2: the new
workflow failed setup because its optional HTTP mock tried to import requests
in a stdlib-only environment (Linux: seven setup errors; both jobs failed).
The harness was corrected to block socket connect/connect_ex/create_connection;
checkpoint/pulse callbacks still fail on any invocation. No dependency was installed,
no assertion or production denial was removed. Local python -S also validates
without site-packages. Operational run 38082294655 independently emitted BLOCKED,
private_checkpoint_fetch_performed=false, pulse_fetch_performed=false and exited 1.
Exact final hosted statuses/URLs are recorded after publication, without claiming all CI
is green. Whole-app/physical tests and full UI are not executed locally.

## Physical Windows test plan — NOT EXECUTED

Prerequisite for every step: separate HUMAN_OWNER authorization naming the host,
exact operation, reviewed artifact/SHA and permitted data; no am12 or unknown host.
A gate failure stops that action; retain UNKNOWN/NO-GO, no override or retry.

1. Independently verify owner/collector/source/witness enrollment and fresh pins,
   tenant ownership, signed deployment/installer manifest and antirollback floor.
   Caller-supplied pins, ADMIN roles or a config flag are insufficient.
2. On the specifically authorized Windows host, validate exact installer/signature
   and device-owner assent through the approved ceremony. No enrollment/signer/TPM
   operation is authorized by this document; request those permissions separately.
3. Review least privilege, sandbox/network denial and secret custody using an
   approved collector with isolated test endpoints and disposable material.
   Tests involving processes, network, keys or installation require their own scope.
4. Under an approved crash/recovery plan, verify lost ACK, power loss, restart,
   concurrent actors, wrong tenant/resource, revoked signer and restored disk/cloud
   snapshots. Independently fresh witnesses must reject stale/forked heads.
5. Reconcile uncertain results by authenticated reads and causal receipts only.
   Never resend merely after 404, ID presence, timeout, 409/422 or local restore.
6. Record exact hashes, verifier identities, timestamps, negative controls and
   failures. Seek a distinct owner decision only after every physical/external
   gate is actually satisfied; CI success alone never authorizes installation.

## Residuals and scope

This patch reduces credential exposure/lifetime in the denied CLI. It does not
supply source trust, protection against arbitrary monkeypatch, whole-process
import-time secret auditing, external antirollback, enrollment, physical Windows
proof, durable reconciliation or GO. The existing source gate never admits the
hypothetical credential branch; no positive trust provider was fabricated.
First installation stays BLOCKED, #1190/#1178 open and #1117 HARD NO-GO.
No merge, deploy, installation, Worker, runtime write, fee, account, TPM/FIDO2,
real signing, service key or UI/business change was performed.
