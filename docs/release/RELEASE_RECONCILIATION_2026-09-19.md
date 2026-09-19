# AtlasQuant — Release Reconciliation Snapshot

Snapshot date: 2026-09-19  
Comparison: `main...atlasquant-runtime`

## Current branch relationship

- Status: **diverged**
- Runtime ahead of `main`: **2308 commits**
- Runtime behind `main`: **470 commits**
- Merge base: `2432a32833426f53cf834d2245ac3bf2ce10a5a1`
- Changed files in comparison: **231**

## Drift classification

- Known mutable runtime/evidence files: **19**
- Unknown files under `dados/`: **0**
- Code/config/docs/workflow files: **212**

All currently changed `dados/` files are classified by `RUNTIME_MUTABLE_PATHS`; there are no unclassified runtime-data files in this snapshot.

## Release meaning

The branch is **not a safe blind-merge candidate**. The 212 source/config/documentation/workflow changes require source reconciliation because `main` also advanced by 470 commits.

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
3. Reconcile source changes against current `main` in a dedicated integration/release branch.
4. Run the full Quality suite and headless/Autopilot smoke checks on the reconciled source.
5. Promote only after manual review of the reconciliation diff.

This document is a point-in-time audit note, not an automatic release approval.
