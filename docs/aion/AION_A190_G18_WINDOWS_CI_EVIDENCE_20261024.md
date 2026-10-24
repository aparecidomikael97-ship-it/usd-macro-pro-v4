# A190 G18 — Windows native stdlib SQLite evidence, 2026-10-24

## Exact tested code and CI

- **Tested SHA:** `7419a0684a5842c9ee530180fd4520eff13b15af`.
- **GitHub Actions Windows run #40118568036:** https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40118568036
- **Job ID:** `120944966189`. Result **completed / success**; exact job log reviewed.
- Python 3.12.10 on Windows runner, Microsoft Visual C compiler discovered using `vswhere`; official SQLite SDK headers downloaded with pinned SHA3-256 `92281c86e2957f9b9305890f9ac04204caa7b677cc868dc326d942689df28e30`.
- **10/10 unittest methods passed**, no skip. All ten test names and evidence markers visible in the job log. The test result is an execution of ten distinct synthetic scenarios, not a production certification.
- Previous run **#40118407964 failed** due to hard-coded MSVC path; repaired by `vswhere`. Run **#40118467654** at SHA `a7cf9df924a0a5cb88c909c7e804fe2abaca496f` succeeded **9/9** before the additional adversarial test.
- Local Windows Python 3.12.10 / SQLite 3.49.1 independent path-anchor test succeeded on two synthetic same-marker cloned files. **No native C extension was compiled or loaded on the user's local machine**; native extension execution occurred only on the GitHub Windows runner.

## Security findings

- Native file identity from the **exact stdlib `sqlite3.Connection`** matches an independently opened Windows path for unchanged files; cloned file with same local marker has a different native identity; rogue preopened connection cannot borrow honest decoy's identity.
- Missing anchor and in-memory DB deny; extension loading is disabled after explicit registration; `SQLITE_DIRECTONLY` blocks SQL view use.
- **RED / expected vulnerability reproduced:** when a hostile host closes all connections and replaces the database with a cloned same-marker file, the new SQLite connection and the independently opened expected path both point to the **wrong content**. Native identity matches and the clone-only event is read. Exact marker: `G18_WIN32_CLOSED_FILE_REPLACEMENT=WRONG_CONTENT_NATIVE_MATCH_RED`. This is proof that local Win32 identity is **not** antirollback or content authenticity.
- WAL main-file match does **not** attest WAL/SHM, transaction atomicity, provider effects, external owner authentication, receipts, H0 or postcommit semantic idempotency.

## Gates

No integration into production SQLiteChatStore; unsigned native loadable extensions are unsafe and must never be loaded into AION runtime. No merge/main, deploy, Worker, provider, credential, customer, spend or external service. Quality/Security canonic suites not rerun in G18.

**0/6 P0 HOMOLOGATED · HARD NO-GO · UNCERTAIN · ZERO_AUTO_RESEND.**
