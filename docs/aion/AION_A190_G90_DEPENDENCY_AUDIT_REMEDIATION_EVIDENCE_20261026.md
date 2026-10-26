# AION A190 G90 — Canonical dependency security-audit remediation (LAB)

**Date:** 2026-10-26. **Parent:** G89 Draft #1580 `b1808eb5bef98665c53ebf605cf3dcb322acdcb4`. **State:** Draft LAB; no main merge/deploy. **Six P0: 0/6 HOMOLOGATED — HARD NO-GO.**

## Measured supply-chain failure (before the patch)

[A184 G89 run 40324033279](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40324033279), security-audit candidate job `121575971051`, ran the unchanged canonical `pip-audit -r requirements.txt`. Output: **"Found 48 known vulnerabilities in 2 packages"**:
- `pypdf==6.19.0`: 11 entries; fixes listed by audit through `6.21.2`.
- `pillow==12.3.0`: 37 entries; fixes listed at `13.0.0`.

Old Streamlit `1.64.0` declared Pillow `>=7.1.0,<13`, so updating Pillow alone would violate the dependency resolver. This is NOT a scanner false-positive clearance or ignored advisory; the vulnerable versions were actually installed.

## Narrow upgraded dependency set

Original nine pinned requirements remain otherwise unchanged. The only updates to `requirements.txt` are:
- `streamlit 1.64.0 → 1.66.1`, whose published metadata allows Pillow `>=9.2.0,<14`.
- `pypdf 6.19.0 → 6.21.2`, released 2026-10-21 (upstream PDF parser security fixes).
- Explicit `pillow==13.0.0`, released 2026-10-16.

Upstream references: `https://pypi.org/project/streamlit/1.66.1/`, `https://pypi.org/project/pypdf/6.21.2/`, `https://pypi.org/project/pillow/13.0.0/`. These are public package facts, not authorization to use production APIs or real data.

## LAB acceptance (source commit `eb8dbc6aa8d0ea57ec2e6fa14c85693b79c9e097`)

[Dedicated G90 run 40325011742](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40325011742), dedicated GitHub Actions workflow `.github/workflows/aion-a190-g90-dependency-audit-lab.yml`:

- Ubuntu Python 3.12: `pip check` **PASS**. Exact installed package versions checked. In-memory synthetic PNG and PDF roundtrip/Streamlit import **PASS**. `pip-audit -r requirements.txt` reported **"No known vulnerabilities found"**. Same unchanged canonical Bandit high-severity selector returned success.
- Windows Python 3.12: `pip check` **PASS**. Exact package versions, synthetic PNG/PDF, Streamlit smoke **PASS**. Same `pip-audit` **"No known vulnerabilities found"** and canonical Bandit selector returned success.
- Ubuntu canonical Quality + Security on the **same upgraded exact code/dependency environment**: job `121579339384` **SUCCESS**. The original Quality selectors from `.github/workflows/quality-tests.yml` SHA256 `67897c3b4340771ffb301f8779227f9bf93dfa115e9d1bc7142ec4cbcf33bfc0` executed `Ran 6449 tests in 83.883s` and `OK`. The unchanged core Security gate SHA256 `927c30233f38f7727d5e15c5a78af3d31176d0ade1614aec0fc17b63fa132485` passed `Ran 368 tests in 1.706s`, `OK`, and `2825 passed in 29.87s` via pytest.
- **Entire G90 three-job workflow completed SUCCESS**, both OS security-audit jobs plus Ubuntu canonical Quality/Security. These are exact-source checks on `eb8dbc6aa8d0ea57ec2e6fa14c85693b79c9e097` (before documentation-only commits).

The prior 48 findings have been remediated in this **specific pinned runtime environment and advisory snapshot**. A clean pip-audit is NOT a general absence-of-vulnerabilities certificate: future advisories, transitive runtime environments, binary/source provenance, unseen import paths, or unsafe PDF/image parsing remain outside its proof.

## Scope and HARD NO-GO

This G90 change only updates dependency pins and adds a LAB verification workflow. No native SQLite VFS integration, operational Worker, real Send, custody enrollment, external signer/root or balance/account funds are created. Five explicit A184 external-red requirements (immutable original identity, independent custodian/monotonic checkpoint, externally pinned root, authenticated native live SQLite VFS version, rollback-proof native writes) remain RED; the six P0 are still 0/6 HOMOLOGATED.

**NO MERGE · NO DEPLOY · NO WORKER · NO PROVIDER SEND · NO REAL FUNDS · 0/6 P0 · HARD NO-GO.**
