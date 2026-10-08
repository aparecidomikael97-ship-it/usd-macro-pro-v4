# AION Windows Local Agent Build Recipe + Reproducible Package Contract V1

Status: IMPLEMENTATION SAFE / NON-PRODUCTION BUILD CONTRACT  
Date: 2026-10-08  
Production package built: NO  
Package installed: NO  
Network during build: FORBIDDEN  
Live GitHub mutation: DISABLED

## Objective

Define a deterministic build recipe for the future Windows local agent and prove
that two independent build observations must converge to identical outputs.

This V1 does not build or install a production package.

It defines the reproducibility contract and validates it with synthetic,
in-memory deterministic archive fixtures plus build-observation comparison.

## Narrow toolchain

The future local agent build recipe is intentionally narrower than the full
AtlasQuant application runtime.

Pinned build/runtime inputs:

- Python 3.12.12
- pip 26.2.1
- cryptography 50.0.2

No floating version or resolver upgrade is allowed during the build.

The dependency lock contains exactly the approved dependencies for this local
agent build contract.

## Build network policy

Build policy is:

`NO_NETWORK_DURING_BUILD`

Dependencies must already exist in a separately verified build cache/environment
before the reproducible build starts.

The reproducible-build phase itself may not:

- resolve dependencies;
- upgrade dependencies;
- call PyPI;
- call GitHub;
- fetch remote content.

This separates artifact reproducibility from dependency acquisition.

## Source set

The build source set is inherited from the closed package manifest introduced in
#1045.

It requires exactly the same seven package roles and exact role/path bindings.

Source rows are sorted by UTF-8 bytewise path order.

No additional source is allowed.

## SOURCE_DATE_EPOCH

A valid build recipe requires an explicit:

`SOURCE_DATE_EPOCH`

It is the canonical archive timestamp.

Wall-clock build time is not part of artifact identity.

Observation time remains audit metadata only and is excluded from the
reproducibility fingerprint.

## Environment normalization

The recipe fixes:

- TZ=UTC
- LC_ALL=C.UTF-8
- LANG=C.UTF-8
- PYTHONHASHSEED=0
- SOURCE_DATE_EPOCH=<pinned epoch>

Host-dependent environment such as username, profile directory, hostname,
runner name and temporary directory must not be embedded into the artifact.

## File metadata normalization

Archive members use deterministic metadata:

- lexical path order;
- entrypoint mode 0755;
- other package files mode 0644;
- UID=0;
- GID=0;
- empty uname/gname;
- timestamp from SOURCE_DATE_EPOCH;
- LF line-ending contract;
- no extra ZIP metadata;
- deterministic compression settings.

## Build recipe pins

The recipe additionally binds:

- builder image digest;
- build script digest;
- dependency-lock digest;
- source-set digest;
- SBOM recipe digest;
- provenance recipe digest;
- recipe revision.

Changing any of these creates a different build recipe identity.

## SBOM reproducibility

The SBOM is part of the reproducibility comparison.

Two builds are not reproducible if the binary/archive matches but their SBOM
digests differ.

This prevents metadata generation from being treated as an unverified side
channel.

## Provenance reproducibility

Build provenance is also compared.

The provenance recipe must avoid ephemeral runner IDs, local paths, wall-clock
timestamps and usernames in the reproducibility-relevant payload.

Audit timestamps may exist outside the reproducibility fingerprint.

## Independent build observations

Each build observation binds:

- recipe digest;
- output archive digest;
- output installation-manifest digest;
- output SBOM digest;
- output provenance digest;
- output tree digest;
- builder image digest;
- build script digest;
- dependency-lock digest;
- source-set digest;
- SOURCE_DATE_EPOCH;
- normalization verification;
- absence of extra files;
- absence of host-specific metadata;
- absence of credentials/private keys;
- absence of network use.

A build observation does not authorize release or installation.

## Two-build certificate

A reproducibility certificate requires two different observation IDs and
external evidence that builds used:

- independent builders;
- independent work directories;
- clean build roots.

The following must match exactly:

- archive digest;
- installation-manifest digest;
- SBOM digest;
- provenance digest;
- output tree digest;
- reproducibility fingerprint.

Any mismatch blocks certification.

Maximum positive state:

`TWO_BUILD_REPRODUCIBILITY_CONFIRMED`

Even this state still reports:

- release_authorized=false
- installation_authorized=false
- package_installed=false

## Synthetic byte-level proof

The dedicated CI tests create two synthetic ZIP archives entirely in memory.

The input rows are deliberately supplied in different orders.

The recipe re-normalizes order, timestamp and file modes.

The tests require both archives to be byte-for-byte identical and to have the
same SHA-256.

A changed SOURCE_DATE_EPOCH must change the archive digest.

This validates the deterministic mechanics without creating a production local
agent package.

## What this V1 does not do

This V1 does not:

- invoke PyInstaller;
- invoke an MSI/EXE compiler;
- build a production ZIP;
- create a release;
- sign a production package;
- install anything;
- spawn subprocesses;
- write build output to disk;
- access a private signing key;
- access GitHub credentials;
- call network;
- call GitHub;
- mutate a repository;
- deploy;
- activate Worker/provider/production persistence.

## Relationship to #1045

#1045 answers:

"Is this package manifest/supply-chain evidence acceptable?"

This V1 answers:

"Can the same pinned inputs produce the exact same package identity twice?"

Both are required before a future Windows installation.

Neither authorizes installation.

## PC/build-host phase still required

Before a real package can be installed, a controlled Windows build phase must
produce two actual independent artifacts using the pinned recipe and compare
their real output digests.

Then #1045 package attestation must verify the resulting package release and
Windows Authenticode evidence.

CI synthetic reproducibility is not a substitute for two real Windows package
builds.

## Next safe phase

After this V1 is green, the next safe block is:

`WINDOWS BUILD INPUT SNAPSHOT + OFFLINE DEPENDENCY CACHE ATTESTATION V1`

That can define how the pinned Python/cryptography inputs are acquired,
hash-verified and frozen before entering the no-network reproducible-build
environment.

## Validation target

After dedicated CI is green, the maximum truthful milestone is:

`AION_WINDOWS_LOCAL_AGENT_REPRODUCIBLE_BUILD_CONTRACT_V1_VALIDATED`

No production package build or installation is implied.
