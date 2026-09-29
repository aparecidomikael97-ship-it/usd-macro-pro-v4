# AION Supply Chain Baseline — 2026-09-29

Verified official GitHub refs:
- actions/checkout v7: 3d3c42e5aac5ba805825da76410c181273ba90b1
- actions/setup-python v7: 5fda3b95a4ea91299a34e894583c3862153e4b97
- actions/upload-artifact v7: 043fb46d1a93c77aae656e7c1c64a875d1fc6a0a

Observed green on Python 3.12:
- pip 26.2.1
- streamlit 1.64.0
- pandas 3.0.6
- numpy 2.5.3
- requests 2.34.2
- altair 6.3.0
- pyarrow 25.0.1
- pip-audit 2.10.1
- bandit 1.9.4
- cyclonedx-bom 7.4.0

This is a proven direct-dependency CI baseline. It is not a claim that every
transitive dependency is fully locked. The security workflow uploads the
resolved-environment CycloneDX SBOM as an artifact for later audit.
