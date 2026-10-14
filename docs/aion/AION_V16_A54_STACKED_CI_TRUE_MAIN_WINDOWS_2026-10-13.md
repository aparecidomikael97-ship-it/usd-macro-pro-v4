# A.54 - strict stacked CI source contract and isolated Windows validation

LAB child of A52 60c61d959c81d50f6a9d6b5d1f1f932abf14844d; existing A50/A51 runtime and ten tests untouched. New checkout AQ_LAB_A54_CI_WINDOWS_20261013; original1676tracked hashes captured.

## Demonstrated RED and corrected policy
On exact A52, GITHUB_BASE_REF=A49 caused the original production-surface test FAIL. The old resolver also preferred origin/<PR target> over origin/main, which could hide cumulative stack changes. Local RED log retained, then main/A49/A52 real Git integration tests PASS on candidate;20transport-control adversarial unit cases PASS. Mock Git control fixtures are not independent source/owner/producer proof.

The gate accepts main or EXACT allowlisted A49/A52 branch names, pinning their commits and verifying A49 ancestry via Git. It confirms canonical public origin URL and ALWAYS freshly fetches origin/main; failed main fetch is fatal even if cached lab/main refs exist. Return immutable fetched main SHA, never target ref as production baseline. Unknown/missing PR base, changed pin, unavailable target, invalid SHA/ancestry/origin all deny. Production diff uses NUL-separated paths and no-renames so old protected paths/newline names cannot disappear; render.yaml, deploy and secret paths always reject, including case variants. Old render auto-off exception is no longer used. This is operational CI Git source selection, NOT independent owner enrollment or antirollback trust root. Existing historical ancestry and all other convergence assertions remain intact.

Both Quality and Security admit only the exact A52 parent branch in pull_request filters; no main retarget or false GITHUB_BASE_REF, no workflow_dispatch. A54 adversarial suite is mandatory before historical Security tests; A50/A51 dedicated steps unchanged.

## Windows separate boundary
No cryptography50.0.2/cffi/pycparser wheel files found by basename in Downloads and existing runtime/pip wheel cache directories. No venv or install performed on owner host. Local full A51 validation remains BLOCKED without verified offline dependency set. New explicitly labelled GitHub Windows ephemeral job creates a runner-local venv, installs pinned requirements (cryptography50.0.2 already required) and tzdata2026.3 for IANA support, then runs the intact ten A50/A51 tests with external sockets denied. Its result is hosted CI, never proof of physical owner installation/hardware/enrollment. No dependency-version changes in requirements.txt.

CI exact-head results must be read before claims. Preserve23OutboxERROR+8SagaERROR+21WorkerFAIL and A51 additional1ERROR+11FAIL. No skip/xfail/waiver, altered hard-stop, fabricated witness/producer receipt, keys, real login, deploy/Worker/Render/flags or spending. 0/6P0homologated;20/20FIRST_INSTALL HARD_NO_GO. Cloud1263 untouched.
