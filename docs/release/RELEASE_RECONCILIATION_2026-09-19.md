# AtlasQuant — Release Reconciliation Snapshot

Snapshot date: 2026-09-19  
Comparison: `main...atlasquant-runtime`

## Current branch relationship

- Status: **diverged**
- Runtime ahead of `main`: **2337 commits**
- Runtime behind `main`: **470 commits**
- Merge base: `2432a32833426f53cf834d2245ac3bf2ce10a5a1`
- Changed files in comparison: **235**

## Drift classification

- Known mutable runtime/evidence files: **19**
- Unknown files under `dados/`: **0**
- Code/config/docs/workflow files: **216**

All currently changed `dados/` files are classified by `RUNTIME_MUTABLE_PATHS`; there are no unclassified runtime-data files in this snapshot.

## Main-only source reconciliation

Relative to the common merge base, `main` currently changes **25 files**. All 25 paths are now also present in the Runtime line of development: there are **0 main-only changed paths** remaining.

The three previously main-only source assets were copied without modifying their behavior:

- `.github/workflows/production-browser-smoke.yml`
- `.github/workflows/production-health.yml`
- `test_autopilot_quota_guard_v111.py`

Additional Paper Trading/Friction test coverage from `main` was merged into the stronger Runtime test suites rather than replacing Runtime safety tests.

This removes missing-file drift, but it does **not** mean the overlapping source files are conflict-free or safe to blind-merge. Content-level reconciliation remains required for the overlapping files.

## Release meaning

The branch is **not a safe blind-merge candidate**. The source/config/documentation/workflow differences still require reconciliation because `main` also advanced by 470 commits.

Known mutable runtime evidence can be ignored when reviewing source-code drift, but it must not be used to justify an automatic merge.

Controls remain:

- automatic branch merge: **disabled**
- automatic core promotion: **disabled**
- automatic weight changes: **disabled**
- real-order execution: **disabled**
- manual reconciliation/review: **required**

## Recommended release path

1. Keep `atlasquant-runtime` as the mutable runtime/evidence branch.
2. Use source checkpoints that exclude known mutable runtime files.
3. Reconcile content of the overlapping source files against current `main`; do not overwrite the hardened Runtime variants blindly.
4. Run the full Quality suite and headless/Autopilot smoke checks on the reconciled source.
5. Promote only after manual review of the reconciliation diff.

This document is a point-in-time audit note, not an automatic release approval.
