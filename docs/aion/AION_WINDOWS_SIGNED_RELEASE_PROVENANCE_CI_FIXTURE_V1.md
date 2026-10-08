# AION Windows — Signed Release Provenance CI Fixture V1

**Status:** IMPLEMENTATION SAFE — CI-only cryptographic tests / Draft  
**Date:** 2026-10-08  
**Stacked on:** #1064 Windows CI Authenticode + Binary Integrity Preflight

## Goal and trust ceiling

#1064 confirmed that Windows can validate an existing signed **operating
system** executable and reject a modified copy on an ephemeral CI runner.
It did not establish AION publisher identity, signer governance, or AION
package integrity. This V1 isolates the **next issue**: checking whether
detached Ed25519 signatures bind an exact release manifest to exact artifact
bytes while a user-selected public key is treated as **untrusted**.

The CI suite generates a disposable Ed25519 private key **inside the test
process memory**. It signs synthetic, inert test bytes and never outputs
private-key material or produces a production signed AION package.

A valid signature proves only that the supplied public key matches the
signer of the supplied manifest bytes. It does **not** prove that the key
belongs to the authorized AtlasQuant/AION publisher, or that a claimed
GitHub commit, workflow run, build system or artifact source is authentic.

## Boundary A: exact detached release manifest

The canonical JSON manifest requires, with no extra fields:
- CI scope and explicit ephemeral untrusted signer key-origin marker;
- synthetic release identifier and `0.x.y-ci.N` version;
- 40-hex source commit and claimed build workflow/run/environment bindings;
- expected CI Ed25519 public key digest;
- publisher policy digest and release-specific challenge;
- sorted allowlisted list of complete artifact names, byte lengths and
  SHA-256 digests;
- explicit FALSE for independent build attestation, trusted publisher
  identity, and HUMAN_OWNER install authorization.

Each artifact path must be strict lowercase ASCII relative path with
forward slashes, no drive prefix/backslash, no parent `..` components,
Windows reserved device names, trailing dots, empty segments, absolute
paths, or duplicate/case-insensitive collisions.

This fixture caps the count at **32** and byte length of each artifact at
**4 MiB**. These are test protections, not future AION package size limits.
The verifier takes bytes **already in memory** and does not open paths,
extract archives, follow symlinks or execute files.

## Boundary B: real cryptographic verification, untrusted provenance

- Requires exact expected release, version, source commit, workflow,
  workflow run ID, environment, publisher-policy digest, challenge, public
  key fingerprint and file-table digest.
- Requires actual complete byte map matching all declared files exactly;
  no missing or extra file.
- Requires file sizes and SHA-256 bytes to match the signed manifest.
- Checks 32-byte Ed25519 public key and 64-byte detached signature.
- Cryptographically verifies Ed25519 signature against exact canonical JSON
  manifest bytes with the Python `cryptography` library.
- Blocks forged signature, unexpected publisher/owner trust flags,
  wrong build identifiers, change of file contents, unsafe paths, and
  missing or conflicting release-binding fields.

**Result ceiling:** `CI_DETACHED_SIGNATURE_AND_MANIFEST_MATCH_UNTRUSTED`.

A syntactically well-formed hash or an arbitrary self-signed key is never
trusted as a third-party witness. CI cannot self-approve its own signer.

## Boundary C: future release handoff — shape only

`build_ci_release_handoff_plan()` composes a contract requiring future
independent inputs:
- exact installation binding;
- separately approved publisher registry;
- independent build attestor manifest;
- package-ingestion policy;
- owner-review policy.

These are required **digest shapes**, not real checked authorities.
The result `RELEASE_PROVENANCE_HANDOFF_SHAPE_READY_UNTRUSTED`
does not grant publisher trust, build provenance, owner authorization,
release approval, artifact installation, deployment or Worker activation.

A real owner-device consumer must later verify the actual signed AION
binaries and hashes against a separately authorized release issuer,
using key lifecycle, signer rotation/revocation and witness provenance.
No generated CI key may ever be promoted into the real trust registry.

## Threat-model tests

The adversarial suite includes successful CI Ed25519 verification, same-size
byte modification, detached signature/key substitution, post-signing manifest
modification, missing or extra files, unsorted and case-colliding names,
Windows path traversal/device-name/drive/Unicode hazards, file-size limits,
invalid hash/commit/version/run identifiers, fake HUMAN_OWNER authorization,
claimed external build trust, mismatched release challenge/publisher policy,
tampered receipt and handoff claims, and automatic-install denial.

CI executes on both **Linux and Windows** using ephemeral test-process
keys, and a static guard checks no production side effects. Neither job
runs an AION installer or accesses a human owner's device.

## Non-actions

- No production AION package built, signed or installed.
- No real publisher private key imported/generated/released.
- No release key registry, signed certificate or revocation authority
  established; no certificate chain claim.
- No independent GitHub build provenance attested beyond caller-declared
  digests (no SLSA/in-toto verification).
- No actual user PC, owner identity, Windows Registry, ACL, startup,
  service, microphone, webcam, process, network, deploy or Worker activity.
- No merge, deploy, or production persistence changes.

## Next step, separately reviewed

**AION Publisher Key Registry + Independent Build Provenance Contract V1**:
document key-approval and rotation policy, verification of external
build attestations and artifact publication, and owner approval boundary.
Even that design must not become a production trust anchor automatically.

Maximum status: `READY_FOR_AION_PUBLISHER_AND_BUILD_PROVENANCE_SECURITY_REVIEW`.
