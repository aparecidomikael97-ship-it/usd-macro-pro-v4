# AION P0 A155 — Autopilot GitHub destination containment

**22 October 2026 · LAB / Draft only · HARD NO-GO · 0/6 P0 homologated**

## Security finding — not a real incident

The scheduled Autopilot writer **autopilot_v107.py / gh_put_bytes(path, raw, message)** originally admitted any ASCII path beginning with dados/ other than the exact dados/aion/checkpoint_master.json or syntactically malformed/escaped paths. A scheduled job holds repository contents:write, so an unintended caller/path can redirect this helper toward other runtime-data objects.

This exceeds the writer's 12 legitimate output destinations. It does **not** establish that an unauthorized live PUT took place: all test HTTP methods were MagicMocks, with no network, credentials, Worker, real product action or provider effects.

## RED-first evidence and bounded fix

- **Initial RED**: commit d2c619284c8afd7c7d9a7588f07731ca48985ef8, [Actions #39776327369](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39776327369). Ubuntu: 18/78 tests FAIL. The old prefix check admitted unrelated files, alternate AION states, input files and diagnostic folders.
- **Patch**: commit 685c6c1ff4ce3251d16f0691b3afe047e5e3acd5. Explicit immutable Python frozenset of exactly 12 literal GitHub paths; negative membership check before token presence and any GET/PUT.
- **Legacy harness compatibility**: A136b's AST-isolated test had no module-level constant. Its harness was changed at commit 10d941befed56d43b11a13e3658cea5a5fab08ac to read the allowed frozenset literal from source AST without importing/executing Autopilot.
- **Regression requirement**: 259 A145–A150 + 16 A151 + 55 A152 + 48 A153 + 73 A154 + 78 A155 = **529 cases per OS**, plus exact 32 producer error documentary audit. A target count never substitutes for checked CI results.

## Exactly 12 legitimate output paths

| Purpose | GitHub runtime destination |
|---|---|
| Scanner | dados/scanner_tecnico_v934.json |
| Daily D1 cache | dados/autopilot_daily_cache_v107.json |
| Derived timeframes | dados/atlasquant_research_timeframes_v1.json |
| Twelve Data cache | dados/twelve_series_v1108.json |
| Market map | dados/master_market_map_v102.json |
| Currency news | dados/currency_news_current_v107.json |
| Observational AION event journal | dados/aion_live_event_journal_v1.json |
| News CSV | dados/currency_news_validation_v1061.csv |
| Signal lifecycle | dados/atlasquant_signal_lifecycle_v1.json |
| Home snapshot | dados/atlasquant_home_snapshot_v1.json |
| Quota shadow | dados/atlasquant_quota_shadow_v1.json |
| Status | dados/autopilot_status_v107.json |

Input dados/autopilot_inputs_v107.json is intentionally NOT writable via this function. Path constants imported from other modules do not implicitly change this literal allowlist: new destinations require a reviewed PR and new evidence.

## What the adversarial tests prove locally

- Previously valid arbitrary dados/ sibling paths, alternative checkpoint aliases, aion outbox, other writer's feedback/flight-recorder paths, version suffixes and input-only files are denied **before mocked GET/PUT**.
- Original rejection of the exact checkpoint path, path traversal, dot and empty components, percent escapes, backslashes, query/fragment, nonstring paths and Unicode lookalikes remains.
- All twelve scheduled legitimate outputs retain the mocked GET → PUT behavior, preserving their current semantics.
- The JSON/CSV wrappers still delegate to the same guarded byte writer. Static checks require one exact literal allowlist and a top-level negative membership before the outgoing PUT.
- Previous A136/A154 checkpoint-writer protection and its NO-GO signal are not bypassed.

## Security boundaries NOT closed by A155

1. **GitHub contents:write remains repository-wide for its credential**: a separate program, API client, Action, git push or compromised process can still target other destinations. No effective provider-side per-path permission is proven.
2. This is not a complete call-graph/taint/cross-language audit of all GitHub writes. Other telemetry writers and scheduled workflows require separate validation.
3. The allowlist protects filenames, not JSON/CSV payload schema, authenticity, trusted issuer, monotonic freshness, owner consent or H0 replay prevention.
4. The checkpoint's A154 witness remains un-enrolled and deny-only. No external current-head attestation or independent D1/D2 custodian has been proven.
5. Historical Quality still has a RED reference baseline (51 FAIL, 34 ERROR), including 32 producer-proof errors (23 enrollment, eight causal effect receipts, one terminal no-effect fence). New isolated test passes do not close them.
6. No independent custody, live IAM permission evaluation, physical Windows H0 restore experiment, real provider-effect proof or paid infrastructure trial was authorized. R$200/month remains a **global** operational ceiling, not extra project money.

**Draft only. No merge, deploy, Worker, real runtime GitHub PUT, supplier action or expense. HARD NO-GO · 0/6 P0 · ZERO_AUTO_RESEND.**
