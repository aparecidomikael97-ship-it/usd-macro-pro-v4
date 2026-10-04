# AION Biblioteca — real-app synthetic-login browser gate (Draft)

This change uses the REAL AtlasQuant `usd_macro_pro_v4_cloud.py` entry and existing PBKDF2 session/login, existing AION admin selector, and the actual static sandbox Library component. A synthetic local registry is generated strictly in the ephemeral CI process; this is NOT an authorized real-user test or a production deployment. No document preview, database access, external API keys, permanent accounts, uploads, approvals or indexing are enabled.

**Opt-in test only**: GitHub Actions job `aion-library-real-app-sandbox.yml` with `CI=true` and `ATLASQUANT_REAL_APP_SYNTHETIC=1`. The script itself forces `ATLASQUANT_ENV=SANDBOX`, required local login, disabled bootstrap preview, offline network-data smoke, and clears financial/news/AI/GitHub keys in the synthetic app process. It uses test-only `admin.ci` and `reader.ci` accounts. The temporary Streamlit server binds to 127.0.0.1:8594; no cloud/deployment endpoint is accessed.

## Coverage

1. Synthetic ADMIN login through the actual Streamlit form and `?aion=1` navigation; opt-in Library workspace and its warning/disabled document controls in Android-class 390x844 and desktop 1440x900 viewports.
2. Synthetic USER login; admin workspace must be absent even if `?aion=1` is requested.
3. Reboot synthetic app with flag disabled and log in ADMIN; Library workspace must remain absent.
4. Check Streamlit exceptions, browser JS exceptions and document width versus viewport; keep synthetic screenshots as short-lived GitHub artifacts. Screenshots should never contain real documents or credentials.

## Important boundaries

- This covers the actual app and session route, but still **does not** enable or verify any public document route. The static Library shell remains non-operational.
- The persisted PostgreSQL ACL adapter from #489 has passed isolated, real PostgreSQL CI tests, but still requires explicit trusted host assembly and deployment-reviewed injection into any future document route. No database is connected to this UI test.
- Startup of this large existing AtlasQuant app and legacy unrelated pages may be unstable independently of Library. Failure is reported rather than bypassed; do not claim an E2E pass unless GitHub run logs and screenshots confirm it.
- Do not upload the synthetic local app logs by default; they may include environmental diagnostics. Screenshots are synthetic and retained only 7 days.
- Requires code review, cross-tenant E2E with current RBAC, safety/security review and targeted user authorization before any production merge/deploy.

**Stack dependency**: Draft #489. Keep issue #477 open, never modify PR #472 Business or unrelated main deployment settings.
