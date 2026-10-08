# AION Windows Sandbox Physical Probe Plan + Evidence Schema V1

Status: IMPLEMENTATION SAFE / DATA-ONLY PHYSICAL PROBE PLAN  
Date: 2026-10-08  
Windows physical probe executed: NO  
Collector implemented: NO  
Independent verifier implemented: NO  
Build authorized: NO  
Production build started: NO

## Objective

Define exactly how the future Windows owner machine must prove the physical
sandbox guarantees described by #1048 before the first real local-agent build
may be considered.

This layer defines the plan and evidence schema only.

It does not inspect Windows, spawn a process, create a token, create a Job
Object, open files, probe the network, or authorize a build.

## Exact inherited proof set

The plan must inherit exactly the twelve physical requirements from #1048, in
the same order:

1. WINDOWS_RESTRICTED_TOKEN_PROOF_REQUIRED
2. WINDOWS_JOB_OBJECT_LIMITS_PROOF_REQUIRED
3. CACHE_READ_ONLY_MOUNT_PROOF_REQUIRED
4. SOURCE_READ_ONLY_MOUNT_PROOF_REQUIRED
5. RUNTIME_READ_ONLY_MOUNT_PROOF_REQUIRED
6. OUTPUT_TEMP_ONLY_WRITE_PROOF_REQUIRED
7. SYMLINK_REPARSE_HARDLINK_ESCAPE_PROOF_REQUIRED
8. ENVIRONMENT_SCRUB_PHYSICAL_PROOF_REQUIRED
9. PINNED_PYTHON_BINARY_PROOF_REQUIRED
10. NO_CHILD_PROCESS_PHYSICAL_PROOF_REQUIRED
11. WINDOWS_NETWORK_DENY_PHYSICAL_PROOF_REQUIRED
12. RESOURCE_LIMITS_PHYSICAL_PROOF_REQUIRED

Missing, reordered or additional requirements block the plan.

## Host binding

The future probe plan is bound to one exact host evidence identity.

Evidence from another machine may not satisfy the plan.

The host binding is digest-only in this phase.

The future collector must define how Windows machine/session identity is derived
without placing sensitive raw identifiers into ordinary application logs.

## Collector binding

The plan requires a collector-manifest digest.

Every future measurement must also bind:

- collector binary digest;
- collector-signature evidence digest;
- collector manifest digest.

A result that does not identify the exact collector is not acceptable.

## Sandbox-preflight binding

Every measurement binds the exact #1048 sandbox-preflight digest.

A probe collected against an older or different sandbox plan cannot be reused
for a changed sandbox.

## Positive + negative proof

Every requirement needs both:

- the expected positive observation;
- a deliberate negative/adversarial test.

Example:

For NO_CHILD_PROCESS_PHYSICAL_PROOF_REQUIRED:

Positive observation:
`CHILD_PROCESS_CREATION_DENIED`

Negative test:
`CREATE_PROCESS_CHILD_ATTEMPT_BLOCKED`

A positive-looking configuration dump alone is insufficient.

## Requirement-specific methods

### Restricted token

Method:
`WINDOWS_ACCESS_TOKEN_INSPECTION`

Expected:
`RESTRICTED_CURRENT_USER_TOKEN`

Negative:
`PRIVILEGE_ESCALATION_NOT_AVAILABLE`

### Job Object

Method:
`WINDOWS_JOB_OBJECT_QUERY`

Expected:
`JOB_OBJECT_LIMITS_MATCH_PREFLIGHT`

Negative:
`SECOND_PROCESS_OR_CHILD_LIMIT_REJECTED`

### Read-only roots

Cache/source/runtime each require a real Windows write-denial probe.

The collector must attempt create/modify/delete/rename operations and prove they
fail.

### Output/temp write boundary

The collector must prove writes succeed only inside output/temp and fail outside
those roots.

### Symlink/reparse/hardlink escape

The collector must attempt filesystem escape paths and prove the sandbox does
not cross the permitted root boundary.

### Environment scrub

The future child environment must be enumerated physically and compared to the
exact #1048 environment contract.

Forbidden parent/user/proxy/credential/Git variables must be absent.

### Pinned Python

The probe must bind the opened executable through secure path/handle evidence
and SHA-256, not PATH lookup or filename alone.

### No child process

