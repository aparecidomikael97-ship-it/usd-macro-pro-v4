# AION P0 A158 — Supply-chain remediation split, NO-GO

**2026-10-22 · Isolated Draft against main · 0/6 P0 homologated · HARD NO-GO**

## Actual canonical pipeline evidence

PR #1442, based on main, ran [AION Core Security Gate #39783270491](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39783270491). The supply-chain step **FAILED** at `pip-audit -r requirements.txt`, reporting **29 vulnerabilities in two packages**:

| Resolved package on main | Detected advisories | Remediation according to the actual auditor |
|---|---:|---|
| `pypdf==6.19.0` (direct pin) | 5 | `pypdf==6.21.1` covers all listed fixes |
| `pillow==12.3.0` (transitive via Streamlit) | 24 | Auditor lists `pillow==13.0.0` |

This is a count of **reported CVE/advisory rows**, not independently established exploitability or a demonstration that attacks occurred. The existing `AION adversarial contracts` Security job passed, but overall Security remained RED. Separately [Quality #39783270601](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39783270601) completed **SUCCESS: 6117 tests, OK** in its selected test suite. This does NOT demonstrate that the whole historical 6895-test Quality canonical baseline or 6 P0 acceptance obligations are green.

## A158 isolated and deliberately partial remediation

- In `requirements.txt` change **only** `pypdf==6.19.0` → `pypdf==6.21.1`, the published security fix level from the actual CI advisories. Every other existing application dependency stays untouched.
- `tools/aion_p0_a158_dependency_audit_lab.py` runs actual **pip-audit** with machine-readable JSON; it rejects missing/ambiguous reports, altered pypdf or Streamlit pins, unreviewed transitive overrides, fake clean exit status, skipped packages, and any advisories remaining outside Pillow.
- The auditor output explicitly reports the observed `pillow` CVE count/IDs, Streamlit's installed Pillow requirement, and the unresolved Security verdict. If the `pypdf` advisories are truly cleared, only the **pypdf-specific partial gate** can be marked clean. Full canonical Security stays **NOT HOMOLOGATED**.
- Exactly **36 synthetic negative/adversarial tests** + **8 in-memory PDF/Pillow compatibility tests**, Windows+Ubuntu, target **44 per OS**. A real installed-environment `pip check` and independent `pip-audit -r requirements.txt` are required. This cannot upgrade/enable anything in production without separate merge approval.
- The existing main Security Gate is **NOT** changed, disabled or excepted. Expect it to stay RED while Pillow advisories remain; this is intentional.

## Why Pillow 13 is NOT silently pinned

The live Streamlit package version in main is `streamlit==1.64.0`. The project's release metadata presently constrains Pillow below the next major series (verify exactly from the installed package in CI), while the auditor's fixes for 24 Pillow advisories require 13.0.0. Even if a higher Streamlit release is available, changing a UI runtime dependency and a major image decoder carries broad API/compatibility risk. **A158 does not override this relationship, mask audit findings or declare Pillow fixed**.

A separate successor lab needs to demonstrate one of: an upstream Streamlit release formally compatible with a patched Pillow, an independently audited replacement/removal of the Pillow-dependent Streamlit path, or another supported and auditable upstream fix. It must run the complete UI, media, launch, app and security test matrix and preserve all controls. Suppressing 24 advisories or bypassing pip's resolver is NOT an approved solution.

## Production constraints and next work

- Still unverified: independently administered D0/D1/D2 monotonic witness, HUMAN_OWNER critical-action consent, provider causal receipt, real H0 first-uncertain-effect resolution, two original SQLite P0 defects, canonical Security and full Quality coverage.
- Workflow containment proposed in [Draft #1442](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/pull/1442) has **not been merged**. Autopilot/coleta still execute in main as separately evidenced in GitHub Actions. This dependency PR does **not** change jobs or suspend collection.
- Never claim that an A158 unit-test or pypdf-only success authorizes any worker, real PDF ingestion of untrusted files, provider effect, automatic resend, owner approval, new cost, merge or deploy.

**HARD NO-GO; 0/6 P0; ZERO_AUTO_RESEND; no merge, Worker, external supplier transaction, credentials or paid services.**
