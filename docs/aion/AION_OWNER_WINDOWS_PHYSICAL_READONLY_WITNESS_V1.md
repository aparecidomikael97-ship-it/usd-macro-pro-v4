# AION Owner-Windows Physical Read-Only Witness V1

**DRAFT, read-only physical observation only. NOT a signed collector.**

This V1 is a narrowly scoped executable/token readback on the owner's Windows device, after explicit owner approval for this physical collector phase. A separate host controller supplies a fresh 256-bit hex nonce; the CLI flag is only a scope fence, not HUMAN_OWNER signature authentication.

## Probe
- Windows-only and explicit exact CLI option.
- Opens current Python image with CreateFileW READ and FILE_SHARE_READ only; this blocks new incompatible writer/delete opens, not preexisting writer handles.
- Native held-file identity + SHA-256 before/after, process image path via QueryFullProcessImageNameW.
- Native TokenIsAppContainer / IsTokenRestricted query, read-only.
- Closes handles, emits sanitized result without path, username, SID, environment or credentials.
- No child launch, process resume, network test, ACL/registry/firewall/WFP/AppContainer/profile or service changes.

## Truth boundary
Only the diagnostic Python process is observed. There is NO real AION
AppContainer probe, trusted owner/collector enrollment, independent signed
evidence, physical 12/12 #1049 proof or 16/16 #1087 network denial proof.

Maximum state: PHYSICAL_READONLY_OBSERVATION_UNTRUSTED

All authorization flags stay false: signature_trusted,
physical_attestation_verified, network_deny_verified, safe_to_resume,
installer_authorized, build_authorized, deploy_authorized.

## Owner Windows
After CI validation, run only in a unique fresh TEMP scratch file with
ephemeral challenge, collect sanitized output, and delete script/folder.
Never auto-install, merge, deploy or call external network.
Future signed physical collector still needs secure collector-key enrollment,
independent raw evidence verifier, physical antirollback and full network gates.