The probe must attempt child process creation and prove it is blocked.

### Network deny

The probe must test the denied surfaces:

- DNS
- TCP
- UDP
- loopback
- proxy path
- remote named pipe

The freshness window for this requirement is deliberately shorter: 60 seconds.

### Resource limits

The future probe must demonstrate that the Job Object/resource policy actually
enforces process, memory/output/runtime limits rather than merely reporting
configured values.

## Evidence envelope

Each future evidence record must bind:

- requirement;
- measurement-plan digest;
- probe-plan digest;
- sandbox-preflight digest;
- host-binding digest;
- collector-manifest digest;
- raw evidence reference;
- raw evidence SHA-256;
- collector binary SHA-256;
- collector-signature evidence digest;
- observed value;
- negative-test observed value;
- collection time;
- valid-until time;
- canonical sequence.

## Freshness

Evidence is not eternally valid.

Most requirements have a maximum 120-second collection validity window.

Network-deny evidence has a maximum 60-second window.

All evidence requires recheck before use.

A future authorization layer must re-evaluate freshness at the moment of use.

## Caller booleans are not authority

This V1 explicitly rejects caller-supplied claims such as:

- evidence_is_physical=true
- independently_verified=true
- host_binding_verified=true
- preflight_binding_verified=true
- collector_identity_verified=true
- negative_test_verified=true
- freshness_verified=true
- physical_proof_verified=true

Those flags cannot create proof.

## Valid shape is still untrusted

A future evidence candidate may contain the correct shape, digests, expected
observations and timestamps.

The maximum state this V1 may return for such a record is:

`EVIDENCE_CANDIDATE_SHAPE_VALID_BUT_UNTRUSTED`

That means schema validation passed.

It does NOT mean physical proof passed.

## Why this distinction matters

A JSON document can claim anything.

A SHA-256 proves content identity, not truth.

Therefore a document digest, a caller boolean or a self-reported observation
cannot independently prove Windows enforcement.

The future physical phase must add:

- real collector implementation;
- collector identity/signing evidence;
- raw evidence capture;
- independent verifier;
- evidence-store integrity;
- trust/root-of-trust model appropriate to the local owner machine.

## Uncollected evidence bundle

This V1 creates one canonical evidence slot per physical requirement.

All twelve slots begin as:

- collection_state=NOT_COLLECTED
- observed_value=NOT_MEASURED
- evidence_is_physical=false
- independently_verified=false
- physical_proof_verified=false

The bundle therefore has:

- required_total=12
- collected_total=0
- verified_total=0
- all twelve requirements missing

This is intentional and truthful.

## Implementation-review state

If the plan, evidence schema and future collector/verifier design digests are
complete, the maximum state is:

`READY_FOR_WINDOWS_PHYSICAL_PROBE_IMPLEMENTATION_REVIEW`

This only means the next PC-side implementation work is well specified.

It still reports:

- collector_implemented=false
- collector_executed=false
- independent_verifier_implemented=false
- evidence_collected=false
- physical_probe_executed=false
- physical_proof_verified=false
- windows_sandbox_verified=false
- build_authorized=false
- build_started=false
- package_built=false

## Next physical phase

The next phase requires the owner's Windows PC:

`WINDOWS_PROBE_COLLECTOR_IMPLEMENTATION_ON_OWNER_PC`

That phase will need to implement the actual Windows evidence collector and run
only non-production sandbox probes first.

It must still remain separated from authorization of the real production build.

## Explicitly absent

This V1 does not:

- create a Windows restricted token;
- create/query a real Job Object;
- modify ACLs;
- mount roots;
- open/write probe files;
- create symlinks/reparse points/hardlinks;
- inspect a real child environment;
- hash a real python.exe;
- spawn python.exe;
- attempt child process creation;
- open sockets;
- test DNS/TCP/UDP;
- create firewall rules;
- collect raw evidence;
- independently verify evidence;
- authorize a build;
- start a build;
- build/install a package;
- call GitHub;
- mutate a repository;
- deploy;
- activate Worker/provider/production persistence.

## Validation target

After dedicated CI is green, the maximum truthful milestone is:

`AION_WINDOWS_SANDBOX_PHYSICAL_PROBE_PLAN_EVIDENCE_V1_VALIDATED`

No physical Windows proof is implied.
