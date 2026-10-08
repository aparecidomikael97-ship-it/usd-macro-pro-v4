# AION Windows Build Input Snapshot + Offline Dependency Cache Attestation V1

Status: IMPLEMENTATION SAFE / NON-DOWNLOADING INPUT GOVERNANCE  
Date: 2026-10-08  
Artifacts downloaded by this module: NO  
Packages installed: NO  
Build started: NO  
Network during attestation/build: FORBIDDEN  
Live GitHub mutation: DISABLED

## Objective

Freeze the exact Python/runtime inputs that may enter the reproducible Windows
local-agent build environment.

This layer sits before the no-network reproducible build from #1046.

It answers:

1. Which exact artifacts are allowed?
2. Were their expected and observed SHA-256 values identical?
3. Is the full transitive dependency graph closed?
4. Was a future physical cache independently observed as read-only, owner-only,
   exact and network-isolated?
5. May those attested inputs be presented to the reproducible-build review?

It does not download, copy, install or build anything.

## Closed input set

V1 allows exactly five roles:

- PYTHON_RUNTIME
- PIP_WHEEL
- CRYPTOGRAPHY_WHEEL
- CFFI_WHEEL
- PYCPARSER_WHEEL

No sixth file is permitted.

## Exact versions

The frozen versions are:

- CPython 3.12.12
- pip 26.2.1
- cryptography 50.0.2
- cffi 2.1.1
- pycparser 3.1

The cffi/pycparser pins close the transitive graph that appeared behind the
pinned cryptography runtime.

## Closed dependency graph

The allowed logical graph is:

- Python runtime -> no package dependency
- pip -> no package dependency
- cryptography -> cffi
- cffi -> pycparser
- pycparser -> none

Missing a transitive artifact blocks the snapshot.

Runtime dependency resolution is not permitted to silently add a package later.

## Artifact classes

Python itself is an exact Windows x64 embeddable runtime ZIP.

Python packages must be wheels compatible with the target:

- pip: py3-none-any
- cryptography: abi3 + win_amd64 compatible with CPython 3.12
- cffi: cp312-cp312-win_amd64
- pycparser: py3-none-any

Source distributions are forbidden in this V1.

Build-from-source is forbidden in this V1.

That removes compiler/toolchain variability from the initial local-agent supply
chain.

## Expected hash vs observed hash

Every artifact contains two separately supplied SHA-256 bindings:

- expected_sha256
- observed_sha256

They must match exactly.

An expected hash alone is insufficient.

An observed hash without a trusted expected value is also insufficient.

## Per-artifact acquisition evidence

Each artifact requires:

- source metadata digest;
- package metadata digest;
- acquisition receipt digest;
- verified acquisition transport evidence;
- verified trusted source snapshot evidence.

The contract records these digests but does not contact the source itself.

## Global acquisition snapshot

The input snapshot also binds:

- trusted Python release snapshot digest;
- trusted Python package-index snapshot digest;
- dependency resolver evidence digest;
- acquisition environment digest;
- the #1046 dependency-lock digest.

This separates the online acquisition ceremony from the later no-network build.

## Offline cache physical boundary

A future physical Windows cache may be attested only if external evidence proves:

- cache root identity;
- owner-only ACL;
- cache is read-only;
- no extra files;
- no symbolic links;
- no NTFS reparse points;
- no Alternate Data Streams;
- network isolation.

The module validates those observations.

It does not create or modify the cache.

## Why symlink/reparse/ADS checks matter

A filename and SHA list is not enough if the filesystem can redirect a path or
hide another stream.

The Windows cache boundary therefore explicitly rejects:

- symbolic links;
- junction/reparse indirection;
- Alternate Data Streams.

The future physical verifier must inspect those properties on the actual owner
machine.

## Deterministic cache tree

Observed cache files are normalized into UTF-8 bytewise filename order.

The cache tree digest is independent of enumeration order.

Reversing the input observation order must produce the same tree digest.

## Read-only transition

After positive cache attestation:

`cache_mutation_allowed_after_attestation=false`

Any future cache change requires a new snapshot and new attestation.

A previously certified cache cannot absorb a new wheel silently.

## Reproducible-build promotion

A positive promotion binds:

- #1046 dependency-lock digest;
- input-snapshot digest;
- offline-cache attestation digest;
- cache-tree digest;
- reproducible-build recipe digest;
- promotion-review digest.

Maximum positive state:

`OFFLINE_BUILD_INPUTS_READY_FOR_REPRODUCIBLE_BUILD`

This is only input readiness.

It still reports:

- build_authorized=false
- build_started=false
- package_built=false
- package_installed=false
- network_allowed=false

## No resolver in the reproducible build

The build environment may consume exact artifacts only according to the frozen
manifest.

It may not run a resolver that chooses another version.

Therefore:

`dependency_resolution_from_cache_allowed=false`

means no dynamic resolver decision is allowed; it does not mean the future build
cannot read the exact attested wheel files.

## Security invariants

The cache policy keeps:

- sdist_allowed=false
- build_from_source_allowed=false
- extra_cache_files_allowed=false
- cache_read_only_after_attestation=true
- owner_only_cache_acl_required=true
- symlinks_allowed=false
- reparse_points_allowed=false
- alternate_data_streams_allowed=false
- network_during_cache_attestation_allowed=false
- network_during_reproducible_build_allowed=false
- cache_mutation_after_attestation_allowed=false

## Explicitly absent

This V1 does not:

- download Python;
- download a wheel;
- call PyPI;
- call python.org;
- resolve dependencies;
- install packages;
- copy artifacts;
- create a physical cache;
- modify Windows ACLs;
- start the reproducible build;
- create a production package;
- load credentials/private keys;
- call GitHub;
- perform a repository mutation;
- deploy;
- activate Worker/provider/production persistence.

## Future physical acquisition phase

Before a real Windows build, a controlled acquisition phase must obtain the real
files and fill in their real:

- filenames;
- sizes;
- SHA-256 hashes;
- source metadata evidence;
- package metadata evidence;
- acquisition receipts.

Then a separate offline host/cache verifier must recompute the byte hashes and
filesystem boundary evidence.

Synthetic CI digests are not production artifact hashes.

## Relationship to #1046

#1046 defines how already-frozen inputs must build reproducibly with no network.

This V1 defines how those inputs become trustworthy enough to enter that
environment.

The order is:

Acquisition -> exact snapshot -> offline cache attestation -> promotion review ->
reproducible build.

## Next safe phase

After this V1 is green, the next phone-safe block is:

`WINDOWS OFFLINE BUILD SANDBOX + INPUT MOUNT CONTRACT V1`

That can define a read-only cache mount, writable isolated output directory,
environment scrub, process allowlist and network-deny boundary for the future
actual build process without running a production build.

## Validation target

After dedicated CI is green, the maximum truthful milestone is:

`AION_WINDOWS_BUILD_INPUT_OFFLINE_CACHE_ATTESTATION_V1_VALIDATED`

No production download, build or installation is implied.
