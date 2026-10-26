# AION G101 — Ubuntu full canonical confirmation of G99/G100 and G90 dependency pins

Date: 2026-10-26. Stacked on G100 Draft #1591 documentation head 8280a65c9a1402379084e62761bed22b888656d1. This PR adds a verification workflow only, without editing runtime code or original canonical suite selectors.

## Source chain
- G90 Draft #1581 updated Streamlit/pypdf/Pillow dependency pins, eliminating 48 then-known package advisories in the tested environment.
- G94/G96/G98 (Draft #1585 / #1587 / #1589) fixed 26 durable SQLite connection scopes, six persistent nonce connection scopes and one synthetic schema-inspection test fixture, reducing original Windows canonical Quality native file-handle errors from 109 to zero.
- G99 Draft #1590 fixed exact-60-minute scanner staleness and a clock-dependent boundary test (12/12 PASS Windows and Ubuntu).
- G100 Draft #1591 corrected only the Python LAB Windows asyncio stdlib socketpair harness for internal self-pipe support, with five new positive/negative socket guard tests. Original Windows 6,449 Quality PASS, 368 Security unittest PASS, 2,824 pytest PASS plus one historical Windows skip. The Python test guard does NOT constitute an operating-system firewall, and subprocesses do not inherit it.

## Objective G101 evidence: all 3 jobs SUCCESS

[GitHub Actions run 40338947593](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40338947593), tested workflow source 0f62e810015705a1f753d0f449b743f9b1ad6410:

- Ubuntu original canonical Quality selector: 6449/6449 PASS, Ran 6449 tests in 69.655s, OK, job 121628002425, canonical workflow SHA256 67897c3b4340771ffb301f8779227f9bf93dfa115e9d1bc7142ec4cbcf33bfc0.
- Ubuntu original canonical Security unittest: 368/368 PASS, Ran 368 tests in 1.820s, OK, job 121628002167.
- Ubuntu original canonical Security pytest: 2825/2825 PASS, 2825 passed in 31.49s, job 121628002167.
- Ubuntu exact canonical package audit and critical Bandit selector: SUCCESS, pip-audit -r requirements.txt reported No known vulnerabilities found, job 121628002316. No scanner exception/ignore flags; pip check reported No broken requirements found.

## Combined reproducible local candidate state

Windows [G100 run 40337504265](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40337504265): 6449/6449 Quality PASS; 368/368 Security unittest PASS; 2824 pytest PASS + 1 historical Windows skip (not counted as passed). Five focused internal socket/egress tests PASS on both OS.
Ubuntu G101: 6449/6449 Quality PASS; 368/368 Security unittest PASS; 2825/2825 pytest PASS; zero known dependency findings in the current tested snapshot.

No original production live H0 acceptance or external-root enrollment occurred. Local Quality and dependency audit completion does NOT certify native SQLite VFS antirollback, immutable original business intent/identity, independent monotonic custody, externally pinned root or real provider first SEND outcome reconciliation. A184's five genuine external RED acceptance criteria remain open. Six P0 are **0/6 HOMOLOGATED; HARD NO-GO**.

NO MERGE, NO DEPLOY, NO WORKER, NO REAL SEND, NO FUNDS.
