# Windows execution runbook — AION Core V1 formal closure

This runbook is for the authorized Windows host after it is online. It never generates, prints, uploads or stores a private key.

## Local paths

From the repository root in PowerShell:

```powershell
$Repo = (Get-Location).Path
$Ops = Join-Path $Repo "ops\aion_core_v1_formal_closure"
$Packet = Join-Path $Repo "ops\aion-core-v1-formal-closure\unsigned_v220_evidence_packet.json"
$Work = Join-Path $env:LOCALAPPDATA "AtlasQuantAION\formal-closure\work"
$NonceDb = Join-Path $env:LOCALAPPDATA "AtlasQuantAION\formal-closure\nonce_registry.sqlite3"
New-Item -ItemType Directory -Force -Path $Work | Out-Null
```

Keep both private Ed25519 keys outside `$Repo`.

## 0. Read-only readiness gate

Before generating any signing request, consuming any nonce or attempting any runtime write, use the tested PowerShell launcher. This is the preferred entrypoint for the real ceremony.

Prepare **public-only** certification and HUMAN_OWNER trust-root JSON files outside the repository. Private Ed25519 keys must never be passed to this tool, committed, printed, uploaded or placed in runtime JSON.

```powershell
$CertTrust = "<PUBLIC_CERTIFICATION_TRUST_ROOT_JSON>"
$OwnerTrust = "<PUBLIC_OWNER_TRUST_ROOT_JSON>"

.\ops\aion-core-v1-formal-closure\Start-AionCoreClosure.ps1 `
  -CertificationTrustRoot $CertTrust `
  -OwnerTrustRoot $OwnerTrust `
  -ExpectedRuntimeSha "020facc9991c5d2d4ce457e0840b04c875f8cfae" `
  -CheckRuntimeRead `
  -RequireWriteReady
