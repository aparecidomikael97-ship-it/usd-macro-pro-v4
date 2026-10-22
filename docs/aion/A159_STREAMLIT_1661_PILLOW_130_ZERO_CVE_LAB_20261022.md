# AtlasQuant / AION — A159 Supported Streamlit + Pillow 13 security upgrade (LAB)

**22 October 2026. Draft for review. HARD NO-GO; 0/6 P0 homologated.**

## Root cause and newly released upstream fix

The previous A158 isolated fix upgraded `pypdf==6.19.0` to `6.21.1`, removing five of 29 pip-audit advisories. Its canonical Security Gate still identified **24 vulnerabilities in Pillow 12.3.0**. The existing `streamlit==1.64.0` metadata constrained `pillow<13,>=7.1.0`, and the 24 advisories required Pillow 13.0.0.

**A timely upstream compatibility fix now exists:** `streamlit==1.66.1`, published **2026-10-21**, declares `pillow<14,>=9.2.0` in the official wheel metadata. Thus Pillow 13.0.0 is a **supported** dependency without ignoring the resolver. Official evidence: https://pypi.org/pypi/streamlit/1.66.1/json and https://pypi.org/project/pillow/13.0.0/.

A159 updates only the relevant direct dependencies in the proposed PR:
- `streamlit==1.64.0` → `streamlit==1.66.1`
- `Pillow==13.0.0` added as an explicit exact security pin
- `pypdf==6.21.1` retained from A158
- All other existing direct pins unchanged.

The branch is based on A158 code; the PR for A159 targets `main` directly and includes the complete A158+A159 dependency remediation. **Neither PR has been merged or deployed.** The earlier partial-only Draft #1443 remains separate; do not merge both independently without an integration plan.

## Exact verified-source and runtime constraints

The A158 audit parser was strengthened to allow **only two reviewed pairings**: historical A158 `(Streamlit 1.64.0, Pillow transitive/unpinned)` and the A159 proposed `(Streamlit 1.66.1, Pillow==13.0.0)`. A random Streamlit release, unpinned Pillow major upgrade or mismatched audit JSON causes failure.

The full A159 gate (`tools/aion_p0_a159_supported_pillow13_zero_cve_lab.py`):
1. Reads `requirements.txt`, rejects variant drift, malformed pins, duplicate packages and unsupported combinations.
2. Cross-checks **actually installed** package metadata for exact Streamlit, Pillow and pypdf versions; checks Streamlit's actual Pillow specifier includes 13.0.0.
3. Executes `python -m pip_audit -r requirements.txt --format json` and requires verified zero-advisory exit status AND zero advisories for **all parsed packages**, with all directly pinned names present and no skipped/ambiguous package entries.
4. Emits a documentary statement `HARD_NO_GO_P0_EXTERNAL_H0_AND_OWNER_PROOFS_MISSING` even if the dependency scan is clean.

The pipeline runs **96 exact tests per platform**, including A158's 44 earlier checks and A159's 52 new tests: 40 adversarial version/audit/metadata checks plus 12 real in-memory image and Streamlit `AppTest` widgets/graphics smoke checks. Test runners fail closed on changed counts, exceptions or skips. A live `pip check` is required.

**Do not claim full security or full quality before independent canonical CI results.** The pipeline triggers the existing AION Core Security Gate and Quality suite by opening a PR against `main`. The official `pip-audit` security step remains unchanged: NO `--ignore-vuln`, NO `--no-deps`, NO bypass.

## Operational and acceptance limits

- A major Pillow update and minor Streamlit update can change UI, image format, font, browser, Plotly/Altair, Streamlit `AppTest`, and internal layout behavior. Complete Quality, actual browser and staging validations are mandatory before any deployment.
- A green dependency audit means only no vulnerabilities returned by the auditing feed at that particular instant. It does NOT prove no exploitability, no new advisories tomorrow, nor absence of unsafe image decoder behavior in untested real input.
- There is no independent D0/D1/D2 monotonic witness, trusted H0 reboot/restore exercise, owner FIDO2 signing enrollment, supplier committed/no-effect receipt, 6/6 P0 acceptance or live first-effect authorization.
- The separate main workflow-containment PR #1442 is still Draft; this library PR does NOT disable any scheduled Autopilot/Coleta jobs, change credentials or alter GitHub permissions.
- R$200 remains the GLOBAL approved cost ceiling. This PR authorizes no additional spend, provider account, GitHub merge, deploy or Worker action.

**HARD NO-GO; ZERO_AUTO_RESEND; 0/6 P0 homologated; Worker OFF.**
