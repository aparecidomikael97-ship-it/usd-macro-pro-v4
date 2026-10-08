# AION — Windows Network Denial Physical Gate V1 (08/10/2026)

**STATUS: DRAFT / OFFLINE REVIEW ONLY. NO PACKAGE BUILD, NO INSTALLATION, NO NETWORK DENIAL PROVED.**

## Scope and directly observed PC evidence

This PR is stacked on **#1049** and inherits its existing twelve physical proof requirements; it further specifies the `WINDOWS_NETWORK_DENY_PHYSICAL_PROOF_REQUIRED` requirement.

On the owner's authorized Windows 11 Home computer, a non-mutating capability survey observed:
- Base Filtering Engine (BFE), Windows Firewall (`mpssvc`) and Defender (`WinDefend`) all running; Firewall profiles enabled. This is NOT process-scoped deny proof.
- `userenv!DeriveAppContainerSidFromAppContainerName` successfully derived a scratch identifier and immediately released the SID. **No AppContainer profile was created**. Availability of `CreateAppContainerProfile` does not imply an AppContainer process was launched.
- `FwpmEngineOpen0` + `FwpmEngineClose0` successfully opened and closed read-only sessions using **RPC_C_AUTHN_WINNT (10)** and **RPC_C_AUTHN_DEFAULT (0xffffffff)**. Initial experiment with unsupported authentication selector `0` returned Windows code `50`; corrected experiment returned `0`. Neither session installed filters; ability to open a WFP session does not authorize adding deny filters or mean rules would apply to an intended child.
- Prior controlled network attempt with a restricted impersonated token still reached a **local TCP IPv4 loopback listener**. Therefore prior token-only `network_deny_verified=FALSE`.
- Low-integrity Python run and temporary NTFS write denial were demonstrated in previous controlled tests. **Low integrity does NOT imply network deny or total read isolation**.

All observations in this document are *reports from a remotely controlled machine*, NOT independently authenticated measurements in the evidence format required by #1049. No permanent configuration, ACL, AppContainer profile, WFP filters, firewall rules or internet access were changed by the read-only API inventory.

## Recommendation and alternatives

**Primary candidate — AppContainer without network capabilities:** first investigate a child with zero network capabilities (no `internetClient`, private network client/server, loopback/debug exemptions), pinned executable, explicit scratch paths, OS job object limits, fixed subprocess policy. Microsoft documents that an AppContainer without network capability cannot access the network; however, Windows desktop compatibility, Python loader/DLL ACL and local/remote network behavior must be physically demonstrated. Creating a profile writes per-user folders/registry data, and is NOT authorized in this block. Future profile lifecycle requires specific approval, cleanup and inspection; no AppContainer profile exists from this PR.

**Alternative — WFP process-scoped deny in a dynamic session:** only as a specifically reviewed alternative when child network isolation is independently demonstrated. An open WFP session does not prove permission to add filters. A later build must target the intended child identity across outbound TCP, UDP, IPv4 and IPv6, cover DNS, proxy/loopback/broker paths and prevent launch without the filter successfully installed. Microsoft documents that objects in a dynamic WFP session are automatically deleted when the session ends, but this alone does not prove there is no policy race or that all traffic is blocked. Applying any real filter requires new explicit owner approval and a rollback plan.

## Required negative/positive network matrix

The V1 test planning module defines **16 mandatory surfaces**:
- TCP/UDP loopback on IPv4 and IPv6.
- TCP/UDP outbound on IPv4 and IPv6.
- DNS over TCP/UDP on IPv4 and IPv6.
- HTTP CONNECT proxy, SOCKS proxy, remote SMB/named pipes, inherited open socket handles.

A credible negative test requires a positive reachability control for the **same intended endpoint**, measured outside the sandbox in a separately authenticated collector. An unreachable route, local DNS failure, offline laptop or missing listener is not proof of OS blocking. The isolated child must then observe denial by the intended OS policy, not simply catch an arbitrary exception. Test both sockets and applicable alternate broker/IPC paths. User approval is needed before connecting to any external endpoint, changing Windows filter settings or creating AppContainer profiles. The initial localhost fixtures can be planned without internet but cannot alone verify all outbound surfaces.

## Fail-closed contract and status

`atlasquant_aion_windows_network_deny_evidence_gate_v1.py`:
- Accepts only two reviewed *candidate* implementations.
- Enforces exactly 16 records with unique names and strict result enums.
- Rejects any allowed, errored or unmeasured network surface, missing positive control, malformed record, or caller-asserted verification/build approval flag.
- Even when every record falsely claims `BLOCKED_BY_OS`, the maximum return is `DENY_EVIDENCE_CANDIDATE_UNTRUSTED`. It **NEVER sets `network_deny_verified`, `build_authorized`, `package_install_authorized`, `deploy_authorized` or `physical_proof_verified` to true.**
- Does not open sockets or install AppContainer/WFP rules.

`scripts/aion_windows_network_readonly_capabilities_v1.py`:
- Re-runs harmless AppContainer SID derivation+free and WFP engine open+close with supported RPC authentication on Windows.
- No network sockets, no creation/deletion of AppContainer profiles, no WFP filter, no firewall configuration. This is not physical isolation proof.

**Important:** even a complete physical network-deny result will not certify the whole sandbox until all 12 proof categories from #1049 are independently measured, signed, recent, and verified. Additional boundaries include process/tokens, child-escape prevention, writable areas, executable pinning, resource quotas and clean rollback.

## Approval boundary

All changes are GitHub Draft + isolated test runs. No merge, deploy, Render, Worker, installing AION, writing on owner PC, altering host security policy, creating AppContainer profile or WFP filter, enrolling keys, opening paid API, or raising temporary operating budget of R$200/month. Any controlled physical containment test that changes a Windows policy/profile requires new, specific owner authorization and explicit cleanup.

## Microsoft references

- AppContainer isolation: https://learn.microsoft.com/en-us/windows/win32/secauthz/appcontainer-isolation
- AppContainer creation, per-user profile side effects: https://learn.microsoft.com/en-us/windows/win32/api/userenv/nf-userenv-createappcontainerprofile
- AppContainer launch: https://learn.microsoft.com/en-us/windows/win32/secauthz/implementing-an-appcontainer
- WFP engine sessions: https://learn.microsoft.com/en-us/windows/win32/api/fwpmu/nf-fwpmu-fwpmengineopen0
- WFP dynamic session lifecycle: https://learn.microsoft.com/en-us/windows/win32/fwp/object-management
- AppContainer loopback exception configuration must NOT be modified as part of this test: https://learn.microsoft.com/en-us/windows/win32/api/netfw/nf-netfw-networkisolationsetappcontainerconfig