```

The launcher invokes the underlying read-only readiness preflight and stops before REAL V2.20 signing.

Required state:

`READY_FOR_FORMAL_CLOSURE_CEREMONY`

Required safety flags:

- `private_key_loaded=false`
- `signature_performed=false`
- `nonce_consumed=false`
- `runtime_write_performed=false`
- `merge_authorized=false`
- `deploy_authorized=false`
- `worker_armed=false`
- `executes_action=false`

If the runtime SHA is no longer `020facc9991c5d2d4ce457e0840b04c875f8cfae`, **stop**. Reconcile the new runtime state and rebuild the ceremony baseline; never force the stale CAS value.


## 1. Validate unsigned V2.20

```powershell
python "$Ops\validate_unsigned_v220_packet.py" "$Packet"
```

Required state: `VALID_UNSIGNED_PACKET`.

Required digest: `sha256:14ca8f5231465136826518d9133092420c9f19f0f0de53e4c27634017419a72d`.

## 2. Export the 17 V2.20 messages for external certification signing

Create the public certification trust-root JSON from `certification_trust_root.public.example.json`.

Run `export_v220_signing_bundle.py` with a fresh certification key id/version and a fresh RFC3339 signing window. The tool writes `v220_signing_bundle.json` and never loads a private key.

External signer input is each `canonical_message_b64url`. The external signer returns a JSON object mapping all 17 dimension names to base64url Ed25519 signatures. Save that map outside the repository, for example `$Work\v220_signatures.json`.

Then assemble the signed evidence:

```powershell
python -m ops.aion_core_v1_formal_closure.apply_v220_signatures --bundle "$Work\v220_signing_bundle.json" --signatures "$Work\v220_signatures.json" --output "$Work\v220_signed_evidence.json"
```

## 3. Build V2.20 → V2.22

Run `prepare_v220_v222.py` with the signed evidence, public certification trust root, a fresh V2.22 ceremony id/nonce and a short validity window.

Required terminal prep state: `READY_FOR_REAL_V223_PERSISTENCE`.

The output directory contains:

- `v220_certification_manifest.json`
- `v221_owner_review.json`
- `logical_checkpoint_master.json`
- `v222_preflight.json`
- `formal_closure_prep_summary.json`

## 4. V2.23 dry-run and explicit write

First run `perform_v223_runtime_write.py` without `--execute-v223-write`, using the freshly observed official runtime SHA.

Required dry state: `READY_FOR_EXPLICIT_V223_WRITE`.

Only when the operator intentionally chooses to persist V2.23, rerun the same command with `--execute-v223-write`.

Required real state: `READY_FOR_OWNER_SIGNATURE_CEREMONY`.

If the write result is ambiguous, stop. Do not automatically retry.

## 5. Prepare V2.24 only when the HUMAN_OWNER signer is ready

Create the public owner trust-root JSON from `owner_trust_root.public.example.json`.

V2.24 has a maximum 180-second request window. Run `prepare_v224_owner_signature.py` only immediately before signing.

The output `v224_signing_bundle.json` contains the exact canonical owner acknowledgement message. Sign it externally with the HUMAN_OWNER private key and save only the returned public signature text outside the repo, e.g. `$Work\v224_signature.txt`.

## 6. Verify V2.24 and prepare exact V2.25 decision

Run `verify_v224_prepare_v225.py` with the durable nonce registry `$NonceDb`.

This step consumes the V2.24 nonce only after the decision request has already been fully prebuilt.

Choose exactly one decision:

- `APPROVE_CORE_FREEZE`
- `DENY_CORE_FREEZE`

The tool exports `v225_decision_signing_bundle.json`. Sign its canonical message externally and save the returned signature outside the repo, e.g. `$Work\v225_signature.txt`.

## 7. V2.26 dry-run

Run `perform_v225_v226.py` without `--execute-v226-write`.

The dry-run:

- re-reads the official runtime;
- requires the runtime SHA to still equal the V2.23 SHA;
- rebuilds the V2.25 request;
- cryptographically prechecks the V2.25 signature;
- does **not** consume the V2.25 decision nonce;
- does **not** write runtime state.

Required dry state: `READY_FOR_EXPLICIT_V226_WRITE`.

## 8. Explicit V2.26 write

Only when ready to durably record the already signed decision, rerun the same V2.26 command with `--execute-v226-write`.

This consumes the V2.25 decision nonce and attempts exactly one conditional runtime write.

Positive terminal states:

- `OWNER_DECISION_RECORD_PERSISTENCE_ATTESTED_APPROVE`
- `OWNER_DECISION_RECORD_PERSISTENCE_ATTESTED_DENY`

For APPROVE, the maximum new authority is still only `core_freeze_ceremony_eligible=true`.

Do not freeze, merge, deploy or arm the Global Worker from this runbook.

## Timing and replay rules

- V2.24/V2.25 windows are <= 180 seconds.
- Never pre-create those requests long in advance.
- Never reuse a consumed nonce.
- Keep `$NonceDb` outside the repository and durable across the ceremony.
- If runtime changes after V2.23, rebuild owner ceremony material before consuming the V2.25 nonce.
- If a V2.23/V2.26 write outcome is unknown, reconcile manually; never retry automatically.

## 9. Prepare the separate Core Freeze signature

Only a positive V2.26 APPROVE may enter this step. A DENY terminates the freeze path.

Run `prepare_core_freeze.py` only when the HUMAN_OWNER signer is ready, using:

- the full `v226_attestation.json`;
- the public owner trust root;
- a fresh freeze ceremony id;
- a fresh freeze nonce;
- a <= 180-second validity window;
- the HUMAN_OWNER key id/version.

Required state:

`READY_FOR_EXTERNAL_CORE_FREEZE_SIGNATURE`

Externally sign the exported canonical freeze message and save only the returned signature outside the repository, e.g. `$Work\core_freeze_signature.txt`.

## 10. Core Freeze dry-run

Run `perform_core_freeze.py` without `--execute-core-freeze`.

The dry-run:

- cryptographically verifies the third owner signature;
- re-reads the official runtime;
- requires its SHA and source digest to still equal the exact post-V2.26 runtime;
- does not consume the freeze nonce;
- does not write runtime state.

Required dry state:

`READY_FOR_EXPLICIT_CORE_FREEZE_WRITE`

## 11. Explicit Core Freeze write

Only after the owner intentionally chooses to execute the freeze, rerun the same command with:

`--execute-core-freeze`

This:

- claims the fresh freeze nonce in `$NonceDb`;
- attempts exactly one CAS write;
- persists `aion_core_freeze_v1`;
- requires receipt, read-after-write and write attribution;
- uses `allow_global_arming_transition=False`;
- never retries an ambiguous write automatically.

Required positive terminal state:

`CORE_FREEZE_PERSISTENCE_ATTESTED`

Then run:

`validate_post_freeze_boundary.py --freeze-attestation <core_freeze_attestation.json>`

Required boundary state:

`CORE_V1_FROZEN_RELEASE_BOUNDARIES_CLOSED`

At that point Core V1 may be formally frozen, but merge, deploy, Global Worker arming and Global Worker activation remain explicitly unauthorized and require separate ceremonies.
