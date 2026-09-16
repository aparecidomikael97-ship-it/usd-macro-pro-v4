"""AtlasQuant runtime-data branch policy.

Keeps operational snapshots/history out of code branches so scheduled writes do
not create artificial main/dev divergence. This module only resolves branch
names; it does not perform network I/O.
"""
from __future__ import annotations

from dataclasses import dataclass
import os


DEFAULT_RUNTIME_BRANCH = "atlasquant-runtime"
CODE_BRANCHES = frozenset({"main", "atlasquant-dev"})


def _clean(value: str | None) -> str:
    return str(value or "").strip()


def resolve_runtime_branch(
    explicit_data_branch: str | None = None,
    legacy_history_branch: str | None = None,
    *,
    default: str = DEFAULT_RUNTIME_BRANCH,
) -> str:
    """Resolve the branch used only for persistent runtime data.

    Migration rule:
    - GITHUB_DATA_BRANCH wins.
    - A legacy non-code branch remains valid.
    - Legacy values main/atlasquant-dev are redirected to atlasquant-runtime.
    """
    explicit=_clean(explicit_data_branch)
    if explicit:
        return explicit

    legacy=_clean(legacy_history_branch)
    if legacy and legacy not in CODE_BRANCHES:
        return legacy

    return _clean(default) or DEFAULT_RUNTIME_BRANCH


def runtime_branch_from_env() -> str:
    return resolve_runtime_branch(
        os.getenv("GITHUB_DATA_BRANCH", ""),
        os.getenv("GITHUB_BRANCH_HISTORICO", ""),
    )


def is_code_branch(branch: str | None) -> bool:
    return _clean(branch) in CODE_BRANCHES


@dataclass(frozen=True)
class RuntimeBranchPolicy:
    branch: str
    safe_for_runtime_writes: bool
    reason: str


def evaluate_runtime_branch(branch: str | None) -> RuntimeBranchPolicy:
    resolved=_clean(branch) or DEFAULT_RUNTIME_BRANCH
    if is_code_branch(resolved):
        return RuntimeBranchPolicy(
            branch=resolved,
            safe_for_runtime_writes=False,
            reason="Runtime data must not be persisted on a code branch.",
        )
    return RuntimeBranchPolicy(
        branch=resolved,
        safe_for_runtime_writes=True,
        reason="Dedicated runtime-data branch.",
    )


def require_runtime_branch(branch: str | None) -> str:
    policy=evaluate_runtime_branch(branch)
    if not policy.safe_for_runtime_writes:
        raise ValueError(policy.reason)
    return policy.branch
