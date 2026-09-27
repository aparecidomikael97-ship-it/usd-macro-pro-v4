"""Read-only adversarial audit of the AION Developer chain.

Calls the existing in-memory contracts and classifies each probe as
PASS, GAP or BLOCKED_BY_DESIGN. It does not execute repository code, start a
process, use the network, edit existing files, commit, merge or deploy.
Temporary fixture files exist only for the structural scanner and are removed
before the report is returned.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import tempfile
from typing import Any, Callable, Mapping

from atlasquant_aion_developer_builder_sandbox import build_builder_sandbox_request
from atlasquant_aion_developer_correction import build_correction_plan
from atlasquant_aion_developer_diagnostics import diagnose_failure
from atlasquant_aion_developer_engine import new_development_workflow
from atlasquant_aion_developer_evidence_gate import (
    confirm_root_cause_human_review,
    evaluate_evidence_promotion,
)
from atlasquant_aion_developer_implementation import (
    approve_implementation_session,
    build_implementation_envelope,
    prepare_implementation_readiness,
)
from atlasquant_aion_developer_intelligence import (
    build_development_plan,
    scan_repository,
)
from atlasquant_aion_developer_manifest import (
    REQUIRED_MANDATORY_GATES,
    bind_builder_request_lineage,
    canonical_identity,
    implementation_base_manifest_id,
    implementation_readiness_manifest_id,
    release_sensitive_path,
)
from atlasquant_aion_developer_command_policy import (
    assert_command_policy_integrity,
    build_command_policy_contract,
)
from atlasquant_aion_developer_executable_pinning import (
    build_environment_contract,
    build_executable_pinning_spec,
    build_os_sandbox_design_review,
)
from atlasquant_aion_developer_content_attestation import attestation_for_documents
from atlasquant_aion_developer_executable_pinning import build_executable_pinning_spec
from atlasquant_aion_developer_principal_identity import (
    assert_independent_principals,
    classify_actor_pair,
    require_principal_id,
)
from atlasquant_aion_developer_package import build_developer_package
from atlasquant_aion_developer_patch_validation import validate_patch
from atlasquant_aion_developer_runner_contract import (
    MAX_MANDATORY_GATES,
    MAX_TEST_TARGETS,
    bind_runner_contract_ids,
    build_runner_contract,
)
from atlasquant_aion_developer_sandbox_preflight import (
    build_sandbox_preflight,
    expected_preflight_id,
)

SCHEMA = "ATLASQUANT_AION_DEVELOPER_ADVERSARIAL_AUDIT_V1"
CLASSIFICATIONS = ("PASS", "GAP", "BLOCKED_BY_DESIGN")
SEVERITIES = ("CRITICAL", "HIGH", "MEDIUM", "LOW")
_SECRET_SENTINEL = "supersecretvalue"
_TOKEN_SENTINEL = "ghp_ADVERSARIALAUDITOR1234567890"
_CREATED = "2026-09-27T12:00:00+00:00"


def _finding(
    invariant_id: str,
    module: str,
    description: str,
    classification: str,
    severity: str = "",
) -> dict[str, str]:
    if classification not in CLASSIFICATIONS:
        raise ValueError("invalid adversarial classification")
    if classification == "GAP" and severity not in SEVERITIES:
        raise ValueError("gap finding requires severity")
    if classification != "GAP":
        severity = ""
    return {
        "invariant_id": invariant_id,
        "module": module,
        "description": description,
        "classification": classification,
        "severity": severity,
    }


def _invoke(fn: Callable[[], Any]) -> tuple[str, Any]:
    try:
        return "ACCEPT", fn()
    except (TypeError, ValueError) as exc:
        return "REJECT", exc


def _blocked(invariant_id: str, module: str, description: str, fn: Callable[[], Any]) -> dict[str, str]:
    status, result = _invoke(fn)
    if status == "REJECT":
        return _finding(invariant_id, module, description, "BLOCKED_BY_DESIGN")
    state = ""
    if isinstance(result, Mapping):
        state = str(result.get("state") or "")
    return _finding(
        invariant_id,
        module,
        description + f" Aceito com estado {state or 'OK'}.",
        "GAP",
        "HIGH",
    )


class _World:
    def __init__(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        (root / "atlasquant_aion_admin.py").write_text(
            "def render():\n    return True\n",
            encoding="utf-8",
        )
        (root / "other_mod.py").write_text("VALUE = 1\n", encoding="utf-8")
        (root / "test_atlasquant_aion_admin.py").write_text(
            "import atlasquant_aion_admin\n"
            "def test_render():\n"
            "    assert atlasquant_aion_admin.render()\n",
            encoding="utf-8",
        )
        workflow = root / ".github" / "workflows"
        workflow.mkdir(parents=True)
        (workflow / "quality-tests.yml").write_text("name: quality\n", encoding="utf-8")
        release = root / "docs" / "release"
        release.mkdir(parents=True)
        (release / "NOTES.md").write_text("release note\n", encoding="utf-8")
        (root / ".env").write_text("TOKEN=not-a-real-secret\n", encoding="utf-8")
        (root / "linked.py").symlink_to(root / "atlasquant_aion_admin.py")
        self.root = root
        self.snapshot = scan_repository(root)
        self.package = self._package(changed=["atlasquant_aion_admin.py"])
        self.diagnostic = self._diagnostic("atlasquant_aion_admin.py")
        self.correction = build_correction_plan(self.snapshot, self.diagnostic, self.package)
        self.hypothesis = str(self.correction["hypotheses"][0]["label"])
        self.test_id = str(self.correction["test_candidates"][0])
        self.gate = self._gate(self.correction, ["atlasquant_aion_admin.py"])
        self.confirmed = confirm_root_cause_human_review(
            self.correction,
            self.gate,
            approved=True,
            reviewer_actor="root-cause-reviewer",
            review_evidence_refs=["review:cause"],
        )
        self.envelope = build_implementation_envelope(
            self.snapshot, self.package, self.confirmed,
        )
        self.ready = self._ready(self.envelope, "builder-a", "reviewer-b", "breaker-c", "Reverter a mudanca logica.")
        self.approved = self._approve(self.ready, "human-approver")

    def close(self) -> None:
        self._tmp.cleanup()

    def _package(self, *, branch: str = "cursor/admin-fix", changed: list[str] | None = None) -> dict[str, Any]:
        return build_developer_package(
            "Corrigir admin",
            self.snapshot,
            branch=branch,
            baseline_ref="base@a",
            candidate_ref="cursor/admin-fix@b",
            changed_paths=changed,
            created_at=_CREATED,
        )

    def _diagnostic(self, relative: str, extra: str = "") -> dict[str, Any]:
        log = (
            f"AssertionError: password={_SECRET_SENTINEL} "
            f"token={_TOKEN_SENTINEL}\n"
            "FAILED test_atlasquant_aion_admin.py::test_render\n"
            f'File "{self.root / relative}", line 1\n'
            + extra
        )
        return diagnose_failure(self.snapshot, log)

    def _gate(self, correction: Mapping[str, Any], changed: list[str]) -> dict[str, Any]:
        return evaluate_evidence_promotion(
            correction,
            hypothesis_label=self.hypothesis,
            test_id=self.test_id,
            before_state="FAIL",
            after_state="PASS",
            changed_files=changed,
            evidence_refs=["run:before", "run:after"],
            intervention_summary="Mudanca minima reproduziu a falha e o teste.",
            scope_preserved=True,
            snapshot_digest=self.snapshot["snapshot_digest"],
            diagnostic_id=self.diagnostic["diagnostic_id"],
        )

    def _ready(
        self,
        envelope: Mapping[str, Any],
        builder: str,
        reviewer: str,
        breaker: str,
        rollback: str,
    ) -> dict[str, Any]:
        return prepare_implementation_readiness(
            envelope,
            rollback_plan=rollback,
            builder_actor=builder,
            reviewer_actor=reviewer,
            breaker_actor=breaker,
            readiness_refs=["ready:scope"],
        )

    def _approve(self, ready: Mapping[str, Any], approver: str) -> dict[str, Any]:
        return approve_implementation_session(
            ready,
            approved=True,
            approver_actor=approver,
            approval_refs=["approval:implementation"],
        )

    def sandbox(self, implementation: Mapping[str, Any] | None = None, **kwargs: Any) -> dict[str, Any]:
        selected = self.approved if implementation is None else implementation
        revision = (
            selected.get("revision_contract")
            if isinstance(selected.get("revision_contract"), Mapping)
            else {}
        )
        args = {
            "branch": str(revision.get("branch") or "cursor/admin-fix"),
            "baseline_ref": str(revision.get("baseline_ref") or "base@a"),
            "candidate_ref": str(revision.get("candidate_ref") or "cursor/admin-fix@b"),
        }
        args.update(kwargs)
        return build_builder_sandbox_request(
            self.snapshot,
            selected,
            **args,
        )

    def chain_for(self, relative: str) -> dict[str, Any]:
        diagnostic = self._diagnostic(relative)
        package = self._package(changed=[relative])
        correction = build_correction_plan(self.snapshot, diagnostic, package)
        hypothesis = str(correction["hypotheses"][0]["label"])
        test_id = str(correction["test_candidates"][0])
        gate = evaluate_evidence_promotion(
            correction,
            hypothesis_label=hypothesis,
            test_id=test_id,
            before_state="FAIL",
            after_state="PASS",
            changed_files=[relative],
            evidence_refs=["run:before", "run:after"],
            intervention_summary="Mudanca minima no arquivo citado.",
            scope_preserved=True,
            snapshot_digest=self.snapshot["snapshot_digest"],
            diagnostic_id=diagnostic["diagnostic_id"],
        )
        confirmed = confirm_root_cause_human_review(
            correction,
            gate,
            approved=True,
            reviewer_actor="root-cause-reviewer",
            review_evidence_refs=["review:cause"],
        )
        envelope = build_implementation_envelope(self.snapshot, package, confirmed)
        ready = self._ready(envelope, "builder-a", "reviewer-b", "breaker-c", "Reverter a mudanca logica.")
        approved = self._approve(ready, "human-approver")
        request = build_builder_sandbox_request(
            self.snapshot,
            approved,
            branch="cursor/admin-fix",
            baseline_ref="base@a",
            candidate_ref="cursor/admin-fix@b",
        )
        return {"envelope": envelope, "approved": approved, "request": request}


def _lineage(world: _World) -> list[dict[str, str]]:
    findings = []
    other_snapshot = deepcopy(world.snapshot)
    other_snapshot["snapshot_digest"] = "REPO-CROSSED-SNAPSHOT"
    findings.append(_blocked(
        "lineage.crossed_snapshot",
        "atlasquant_aion_developer_correction",
        "Diagnostico e pacote de outro snapshot nao formam plano de correcao.",
        lambda: build_correction_plan(other_snapshot, world.diagnostic, world.package),
    ))
    findings.append(_blocked(
        "lineage.evidence_snapshot_mismatch",
        "atlasquant_aion_developer_evidence_gate",
        "Evidence gate rejeita snapshot digest diferente da correcao.",
        lambda: evaluate_evidence_promotion(
            world.correction,
            hypothesis_label=world.hypothesis,
            test_id=world.test_id,
            before_state="FAIL",
            after_state="PASS",
            changed_files=["atlasquant_aion_admin.py"],
            evidence_refs=["run:before", "run:after"],
            intervention_summary="Mudanca minima.",
            scope_preserved=True,
            snapshot_digest="REPO-STALE",
            diagnostic_id=world.diagnostic["diagnostic_id"],
        ),
    ))
    findings.append(_blocked(
        "lineage.evidence_diagnostic_mismatch",
        "atlasquant_aion_developer_evidence_gate",
        "Evidence gate rejeita diagnostic_id de outro envelope.",
        lambda: evaluate_evidence_promotion(
            world.correction,
            hypothesis_label=world.hypothesis,
            test_id=world.test_id,
            before_state="FAIL",
            after_state="PASS",
            changed_files=["atlasquant_aion_admin.py"],
            evidence_refs=["run:before", "run:after"],
            intervention_summary="Mudanca minima.",
            scope_preserved=True,
            snapshot_digest=world.snapshot["snapshot_digest"],
            diagnostic_id="DEVFAIL-OTHER",
        ),
    ))
    other_package = deepcopy(world.package)
    other_package["package_id"] = "DEVPACK-OTHER"
    findings.append(_blocked(
        "lineage.implementation_package_mismatch",
        "atlasquant_aion_developer_implementation",
        "Envelope de implementacao rejeita correcao ligada a outro pacote.",
        lambda: build_implementation_envelope(world.snapshot, other_package, world.confirmed),
    ))
    other_impl = deepcopy(world.approved)
    other_impl["lineage"] = dict(other_impl["lineage"])
    other_impl["lineage"]["snapshot_digest"] = "REPO-OTHER"
    findings.append(_blocked(
        "lineage.builder_digest_mismatch",
        "atlasquant_aion_developer_builder_sandbox",
        "Builder request rejeita snapshot digest diferente da autorizacao.",
        lambda: build_builder_sandbox_request(
            world.snapshot,
            other_impl,
            branch="cursor/admin-fix",
            baseline_ref="base@a",
            candidate_ref="cursor/admin-fix@c",
        ),
    ))
    replay_correction = deepcopy(world.correction)
    replay_correction["correction_id"] = "DEVCORR-OTHER"
    findings.append(_blocked(
        "replay.gate_other_correction",
        "atlasquant_aion_developer_evidence_gate",
        "Gate de uma correcao nao confirma outra correcao.",
        lambda: confirm_root_cause_human_review(
            replay_correction,
            world.gate,
            approved=True,
            reviewer_actor="root-cause-reviewer",
            review_evidence_refs=["review:cause"],
        ),
    ))

    expanded = deepcopy(world.correction)
    expanded["target_files"] = ["other_mod.py", "atlasquant_aion_admin.py"]
    status, confirmed = _invoke(lambda: confirm_root_cause_human_review(
        expanded,
        world.gate,
        approved=True,
        reviewer_actor="root-cause-reviewer",
        review_evidence_refs=["review:cause"],
    ))
    reached_ready = False
    if status == "ACCEPT" and isinstance(confirmed, Mapping):
        status2, envelope = _invoke(lambda: build_implementation_envelope(
            world.snapshot, world.package, confirmed,
        ))
        if status2 == "ACCEPT" and isinstance(envelope, Mapping):
            files = list((envelope.get("scope") or {}).get("source_files") or [])
            reached_ready = "other_mod.py" in files
    findings.append(_finding(
        "replay.gate_not_bound_to_targets",
        "atlasquant_aion_developer_evidence_gate",
        "O gate nao amarra a lista de alvos. Uma copia da correcao com target_files ampliado reutiliza o mesmo gate e o envelope passa a incluir other_mod.py."
        if reached_ready else
        "O gate permanece amarrado aos alvos avaliados.",
        "GAP" if reached_ready else "BLOCKED_BY_DESIGN",
        "HIGH" if reached_ready else "",
    ))

    stale = deepcopy(world.snapshot)
    stale["files"] = list(stale["files"]) + [{
        "path": "injected.py",
        "category": "MODULE",
        "risk_tags": [],
    }]
    mutated = deepcopy(world.approved)
    mutated["scope"] = deepcopy(mutated["scope"])
    mutated["scope"]["editable_files"] = list(mutated["scope"]["editable_files"]) + ["injected.py"]
    mutated["scope"]["source_files"] = list(mutated["scope"]["source_files"]) + ["injected.py"]
    status, request = _invoke(lambda: build_builder_sandbox_request(
        stale,
        mutated,
        branch="cursor/admin-fix",
        baseline_ref="base@a",
        candidate_ref="cursor/admin-fix@c",
        requested_files=["atlasquant_aion_admin.py", "injected.py"],
    ))
    accepted = (
        status == "ACCEPT"
        and isinstance(request, Mapping)
        and request.get("state") == "READY_FOR_BUILDER_SANDBOX"
        and "injected.py" in list((request.get("scope") or {}).get("requested_files") or [])
    )
    findings.append(_finding(
        "lineage.stale_snapshot_after_authorization",
        "atlasquant_aion_developer_builder_sandbox",
        "O digest do snapshot nao e recalculado. Arquivo injetado depois da autorizacao entra no request READY."
        if accepted else
        "Snapshot alterado depois da autorizacao nao entra no request.",
        "GAP" if accepted else "BLOCKED_BY_DESIGN",
        "HIGH" if accepted else "",
    ))
    return findings


def _scope(world: _World) -> list[dict[str, str]]:
    findings = [
        _blocked(
            "scope.outside_editable",
            "atlasquant_aion_developer_builder_sandbox",
            "Arquivo fora da lista editavel nao entra no builder request.",
            lambda: world.sandbox(requested_files=["atlasquant_aion_admin.py", "other_mod.py"]),
        ),
        _blocked(
            "scope.unknown_path",
            "atlasquant_aion_developer_builder_sandbox",
            "Arquivo inexistente no snapshot e rejeitado pelo builder.",
            lambda: world.sandbox(requested_files=["atlasquant_aion_admin.py", "missing.py"]),
        ),
        _blocked(
            "scope.traversal_path",
            "atlasquant_aion_developer_builder_sandbox",
            "Caminho com ../ e rejeitado pelo builder.",
            lambda: world.sandbox(requested_files=["../etc/passwd"]),
        ),
        _blocked(
            "scope.absolute_path",
            "atlasquant_aion_developer_builder_sandbox",
            "Caminho absoluto e rejeitado pelo builder.",
            lambda: world.sandbox(requested_files=["/etc/passwd"]),
        ),
        _blocked(
            "files.new_path",
            "atlasquant_aion_developer_builder_sandbox",
            "Arquivo novo fora do snapshot e rejeitado pelo builder.",
            lambda: world.sandbox(requested_files=["brand_new.py"]),
        ),
    ]
    plan = build_development_plan(
        "ampliar",
        world.snapshot,
        branch="cursor/admin-fix",
        baseline_ref="base@a",
        changed_paths=["../etc/passwd", "missing.py", "/tmp/outside.py"],
    )
    leaked = [path for path in plan["impacted_files"] if path in {"../etc/passwd", "missing.py", "/tmp/outside.py"}]
    findings.append(_finding(
        "scope.plan_records_outside_snapshot",
        "atlasquant_aion_developer_intelligence",
        "O plano registra caminhos fora do snapshot: " + ", ".join(leaked) + "."
        if leaked else
        "O plano recusa caminhos fora do snapshot.",
        "GAP" if leaked else "BLOCKED_BY_DESIGN",
        "MEDIUM" if leaked else "",
    ))
    package = world._package(changed=["atlasquant_aion_admin.py", "../etc/passwd"])
    diagnostic = world._diagnostic("atlasquant_aion_admin.py")
    correction = build_correction_plan(world.snapshot, diagnostic, package)
    kept = "../etc/passwd" in list(correction.get("target_files") or [])
    findings.append(_finding(
        "scope.correction_excludes_unknown",
        "atlasquant_aion_developer_correction",
        "O plano de correcao exclui caminho desconhecido do snapshot."
        if not kept else
        "O plano de correcao manteve caminho fora do snapshot.",
        "GAP" if kept else "BLOCKED_BY_DESIGN",
        "HIGH" if kept else "",
    ))
    mutated = deepcopy(world.approved)
    mutated["scope"] = deepcopy(mutated["scope"])
    mutated["scope"]["editable_files"] = list(mutated["scope"]["editable_files"]) + ["other_mod.py"]
    mutated["scope"]["source_files"] = list(mutated["scope"]["source_files"]) + ["other_mod.py"]
    status, request = _invoke(lambda: build_builder_sandbox_request(
        world.snapshot,
        mutated,
        branch="cursor/admin-fix",
        baseline_ref="base@a",
        candidate_ref="cursor/admin-fix@c",
        requested_files=["atlasquant_aion_admin.py", "other_mod.py"],
    ))
    expanded = (
        status == "ACCEPT"
        and isinstance(request, Mapping)
        and request.get("state") == "READY_FOR_BUILDER_SANDBOX"
        and "other_mod.py" in list((request.get("scope") or {}).get("requested_files") or [])
    )
    findings.append(_finding(
        "scope.post_authorization_expansion",
        "atlasquant_aion_developer_builder_sandbox",
        "Depois da autorizacao, ampliar editable_files inclui other_mod.py em request READY."
        if expanded else
        "Ampliacao de escopo depois da autorizacao e rejeitada.",
        "GAP" if expanded else "BLOCKED_BY_DESIGN",
        "HIGH" if expanded else "",
    ))
    outside = evaluate_evidence_promotion(
        world.correction,
        hypothesis_label=world.hypothesis,
        test_id=world.test_id,
        before_state="FAIL",
        after_state="PASS",
        changed_files=["atlasquant_aion_admin.py", "not-in-scope.py"],
        evidence_refs=["run:before", "run:after"],
        intervention_summary="Tentativa de ampliar.",
        scope_preserved=True,
        snapshot_digest=world.snapshot["snapshot_digest"],
        diagnostic_id=world.diagnostic["diagnostic_id"],
    )
    blocked_outside = outside.get("state") == "INSUFFICIENT_EVIDENCE"
    findings.append(_finding(
        "scope.evidence_outside_files",
        "atlasquant_aion_developer_evidence_gate",
        "Evidence gate nao promove causa quando ha arquivo fora do escopo."
        if blocked_outside else
        "Evidence gate promove causa com arquivo fora do escopo.",
        "BLOCKED_BY_DESIGN" if blocked_outside else "GAP",
        "" if blocked_outside else "HIGH",
    ))
    return findings


def _branches(world: _World) -> list[dict[str, str]]:
    findings = []
    exact = [
        "main", "MAIN", " main ", "master", "MASTER", "prod", "PROD",
        "production", "Production", "live", "LIVE", "main\x00",
    ]
    accepted_exact = []
    for branch in exact:
        status, _result = _invoke(lambda branch=branch: world.sandbox(
            branch=branch,
            candidate_ref="cursor/admin-fix@c",
        ))
        if status == "ACCEPT":
            accepted_exact.append(branch.replace("\x00", "\\x00"))
    findings.append(_finding(
        "branch.exact_forbidden",
        "atlasquant_aion_developer_builder_sandbox",
        "Variacoes exatas de main, master, prod, production e live sao rejeitadas."
        if not accepted_exact else
        "Branches proibidas aceitas: " + ", ".join(accepted_exact) + ".",
        "BLOCKED_BY_DESIGN" if not accepted_exact else "GAP",
        "" if not accepted_exact else "CRITICAL",
    ))
    refs = ["refs/heads/main", "refs/heads/MAIN", "refs/heads/master"]
    accepted_refs = []
    for branch in refs:
        status, _result = _invoke(lambda branch=branch: world.sandbox(
            branch=branch,
            candidate_ref="cursor/admin-fix@c",
        ))
        if status == "ACCEPT":
            accepted_refs.append(branch)
    findings.append(_finding(
        "branch.refs_heads_main_master",
        "atlasquant_aion_developer_builder_sandbox",
        "refs/heads/main e refs/heads/master sao rejeitados."
        if not accepted_refs else
        "Refs de main/master aceitas: " + ", ".join(accepted_refs) + ".",
        "BLOCKED_BY_DESIGN" if not accepted_refs else "GAP",
        "" if not accepted_refs else "CRITICAL",
    ))
    aliases = [
        "refs/heads/production", "refs/heads/prod", "refs/heads/live", "origin/main",
    ]
    accepted_aliases = []
    for branch in aliases:
        status, result = _invoke(lambda branch=branch: world.sandbox(
            branch=branch,
            candidate_ref="cursor/admin-fix@c",
        ))
        if status == "ACCEPT" and isinstance(result, Mapping) and result.get("state") == "READY_FOR_BUILDER_SANDBOX":
            accepted_aliases.append(branch)
    findings.append(_finding(
        "branch.equivalent_refs",
        "atlasquant_aion_developer_builder_sandbox",
        "Refs equivalentes de producao/main aceitas: " + ", ".join(accepted_aliases) + "."
        if accepted_aliases else
        "Refs equivalentes de producao/main sao rejeitadas.",
        "GAP" if accepted_aliases else "BLOCKED_BY_DESIGN",
        "HIGH" if accepted_aliases else "",
    ))
    prefixes = ["main/hotfix", "production/hotfix"]
    accepted_prefixes = []
    for branch in prefixes:
        status, result = _invoke(lambda branch=branch: world.sandbox(
            branch=branch,
            candidate_ref="cursor/admin-fix@c",
        ))
        if status == "ACCEPT" and isinstance(result, Mapping) and result.get("state") == "READY_FOR_BUILDER_SANDBOX":
            accepted_prefixes.append(branch)
    findings.append(_finding(
        "branch.prefix_bypass",
        "atlasquant_aion_developer_builder_sandbox",
        "Prefixos de branch protegida aceitos: " + ", ".join(accepted_prefixes) + "."
        if accepted_prefixes else
        "Prefixos main/ e production/ sao rejeitados.",
        "GAP" if accepted_prefixes else "BLOCKED_BY_DESIGN",
        "HIGH" if accepted_prefixes else "",
    ))
    status, _result = _invoke(lambda: world.sandbox(branch="ｍain", candidate_ref="cursor/admin-fix@c"))
    findings.append(_finding(
        "branch.fullwidth_rejected",
        "atlasquant_aion_developer_builder_sandbox",
        "Branch com caractere fullwidth nao passa na validacao."
        if status == "REJECT" else
        "Branch fullwidth foi aceita.",
        "BLOCKED_BY_DESIGN" if status == "REJECT" else "GAP",
        "" if status == "REJECT" else "HIGH",
    ))
    package_status, _package = _invoke(lambda: world._package(branch="main"))
    engine_status, _engine = _invoke(lambda: new_development_workflow(
        "pedido",
        branch="MAIN",
        baseline_ref="base@a",
        requested_by="auditor",
        created_at=_CREATED,
    ))
    early = package_status == "ACCEPT" or engine_status == "ACCEPT"
    findings.append(_finding(
        "branch.early_layers_accept_main",
        "atlasquant_aion_developer_package",
        "Pacote e engine aceitam branch main/MAIN. O builder rejeita a forma exata, mas o registro anterior nao."
        if early else
        "Pacote e engine rejeitam branch main.",
        "GAP" if early else "BLOCKED_BY_DESIGN",
        "MEDIUM" if early else "",
    ))
    return findings


def _candidates(world: _World) -> list[dict[str, str]]:
    findings = []
    unbound = []
    for candidate in ("main", "main@c", "cursor/other@c", "CURSOR/ADMIN-FIX@c"):
        status, result = _invoke(lambda candidate=candidate: world.sandbox(candidate_ref=candidate))
        if status == "ACCEPT" and isinstance(result, Mapping) and result.get("state") == "READY_FOR_BUILDER_SANDBOX":
            unbound.append(candidate)
    findings.append(_finding(
        "candidate.unbound_ref",
        "atlasquant_aion_developer_builder_sandbox",
        "candidate_ref nao precisa pertencer a branch isolada. Aceitos: " + ", ".join(unbound) + "."
        if unbound else
        "candidate_ref fora da branch isolada e rejeitado.",
        "GAP" if unbound else "BLOCKED_BY_DESIGN",
        "HIGH" if unbound else "",
    ))
    findings.append(_blocked(
        "candidate.baseline_equal",
        "atlasquant_aion_developer_builder_sandbox",
        "baseline_ref igual a candidate_ref e rejeitado.",
        lambda: world.sandbox(baseline_ref="same-ref", candidate_ref="same-ref"),
    ))
    findings.append(_blocked(
        "candidate.baseline_whitespace_equal",
        "atlasquant_aion_developer_builder_sandbox",
        "baseline e candidate iguais apos normalizar espacos sao rejeitados.",
        lambda: world.sandbox(baseline_ref=" same-ref ", candidate_ref="same-ref"),
    ))
    status, result = _invoke(lambda: world.sandbox(baseline_ref="SameRef", candidate_ref="sameref"))
    case_accepted = status == "ACCEPT" and isinstance(result, Mapping) and result.get("state") == "READY_FOR_BUILDER_SANDBOX"
    findings.append(_finding(
        "candidate.baseline_casefold_equal",
        "atlasquant_aion_developer_builder_sandbox",
        "baseline_ref e candidate_ref que so diferem na caixa sao aceitos como distintos."
        if case_accepted else
        "baseline e candidate iguais por caixa sao rejeitados.",
        "GAP" if case_accepted else "BLOCKED_BY_DESIGN",
        "HIGH" if case_accepted else "",
    ))
    return findings


def _identities(world: _World) -> list[dict[str, str]]:
    findings = []

    def _reach(builder: str, reviewer: str, breaker: str) -> str:
        status, ready = _invoke(lambda: world._ready(
            world.envelope, builder, reviewer, breaker, "Reverter a mudanca logica.",
        ))
        if status == "REJECT":
            return "REJECT"
        status, approved = _invoke(lambda: world._approve(ready, "human-approver"))
        if status == "REJECT":
            return "REJECT"
        status, request = _invoke(lambda: world.sandbox(approved))
        if status == "ACCEPT" and isinstance(request, Mapping) and request.get("state") == "READY_FOR_BUILDER_SANDBOX":
            return "READY"
        return "REJECT"

    same = _reach("same-actor", "same-actor", "same-actor")
    findings.append(_finding(
        "identity.exact_duplicate",
        "atlasquant_aion_developer_implementation",
        "Builder, reviewer e breaker identicos sao rejeitados."
        if same == "REJECT" else
        "Atores identicos chegaram ao builder.",
        "BLOCKED_BY_DESIGN" if same == "REJECT" else "GAP",
        "" if same == "REJECT" else "CRITICAL",
    ))
    spaced = _reach("Alice", " Alice ", "Alice")
    findings.append(_finding(
        "identity.whitespace_duplicate",
        "atlasquant_aion_developer_implementation",
        "A mesma identidade com espacos extras e rejeitada."
        if spaced == "REJECT" else
        "Espacos extras contornam a independencia.",
        "BLOCKED_BY_DESIGN" if spaced == "REJECT" else "GAP",
        "" if spaced == "REJECT" else "HIGH",
    ))
    variants = (
        ("identity.case_variants", "Alice", "alice", "ALICE", "Caixa diferente conta como tres atores."),
        ("identity.unicode_nfkc", "ﬁle", "file", "other", "Ligatura NFKC conta como ator distinto de file."),
        ("identity.fullwidth", "Ａlice", "Alice", "other", "Caractere fullwidth conta como ator distinto."),
        ("identity.combining", "e\u0301", "é", "other", "Marca combinante conta como ator distinto da forma composta."),
    )
    for invariant_id, builder, reviewer, breaker, description in variants:
        reached = _reach(builder, reviewer, breaker)
        findings.append(_finding(
            invariant_id,
            "atlasquant_aion_developer_implementation",
            description + " O request fica READY."
            if reached == "READY" else
            "A variacao de identidade foi rejeitada.",
            "GAP" if reached == "READY" else "BLOCKED_BY_DESIGN",
            "CRITICAL" if reached == "READY" else "",
        ))
    return findings


def _authorization(world: _World) -> list[dict[str, str]]:
    findings = [
        _blocked(
            "auth.approved_false",
            "atlasquant_aion_developer_implementation",
            "approved=False nao autoriza implementacao.",
            lambda: approve_implementation_session(
                world.ready, approved=False, approver_actor="human-approver", approval_refs=["approval:1"],
            ),
        ),
        _blocked(
            "auth.approved_string",
            "atlasquant_aion_developer_implementation",
            "approved='true' nao autoriza implementacao.",
            lambda: approve_implementation_session(
                world.ready, approved="true", approver_actor="human-approver", approval_refs=["approval:1"],
            ),
        ),
        _blocked(
            "auth.missing",
            "atlasquant_aion_developer_builder_sandbox",
            "Builder request sem bloco de autorizacao e rejeitado.",
            lambda: world.sandbox({k: v for k, v in world.approved.items() if k != "authorization"}),
        ),
    ]
    forged = deepcopy(world.approved)
    forged["authorization"] = dict(forged["authorization"])
    forged["authorization"]["human_approved"] = False
    findings.append(_blocked(
        "auth.human_flag_false",
        "atlasquant_aion_developer_builder_sandbox",
        "human_approved falso no bloco de autorizacao e rejeitado.",
        lambda: world.sandbox(forged),
    ))
    replay = deepcopy(world.approved)
    replay["envelope_id"] = "DEVIMPL-OTHERENVELOPE01"
    replay["lineage"] = dict(replay["lineage"])
    replay["lineage"]["correction_id"] = "DEVCORR-OTHER"
    status, request = _invoke(lambda: world.sandbox(replay))
    replayed = status == "ACCEPT" and isinstance(request, Mapping) and request.get("state") == "READY_FOR_BUILDER_SANDBOX"
    findings.append(_finding(
        "auth.replay_other_envelope",
        "atlasquant_aion_developer_builder_sandbox",
        "O bloco de autorizacao de um envelope e aceito em outro envelope com o mesmo snapshot."
        if replayed else
        "Autorizacao de outro envelope e rejeitada.",
        "GAP" if replayed else "BLOCKED_BY_DESIGN",
        "HIGH" if replayed else "",
    ))
    stolen = deepcopy(world.approved)
    stolen["authorization"] = dict(stolen["authorization"])
    stolen["authorization"]["authorization_id"] = "DEVAUTH-STOLENID012345"
    stolen["envelope_id"] = "DEVIMPL-DIFFERENTENVELOPE"
    status, request = _invoke(lambda: world.sandbox(stolen))
    stolen_ok = (
        status == "ACCEPT"
        and isinstance(request, Mapping)
        and request.get("state") == "READY_FOR_BUILDER_SANDBOX"
        and str((request.get("lineage") or {}).get("implementation_authorization_id") or "") == "DEVAUTH-STOLENID012345"
    )
    findings.append(_finding(
        "auth.stolen_authorization_id",
        "atlasquant_aion_developer_builder_sandbox",
        "authorization_id nao e recalculado. Um id substituido segue para o request READY."
        if stolen_ok else
        "authorization_id substituto e rejeitado.",
        "GAP" if stolen_ok else "BLOCKED_BY_DESIGN",
        "HIGH" if stolen_ok else "",
    ))
    status, approved = _invoke(lambda: world._approve(world.ready, "builder-a"))
    self_approved = (
        status == "ACCEPT"
        and isinstance(approved, Mapping)
        and approved.get("implementation_authorized") is True
        and str((approved.get("authorization") or {}).get("approver_actor") or "") == "builder-a"
    )
    findings.append(_finding(
        "auth.approver_is_builder",
        "atlasquant_aion_developer_implementation",
        "O aprovador humano pode ser o proprio builder."
        if self_approved else
        "O aprovador humano nao pode ser o builder.",
        "GAP" if self_approved else "BLOCKED_BY_DESIGN",
        "MEDIUM" if self_approved else "",
    ))
    return findings


def _rollback_and_tests(world: _World) -> list[dict[str, str]]:
    findings = [
        _blocked(
            "rollback.empty",
            "atlasquant_aion_developer_implementation",
            "Rollback vazio ou so com espaco e rejeitado.",
            lambda: world._ready(world.envelope, "builder-a", "reviewer-b", "breaker-c", "   "),
        ),
    ]
    first = "Reverter a mudanca logica."
    status_a, _ready_a = _invoke(lambda: world._ready(
        world.envelope, "builder-a", "reviewer-b", "breaker-c", first,
    ))
    other_envelope = deepcopy(world.envelope)
    other_envelope["envelope_id"] = "DEVIMPL-SECOND"
    status_b, _ready_b = _invoke(lambda: world._ready(
        other_envelope, "builder-a", "reviewer-b", "breaker-c", first,
    ))
    reused = status_a == "ACCEPT" and status_b == "ACCEPT"
    findings.append(_finding(
        "rollback.reused_text",
        "atlasquant_aion_developer_implementation",
        "O mesmo texto de rollback e aceito em outro envelope, sem vinculo com o id da mudanca."
        if reused else
        "Rollback reutilizado em outro envelope e rejeitado.",
        "GAP" if reused else "BLOCKED_BY_DESIGN",
        "MEDIUM" if reused else "",
    ))
    weak = deepcopy(world.ready)
    weak["test_contract"] = deepcopy(weak["test_contract"])
    weak["test_contract"]["candidate_tests"] = []
    weak["test_contract"]["test_deletion_allowed"] = True
    weak["test_contract"]["test_weakening_allowed"] = True
    status, approved = _invoke(lambda: world._approve(weak, "human-approver"))
    weakened = (
        status == "ACCEPT"
        and isinstance(approved, Mapping)
        and approved.get("implementation_authorized") is True
        and not list((approved.get("test_contract") or {}).get("candidate_tests") or [])
    )
    findings.append(_finding(
        "tests.approval_accepts_weakening",
        "atlasquant_aion_developer_implementation",
        "A aprovacao humana aceita envelope com testes removidos e test_deletion_allowed verdadeiro."
        if weakened else
        "A aprovacao rejeita remocao ou afrouxamento de testes.",
        "GAP" if weakened else "BLOCKED_BY_DESIGN",
        "HIGH" if weakened else "",
    ))
    if not weakened:
        contained = True
        builder_detail = "A aprovacao ja rejeita o envelope sem testes."
    else:
        status, request = _invoke(lambda: world.sandbox(approved))
        contained = (
            status == "ACCEPT"
            and isinstance(request, Mapping)
            and request.get("state") == "BLOCKED"
            and request.get("test_contract", {}).get("test_deletion_allowed") is False
        )
        builder_detail = (
            "O builder bloqueia request sem testes candidatos e forca test_deletion_allowed falso."
            if contained else
            "O builder nao contem a remocao de testes autorizada antes."
        )
    findings.append(_finding(
        "tests.builder_blocks_deleted_tests",
        "atlasquant_aion_developer_builder_sandbox",
        builder_detail,
        "BLOCKED_BY_DESIGN" if contained else "GAP",
        "" if contained else "HIGH",
    ))
    return findings


def _workflow_release_authority(world: _World) -> list[dict[str, str]]:
    findings = []

    workflow_status, workflow = _invoke(lambda: world.chain_for(".github/workflows/quality-tests.yml"))
    workflow_in_envelope = False
    workflow_request_blocked = workflow_status == "REJECT"
    if workflow_status == "ACCEPT" and isinstance(workflow, Mapping):
        editable = list((workflow["envelope"].get("scope") or {}).get("editable_files") or [])
        workflow_in_envelope = ".github/workflows/quality-tests.yml" in editable
        request = workflow["request"]
        workflow_request_blocked = request.get("state") == "BLOCKED"

    findings.append(_finding(
        "workflow.envelope_includes_workflow",
        "atlasquant_aion_developer_implementation",
        "O envelope autorizado inclui o workflow antes de bloqueio posterior."
        if workflow_in_envelope else
        "Workflow e bloqueado antes de entrar em escopo editavel autorizado.",
        "GAP" if workflow_in_envelope else "BLOCKED_BY_DESIGN",
        "MEDIUM" if workflow_in_envelope else "",
    ))
    findings.append(_finding(
        "workflow.builder_blocks_workflow",
        "atlasquant_aion_developer_builder_sandbox",
        "Workflow e contido pelo contrato antes ou durante o Builder request."
        if workflow_request_blocked else
        "Workflow chegou a request READY.",
        "BLOCKED_BY_DESIGN" if workflow_request_blocked else "GAP",
        "" if workflow_request_blocked else "HIGH",
    ))

    release_status, release = _invoke(lambda: world.chain_for("docs/release/NOTES.md"))
    release_ready = False
    if release_status == "ACCEPT" and isinstance(release, Mapping):
        release_ready = (
            release["request"].get("state") == "READY_FOR_BUILDER_SANDBOX"
            and "docs/release/NOTES.md" in list((release["request"].get("scope") or {}).get("requested_files") or [])
        )
    findings.append(_finding(
        "release.notes_ready",
        "atlasquant_aion_developer_builder_sandbox",
        "Arquivo docs/release entra em request READY."
        if release_ready else
        "Superficie docs/release e bloqueada antes de ficar READY.",
        "GAP" if release_ready else "BLOCKED_BY_DESIGN",
        "HIGH" if release_ready else "",
    ))

    legitimate = world.sandbox()
    flags_closed = all(legitimate.get(key) is False for key in (
        "execution_authorized",
        "automatic_commit",
        "automatic_merge",
        "automatic_deploy",
        "production_change_allowed",
        "real_trading_enabled",
        "tool_output_is_authority",
        "writes_files",
        "network_called",
        "subprocess_called",
    ))
    branch_closed = all(legitimate["branch_contract"].get(key) is False for key in (
        "main_branch_allowed", "force_push_allowed", "history_rewrite_allowed",
    ))
    file_closed = all(legitimate["scope"].get(key) is False for key in (
        "new_file_allowed", "delete_file_allowed", "rename_file_allowed", "scope_expansion_allowed",
    ))
    findings.append(_finding(
        "authority.legitimate_flags_closed",
        "atlasquant_aion_developer_builder_sandbox",
        "Request legitimo mantem execucao, merge, deploy, producao, trading, force-push e new/delete/rename fechados."
        if flags_closed and branch_closed and file_closed else
        "Request legitimo amplia alguma autoridade.",
        "PASS" if flags_closed and branch_closed and file_closed else "GAP",
        "" if flags_closed and branch_closed and file_closed else "CRITICAL",
    ))
    for invariant_id, key in (
        ("authority.forged_merge", "merge_main_allowed"),
        ("authority.forged_deploy", "deploy_allowed"),
        ("authority.forged_trading", "real_trading_allowed"),
    ):
        forged = deepcopy(world.approved)
        forged["authorization"] = dict(forged["authorization"])
        forged["authorization"][key] = True
        findings.append(_blocked(
            invariant_id,
            "atlasquant_aion_developer_builder_sandbox",
            f"Autorizacao com {key}=True e rejeitada.",
            lambda forged=forged: world.sandbox(forged),
        ))
    return findings


def _secrets_and_limits(world: _World) -> list[dict[str, str]]:
    findings = []
    secret_package = build_developer_package(
        f"password={_SECRET_SENTINEL} token={_TOKEN_SENTINEL}",
        world.snapshot,
        branch="cursor/admin-fix",
        baseline_ref="base@a",
        candidate_ref="cursor/admin-fix@b",
        created_at=_CREATED,
    )
    package_text = json.dumps(secret_package, ensure_ascii=False, default=str)
    diagnostic_text = json.dumps(world.diagnostic, ensure_ascii=False, default=str)
    package_clean = _SECRET_SENTINEL not in package_text and _TOKEN_SENTINEL not in package_text
    diagnostic_clean = (
        _SECRET_SENTINEL not in diagnostic_text
        and _TOKEN_SENTINEL not in diagnostic_text
        and world.diagnostic.get("raw_log_included") is False
    )
    findings.append(_finding(
        "secrets.package_redacts",
        "atlasquant_aion_developer_package",
        "Pedido do pacote nao conserva o sentinela de senha ou token."
        if package_clean else
        "Pedido do pacote conservou material sensivel.",
        "PASS" if package_clean else "GAP",
        "" if package_clean else "CRITICAL",
    ))
    findings.append(_finding(
        "secrets.diagnostic_redacts",
        "atlasquant_aion_developer_diagnostics",
        "Diagnostico redige o log e nao devolve o texto bruto."
        if diagnostic_clean else
        "Diagnostico conservou material sensivel.",
        "PASS" if diagnostic_clean else "GAP",
        "" if diagnostic_clean else "CRITICAL",
    ))
    paths = {str(row.get("path") or "") for row in world.snapshot["files"]}
    dotenv_hidden = ".env" not in paths and int(world.snapshot.get("skipped_sensitive") or 0) >= 1
    findings.append(_finding(
        "secrets.scan_skips_dotenv",
        "atlasquant_aion_developer_intelligence",
        "O scanner estrutural nao inclui .env no snapshot."
        if dotenv_hidden else
        "O scanner incluiu arquivo sensivel no snapshot.",
        "BLOCKED_BY_DESIGN" if dotenv_hidden else "GAP",
        "" if dotenv_hidden else "CRITICAL",
    ))
    symlink_hidden = "linked.py" not in paths and int(world.snapshot.get("skipped_symlink") or 0) >= 1
    findings.append(_finding(
        "path.symlink_skipped",
        "atlasquant_aion_developer_intelligence",
        "Symlink nao entra no snapshot."
        if symlink_hidden else
        "Symlink entrou no snapshot.",
        "BLOCKED_BY_DESIGN" if symlink_hidden else "GAP",
        "" if symlink_hidden else "HIGH",
    ))
    many = [f"bulk_{index}.py" for index in range(120)]
    stale = deepcopy(world.snapshot)
    stale["files"] = [{"path": path, "category": "MODULE", "risk_tags": []} for path in many]
    mutated = deepcopy(world.approved)
    mutated["scope"] = deepcopy(mutated["scope"])
    mutated["scope"]["editable_files"] = list(many)
    mutated["scope"]["source_files"] = list(many)
    status, request = _invoke(lambda: build_builder_sandbox_request(
        stale,
        mutated,
        branch="cursor/admin-fix",
        baseline_ref="base@a",
        candidate_ref="cursor/admin-fix@c",
        requested_files=many,
    ))
    requested = list((request.get("scope") or {}).get("requested_files") or []) if isinstance(request, Mapping) else []
    truncated_ready = (
        status == "ACCEPT"
        and isinstance(request, Mapping)
        and request.get("state") == "READY_FOR_BUILDER_SANDBOX"
        and len(requested) < len(many)
    )
    findings.append(_finding(
        "payload.excess_files_not_rejected",
        "atlasquant_aion_developer_builder_sandbox",
        f"Pedido com {len(many)} arquivos fica READY com {len(requested)} arquivos, sem rejeitar o excesso."
        if truncated_ready else
        "Pedido com arquivos em excesso e rejeitado.",
        "GAP" if truncated_ready else "BLOCKED_BY_DESIGN",
        "MEDIUM" if truncated_ready else "",
    ))
    huge = "cursor/" + ("a" * 5000)
    status, request = _invoke(lambda: world.sandbox(branch=huge, candidate_ref=huge + "@c"))
    stored = ""
    if isinstance(request, Mapping):
        stored = str((request.get("branch_contract") or {}).get("branch") or "")
    bounded = status == "REJECT" or (status == "ACCEPT" and len(stored) <= 240)
    findings.append(_finding(
        "payload.huge_branch_bounded",
        "atlasquant_aion_developer_builder_sandbox",
        "Branch enorme nao ultrapassa 240 caracteres e nao e executada."
        if bounded else
        "Branch enorme foi armazenada acima do limite.",
        "BLOCKED_BY_DESIGN" if bounded else "GAP",
        "" if bounded else "MEDIUM",
    ))
    return findings


def _residual_surface(world: _World) -> list[dict[str, str]]:
    findings = []
    pairs = (
        ("Alice", "Alice\u200b"),
        ("Alice", "Alice\ufeff"),
        ("Alice", "Al\u00adice"),
        ("builder", "bui\u200clder"),
    )
    distinct = [right for left, right in pairs if canonical_identity(left) != canonical_identity(right)]
    findings.append(_finding(
        "identity.format_characters",
        "atlasquant_aion_developer_manifest",
        "Caracteres de formato invisivel ainda separam atores: " + ", ".join(repr(item) for item in distinct) + "."
        if distinct else
        "Zero-width, BOM, hifen suave e ZWNJ nao criam ator independente.",
        "GAP" if distinct else "BLOCKED_BY_DESIGN",
        "CRITICAL" if distinct else "",
    ))

    nested = (
        "refs/heads/refs/heads/main",
        "refs/heads/refs/heads/production",
        "heads/main",
        "main.git",
        "production.git",
    )
    accepted_branches = []
    for branch in nested:
        status, _result = _invoke(lambda branch=branch: build_developer_package(
            "pedido",
            world.snapshot,
            branch=branch,
            baseline_ref="base@a",
            candidate_ref=f"{branch}@c",
            created_at=_CREATED,
        ))
        if status == "ACCEPT":
            accepted_branches.append(branch)
    findings.append(_finding(
        "branch.nested_refs_and_aliases",
        "atlasquant_aion_developer_manifest",
        "Aliases aninhados aceitos: " + ", ".join(accepted_branches) + "."
        if accepted_branches else
        "refs/heads repetido, heads/main e sufixo .git da familia protegida sao rejeitados.",
        "GAP" if accepted_branches else "BLOCKED_BY_DESIGN",
        "HIGH" if accepted_branches else "",
    ))

    release_paths = ("deployment/app.yaml", "scripts/deploy/go.sh", "docs/deployment/notes.md")
    exposed = [path for path in release_paths if not release_sensitive_path(path)]
    findings.append(_finding(
        "release.deployment_and_deploy_scripts",
        "atlasquant_aion_developer_manifest",
        "Superficies de deploy ainda fora da politica: " + ", ".join(exposed) + "."
        if exposed else
        "deployment/, scripts/deploy/ e docs/deployment/ exigem revisao de release.",
        "GAP" if exposed else "BLOCKED_BY_DESIGN",
        "HIGH" if exposed else "",
    ))

    skip_marker = "@" + "unittest." + "skip" + "('bypass')"
    disable_marker = "@" + "unittest." + "expected" + "Failure"
    patch = (
        "diff --git a/test_module.py b/test_module.py\n"
        "--- a/test_module.py\n+++ b/test_module.py\n"
        "@@ -1,2 +1,3 @@\n def test_guard():\n"
        "+    " + skip_marker + "\n"
        "+    " + disable_marker + "\n"
        "     assert guard()\n"
    )
    request = {
        "schema": "ATLASQUANT_AION_DEVELOPER_BUILDER_SANDBOX_REQUEST_V1",
        "request_id": "DEVBUILD-AUDIT",
        "state": "READY_FOR_BUILDER_SANDBOX",
        "branch_contract": {
            "branch": "cursor/safe",
            "baseline_ref": "base@a",
            "candidate_ref": "cursor/safe@c",
        },
        "scope": {
            "requested_files": ["test_module.py"],
            "authorized_files": ["test_module.py"],
        },
        "blockers": [],
        "execution_authorized": False,
        "executor_attached": False,
    }
    preflight = {
        "schema": "ATLASQUANT_AION_DEVELOPER_SANDBOX_PREFLIGHT_V1",
        "preflight_id": "DEVPREF-AUDIT",
        "builder_request_id": "DEVBUILD-AUDIT",
        "state": "READY_FOR_EXECUTOR_DESIGN_REVIEW",
        "preflight_passed": True,
        "execution_authorized": False,
        "executor_attached": False,
    }
    status, validated = _invoke(lambda: validate_patch(
        request, preflight, patch, baseline_ref="base@a", candidate_ref="cursor/safe@c",
    ))
    skip_blocked = (
        status == "ACCEPT"
        and isinstance(validated, Mapping)
        and validated.get("state") == "BLOCKED"
        and "TEST_DELETION_OR_WEAKENING_NOT_ALLOWED" in list(validated.get("blockers") or [])
    )
    findings.append(_finding(
        "tests.added_skip_or_expected_failure",
        "atlasquant_aion_developer_patch_validation",
        "Patch que so adiciona skip ou marcador de falha esperada em teste fica BLOCKED."
        if skip_blocked else
        "Patch que adiciona skip ou marcador de falha esperada em teste nao fica BLOCKED.",
        "BLOCKED_BY_DESIGN" if skip_blocked else "GAP",
        "" if skip_blocked else "HIGH",
    ))

    weakened = deepcopy(world.ready)
    weakened["test_contract"] = deepcopy(weakened["test_contract"])
    weakened["test_contract"]["candidate_tests"] = []
    weakened["test_contract"]["test_deletion_allowed"] = True
    weakened["test_contract"]["test_weakening_allowed"] = True
    weakened["envelope_manifest_id"] = implementation_base_manifest_id(weakened)
    weakened["readiness_manifest_id"] = implementation_readiness_manifest_id(weakened)
    status, approved = _invoke(lambda: approve_implementation_session(
        weakened,
        approved=True,
        approver_actor="human-approver",
        approval_refs=["approval:1"],
    ))
    authorized = (
        status == "ACCEPT"
        and isinstance(approved, Mapping)
        and approved.get("implementation_authorized") is True
    )
    findings.append(_finding(
        "tests.recomputed_manifest_still_blocks_weakening",
        "atlasquant_aion_developer_implementation",
        "Recalcular o manifesto nao autoriza remocao de testes nem test_deletion_allowed."
        if not authorized else
        "Recalcular o manifesto autorizou um envelope sem testes.",
        "BLOCKED_BY_DESIGN" if not authorized else "GAP",
        "" if not authorized else "HIGH",
    ))
    return findings


def _sealed_runner_request(tests, gates=None):
    return bind_builder_request_lineage({
        "schema": "ATLASQUANT_AION_DEVELOPER_BUILDER_SANDBOX_REQUEST_V1",
        "state": "READY_FOR_BUILDER_SANDBOX",
        "lineage": {
            "snapshot_digest": "REPO-FIXTURE",
            "implementation_envelope_id": "DEVIMPL-FIXTURE",
            "implementation_authorization_id": "DEVAUTH-FIXTURE",
        },
        "branch_contract": {
            "branch": "cursor/fix",
            "baseline_ref": "main@aaa",
            "candidate_ref": "cursor/fix@bbb",
            "candidate_bound_to_branch": True,
            "main_branch_allowed": False,
            "force_push_allowed": False,
            "history_rewrite_allowed": False,
        },
        "scope": {
            "requested_files": ["test_module.py"],
            "authorized_files": ["test_module.py"],
            "scope_expansion_allowed": False,
            "new_file_allowed": False,
            "delete_file_allowed": False,
            "rename_file_allowed": False,
        },
        "test_contract": {
            "candidate_tests": list(tests),
            "mandatory_gates": list(gates) if gates is not None else list(REQUIRED_MANDATORY_GATES),
            "test_deletion_allowed": False,
            "test_weakening_allowed": False,
        },
        "blockers": [],
        "execution_authorized": False,
        "executor_attached": False,
        "writes_files": False,
    })


def _sealed_preflight(builder):
    preflight = {
        "schema": "ATLASQUANT_AION_DEVELOPER_SANDBOX_PREFLIGHT_V1",
        "state": "READY_FOR_EXECUTOR_DESIGN_REVIEW",
        "builder_request_id": builder["request_id"],
        "test_contract_manifest_id": builder["test_contract_manifest_id"],
        "preflight_passed": True,
        "environment_contract": {
            "environment_kind": "ISOLATED_WORKTREE",
            "environment_id": "sandbox-001",
            "isolated_worktree": True,
            "repository_root_bound": True,
            "network_disabled": True,
            "secrets_mounted": False,
            "command_policy": "ALLOWLIST_ONLY",
        },
        "resource_budget": {
            "runtime_seconds": 900,
            "memory_mb": 2048,
            "output_bytes": 2_000_000,
            "max_commands": 24,
        },
        "scope": {"requested_files": list(builder.get("scope", {}).get("requested_files") or [])},
        "execution_authorized": False,
        "executor_attached": False,
    }
    preflight["preflight_id"] = expected_preflight_id(preflight)
    return preflight


def _runner_probe(tests, gates=None):
    builder = _sealed_runner_request(tests, gates)
    preflight = _sealed_preflight(builder)
    patch = {
        "schema": "ATLASQUANT_AION_DEVELOPER_PATCH_VALIDATION_V1",
        "validation_id": "DEVPATCHVAL-1",
        "state": "READY_FOR_PATCH_REVIEW",
        "builder_request_id": builder["request_id"],
        "preflight_id": preflight["preflight_id"],
        "patch_digest": "DEVPATCH-ABC",
        "revision_binding": {
            "baseline_ref": "main@aaa",
            "candidate_ref": "cursor/fix@bbb",
            "refs_match_approved_request": True,
            "revision_content_verified": True,
        },
        "blockers": [],
        "patch_applied": False,
        "execution_authorized": False,
        "executor_attached": False,
    }
    return build_runner_contract(
        builder,
        preflight,
        patch,
        content_attestation=attestation_for_documents(builder, preflight, patch),
        human_patch_reviewed=True,
        human_patch_reviewer="reviewer-1",
        human_patch_review_refs=["review:patch:1"],
    )


def _state_closed(result: Any, blocker: str) -> bool:
    return (
        isinstance(result, Mapping)
        and result.get("state") == "BLOCKED"
        and blocker in list(result.get("blockers") or [])
        and result.get("execution_authorized") is False
    )


def _patch_probe(patch: str):
    request = {
        "schema": "ATLASQUANT_AION_DEVELOPER_BUILDER_SANDBOX_REQUEST_V1",
        "request_id": "DEVBUILD-1",
        "state": "READY_FOR_BUILDER_SANDBOX",
        "branch_contract": {
            "baseline_ref": "main@a",
            "candidate_ref": "cursor/safe@b",
        },
        "scope": {
            "requested_files": ["module.py", "test_module.py"],
            "authorized_files": ["module.py", "test_module.py"],
        },
        "blockers": [],
        "execution_authorized": False,
        "executor_attached": False,
    }
    preflight = {
        "schema": "ATLASQUANT_AION_DEVELOPER_SANDBOX_PREFLIGHT_V1",
        "preflight_id": "DEVPREF-1",
        "builder_request_id": "DEVBUILD-1",
        "state": "READY_FOR_EXECUTOR_DESIGN_REVIEW",
        "preflight_passed": True,
        "execution_authorized": False,
        "executor_attached": False,
    }
    return validate_patch(
        request,
        preflight,
        patch,
        baseline_ref="main@a",
        candidate_ref="cursor/safe@b",
    )


def _command_probe(**overrides):
    policy_keys = (
        "requested_environment",
        "path_lookup_allowed",
        "parent_environment_inheritance",
        "absolute_executable_required",
        "executable_digest_required",
    )
    policy_kwargs = {key: overrides.pop(key) for key in policy_keys if key in overrides}
    pycache_prefix = overrides.pop("pycache_prefix", None)
    drop_cache_policy = overrides.pop("drop_cache_policy", False)
    runner = {
        "schema": "ATLASQUANT_AION_DEVELOPER_RUNNER_CONTRACT_V1",
        "runner_contract_id": "DEVRUN-1",
        "state": "READY_FOR_RUNNER_DESIGN_REVIEW",
        "resource_budget": {
            "runtime_seconds": 900,
            "memory_mb": 2048,
            "output_bytes": 2_000_000,
            "max_commands": 24,
        },
        "command_plan": [
            {
                "step": "COMPILE_CHANGED_SCOPE",
                "executable": "python",
                "argv": ["-m", "compileall", "-q", "<AUTHORIZED_CHANGED_SCOPE>"],
                "shell": False,
                "cwd": "<ISOLATED_WORKTREE>",
                "network": False,
                "writes_repo": False,
                "writes_repository": False,
                "may_write_ephemeral_cache": True,
                "pycache_prefix": "<SANDBOX_EPHEMERAL_PYCACHE>",
            },
            {
                "step": "RUN_TARGETED_TESTS",
                "executable": "python",
                "argv": ["-m", "unittest", "-q", "<APPROVED_TEST_TARGETS>"],
                "shell": False,
                "cwd": "<ISOLATED_WORKTREE>",
                "network": False,
                "writes_repo": False,
            },
            {
                "step": "VERIFY_DIFF_CHECK",
                "executable": "git",
                "argv": ["diff", "--check"],
                "shell": False,
                "cwd": "<ISOLATED_WORKTREE>",
                "network": False,
                "writes_repo": False,
            },
        ],
        "lineage": {
            "builder_request_id": "DEVBUILD-FIXTURE",
            "preflight_id": "DEVPREF-FIXTURE",
            "patch_validation_id": "DEVPATCHVAL-1",
            "patch_digest": "DEVPATCH-ABC",
            "content_attestation_id": "DEVATT-FIXTURE000000",
            "content_binding_structurally_bound": True,
            "content_binding_independently_verified": False,
        },
        "review": {
            "human_patch_reviewed": True,
            "human_patch_reviewer": "reviewer-1",
            "human_patch_review_refs": ["review:patch:1"],
        },
        "tests": {
            "targets": ["test_module.py"],
            "mandatory_gates": ["TARGETED_TESTS"],
            "tests_executed": False,
        },
        "command_plan_is_data_only": True,
        "shell_allowed": False,
        "network_allowed": False,
        "secrets_allowed": False,
        "repo_write_allowed": False,
        "path_lookup_allowed": False,
        "parent_environment_inheritance": False,
        "caller_environment_overrides_allowed": False,
        "content_binding_structurally_bound": True,
        "content_binding_independently_verified": False,
        "executable_pinning_verified": False,
        "os_sandbox_verified": False,
        "child_process_policy_verified": False,
        "symlink_physical_boundary_verified": False,
        "hardlink_physical_boundary_verified": False,
        "blockers": [],
        "execution_authorized": False,
        "executor_attached": False,
        "commands_executed": False,
        "writes_files": False,
        "runs_tests": False,
        "network_called": False,
        "subprocess_called": False,
        "automatic_commit": False,
        "automatic_merge": False,
        "automatic_deploy": False,
        "production_change_allowed": False,
        "real_trading_enabled": False,
        "tool_output_is_authority": False,
    }
    if "executable" in overrides:
        runner["command_plan"] = [dict(row) for row in runner["command_plan"]]
        runner["command_plan"][0]["executable"] = overrides["executable"]
    if "extra" in overrides:
        runner["command_plan"] = list(runner["command_plan"]) + [overrides["extra"]]
    if "budget_key" in overrides:
        runner["resource_budget"] = dict(runner["resource_budget"])
        runner["resource_budget"][overrides["budget_key"]] = overrides["budget_value"]
    if pycache_prefix is not None or drop_cache_policy:
        runner["command_plan"] = [dict(row) for row in runner["command_plan"]]
        if drop_cache_policy:
            runner["command_plan"][0].pop("writes_repository", None)
            runner["command_plan"][0].pop("may_write_ephemeral_cache", None)
            runner["command_plan"][0].pop("pycache_prefix", None)
        else:
            runner["command_plan"][0]["pycache_prefix"] = pycache_prefix
    bind_runner_contract_ids(runner)
    return build_command_policy_contract(runner, **policy_kwargs)


def _contract_gap_surface(_world: _World) -> list[dict[str, str]]:
    findings = []

    def _targets(targets, blocker, invariant_id, severity, description):
        accepted = []
        for target in targets:
            status, result = _invoke(lambda target=target: _runner_probe([target]))
            closed = status == "ACCEPT" and _state_closed(result, blocker)
            if not closed:
                accepted.append(target)
        findings.append(_finding(
            invariant_id,
            "atlasquant_aion_developer_runner_contract",
            description if not accepted else description + " Aceitos: " + ", ".join(accepted) + ".",
            "BLOCKED_BY_DESIGN" if not accepted else "GAP",
            "" if not accepted else severity,
        ))

    _targets(
        ("../outside.py", "/outside.py"),
        "UNSAFE_TEST_TARGET",
        "runner.external_test_path",
        "HIGH",
        "Caminho de teste externo ou absoluto POSIX fica BLOCKED.",
    )
    _targets(
        ("C:/outside.py", "C:\\outside.py", "\\\\server\\share\\test.py", "//server/share/test.py"),
        "UNSAFE_TEST_TARGET",
        "runner.windows_absolute_test_path",
        "HIGH",
        "Caminho Windows absoluto ou UNC de teste fica BLOCKED.",
    )
    _targets(
        ("missing_test.py", "other_authorized_looking.py"),
        "TEST_TARGET_NOT_IN_AUTHORIZED_FILES",
        "runner.unauthorized_or_nonexistent_test",
        "HIGH",
        "Teste fora dos arquivos autorizados nao e tratado como existente.",
    )

    dangerous_paths = (
        "C:/outside.py",
        "C:\\outside.py",
        "\\\\server\\share\\test.py",
        "//server/share/test.py",
    )
    accepted_paths = []
    for path in dangerous_paths:
        status, _result = _invoke(lambda path=path: build_sandbox_preflight(
            bind_builder_request_lineage({
                "schema": "ATLASQUANT_AION_DEVELOPER_BUILDER_SANDBOX_REQUEST_V1",
                "state": "READY_FOR_BUILDER_SANDBOX",
                "lineage": {
                    "snapshot_digest": "REPO-FIXTURE",
                    "implementation_envelope_id": "DEVIMPL-FIXTURE",
                    "implementation_authorization_id": "DEVAUTH-FIXTURE",
                },
                "branch_contract": {
                    "branch": "cursor/sandbox",
                    "baseline_ref": "main@a",
                    "candidate_ref": "cursor/sandbox@b",
                    "candidate_bound_to_branch": True,
                    "main_branch_allowed": False,
                    "force_push_allowed": False,
                    "history_rewrite_allowed": False,
                },
                "scope": {
                    "requested_files": [path],
                    "authorized_files": [path],
                    "scope_expansion_allowed": False,
                    "new_file_allowed": False,
                    "delete_file_allowed": False,
                    "rename_file_allowed": False,
                },
                "test_contract": {
                    "candidate_tests": ["test_module.py"],
                    "mandatory_gates": list(REQUIRED_MANDATORY_GATES),
                    "test_deletion_allowed": False,
                    "test_weakening_allowed": False,
                },
                "blockers": [],
                "execution_authorized": False,
                "executor_attached": False,
                "writes_files": False,
            }),
            environment_kind="ISOLATED_WORKTREE",
            environment_id="sandbox-001",
            isolated_worktree=True,
            repository_root_bound=True,
            network_disabled=True,
            secrets_mounted=False,
            command_policy="ALLOWLIST_ONLY",
        ))
        if status == "ACCEPT":
            accepted_paths.append(path)
    findings.append(_finding(
        "preflight.windows_drive_path",
        "atlasquant_aion_developer_sandbox_preflight",
        "Caminho de drive, UNC ou absoluto passa no preflight: " + ", ".join(accepted_paths) + "."
        if accepted_paths else
        "Caminhos de drive, UNC e absolutos sao rejeitados sem depender do SO hospedeiro.",
        "GAP" if accepted_paths else "BLOCKED_BY_DESIGN",
        "HIGH" if accepted_paths else "",
    ))

    status, result = _invoke(lambda: _patch_probe(
        "diff --git a/module.py b/module.py\n--- a/other.py\n+++ b/other.py\n@@ -1 +1 @@\n-old\n+new\n"
    ))
    header_closed = status == "ACCEPT" and _state_closed(result, "DIFF_HEADER_PATH_MISMATCH")
    findings.append(_finding(
        "patch.diff_header_mismatch",
        "atlasquant_aion_developer_patch_validation",
        "Cabecalhos diff/--/+++ divergentes ficam BLOCKED."
        if header_closed else
        "Cabecalhos divergentes de diff ainda passam.",
        "BLOCKED_BY_DESIGN" if header_closed else "GAP",
        "" if header_closed else "HIGH",
    ))

    secret_marker = "password=" + "AUDITSECRETVALUE"
    status, result = _invoke(lambda: _patch_probe(
        "diff --git a/module.py b/module.py\n--- a/module.py\n+++ b/module.py\n@@ -1 +1 @@\n-old\n+"
        + ("A" * 4000) + " " + secret_marker + "\n"
    ))
    secret_text = json.dumps(result, default=str) if status == "ACCEPT" else ""
    secret_closed = (
        status == "ACCEPT"
        and _state_closed(result, "SECRET_LIKE_ADDITION_NOT_ALLOWED")
        and secret_marker not in secret_text
    )
    findings.append(_finding(
        "patch.secret_beyond_prefix",
        "atlasquant_aion_developer_patch_validation",
        "Segredo apos 4000 caracteres e bloqueado e nao volta no relatorio."
        if secret_closed else
        "Segredo apos o prefixo inspecionado ainda passa ou vaza no relatorio.",
        "BLOCKED_BY_DESIGN" if secret_closed else "GAP",
        "" if secret_closed else "HIGH",
    ))

    status, result = _invoke(lambda: _patch_probe(
        "diff --git a/test_module.py b/test_module.py\n--- a/test_module.py\n+++ b/test_module.py\n"
        "@@ -1,2 +1,4 @@\n def test_guard():\n     assert guard()\n+def test_guard():\n+    pass\n"
    ))
    additive_closed = (
        status == "ACCEPT"
        and _state_closed(result, "TEST_ADDITIVE_NEUTRALIZATION_REQUIRES_SEPARATE_REVIEW")
    )
    findings.append(_finding(
        "patch.additive_test_neutralization",
        "atlasquant_aion_developer_patch_validation",
        "Redefinicao aditiva de teste com pass exige revisao separada e fica BLOCKED."
        if additive_closed else
        "Redefinicao aditiva de teste ainda fica pronta para revisao normal.",
        "BLOCKED_BY_DESIGN" if additive_closed else "GAP",
        "" if additive_closed else "HIGH",
    ))

    for invariant_id, executable, description in (
        ("command.executable_nul", "python\x00", "Executavel com NUL nao e normalizado para python."),
        ("command.executable_newline", "python\n", "Executavel com quebra de linha nao e normalizado para python."),
        ("command.executable_whitespace", "python ", "Executavel com espaco nao e normalizado para python."),
    ):
        status, result = _invoke(lambda executable=executable: _command_probe(executable=executable))
        rendered = json.dumps((result or {}).get("validated_command_plan") if isinstance(result, Mapping) else [], default=str)
        closed = status == "ACCEPT" and _state_closed(result, "EXECUTABLE_MISMATCH:COMPILE_CHANGED_SCOPE") and executable not in rendered
        findings.append(_finding(
            invariant_id,
            "atlasquant_aion_developer_command_policy",
            description if closed else description + " O plano validado conservou o valor cru.",
            "BLOCKED_BY_DESIGN" if closed else "GAP",
            "" if closed else "MEDIUM",
        ))

    status, result = _invoke(lambda: _command_probe(extra=None))
    entry_closed = status == "ACCEPT" and _state_closed(result, "COMMAND_PLAN_ENTRY_NOT_OBJECT")
    findings.append(_finding(
        "command.non_mapping_entry",
        "atlasquant_aion_developer_command_policy",
        "Item nao-objeto no command plan bloqueia o plano inteiro."
        if entry_closed else
        "Item nao-objeto no command plan e descartado em silencio.",
        "BLOCKED_BY_DESIGN" if entry_closed else "GAP",
        "" if entry_closed else "MEDIUM",
    ))

    for invariant_id, key, value, blocker in (
        ("command.runtime_budget_invalid", "runtime_seconds", 0, "RUNTIME_BUDGET_OUT_OF_RANGE"),
        ("command.memory_budget_invalid", "memory_mb", 0, "MEMORY_BUDGET_OUT_OF_RANGE"),
        ("command.output_budget_invalid", "output_bytes", 0, "OUTPUT_BUDGET_OUT_OF_RANGE"),
        ("command.command_budget_invalid", "max_commands", 0, "COMMAND_BUDGET_OUT_OF_RANGE"),
    ):
        status, result = _invoke(lambda key=key, value=value: _command_probe(budget_key=key, budget_value=value))
        closed = status == "ACCEPT" and _state_closed(result, blocker)
        findings.append(_finding(
            invariant_id,
            "atlasquant_aion_developer_command_policy",
            "Orcamento adulterado fica BLOCKED." if closed else "Orcamento adulterado ainda passa.",
            "BLOCKED_BY_DESIGN" if closed else "GAP",
            "" if closed else "MEDIUM",
        ))

    status, result = _invoke(lambda: _patch_probe(
        "diff --git a/module.py b/module.py\n--- a/module.py\n+++ b/module.py\n"
    ))
    hunk_count = -1
    if isinstance(result, Mapping):
        files = list(result.get("files") or [])
        if files and isinstance(files[0], Mapping):
            hunk_count = int(files[0].get("hunk_count") or 0)
    hunk_closed = status == "ACCEPT" and _state_closed(result, "DIFF_HUNK_REQUIRED") and hunk_count == 0
    findings.append(_finding(
        "patch.missing_hunk",
        "atlasquant_aion_developer_patch_validation",
        "Diff somente com cabecalhos fica BLOCKED e hunk_count permanece 0."
        if hunk_closed else
        "Diff sem hunk ainda fica pronto para revisao.",
        "BLOCKED_BY_DESIGN" if hunk_closed else "GAP",
        "" if hunk_closed else "MEDIUM",
    ))

    status, result = _invoke(lambda: _runner_probe(["test_module.py"] * (MAX_TEST_TARGETS + 1)))
    gate_status, gate_result = _invoke(lambda: _runner_probe(
        ["test_module.py"],
        [f"GATE_{index}" for index in range(MAX_MANDATORY_GATES + 1)],
    ))
    excess_closed = status == "ACCEPT" and _state_closed(result, "TEST_TARGET_LIMIT_EXCEEDED")
    gate_closed = gate_status == "ACCEPT" and _state_closed(gate_result, "MANDATORY_GATE_LIMIT_EXCEEDED")
    findings.append(_finding(
        "runner.excessive_test_targets",
        "atlasquant_aion_developer_runner_contract",
        "Excesso de testes ou gates bloqueia sem truncar o plano."
        if excess_closed and gate_closed else
        "Excesso de testes ou gates ainda e truncado e permanece pronto.",
        "BLOCKED_BY_DESIGN" if excess_closed and gate_closed else "GAP",
        "" if excess_closed and gate_closed else "MEDIUM",
    ))

    status, verified = _invoke(lambda: _runner_probe(["test_module.py"]))
    claimed = (
        status != "ACCEPT"
        or not isinstance(verified, Mapping)
        or verified.get("symlink_physical_boundary_verified") is not False
        or verified.get("hardlink_physical_boundary_verified") is not False
    )
    findings.append(_finding(
        "path.symlink_hardlink_physical_boundary_unverified",
        "atlasquant_aion_developer_runner_contract",
        "Fronteira fisica de symlink e hardlink nao foi comprovada e permanece falsa."
        if not claimed else
        "O contrato afirmou verificacao fisica de symlink ou hardlink sem prova.",
        "BLOCKED_BY_DESIGN" if not claimed else "GAP",
        "" if not claimed else "MEDIUM",
    ))
    return findings


def _preflight_call(request: Mapping[str, Any]) -> dict[str, Any]:
    return build_sandbox_preflight(
        request,
        environment_kind="ISOLATED_WORKTREE",
        environment_id="sandbox-001",
        isolated_worktree=True,
        repository_root_bound=True,
        network_disabled=True,
        secrets_mounted=False,
        command_policy="ALLOWLIST_ONLY",
    )


def _runner_from_pair(request: Mapping[str, Any], preflight: Mapping[str, Any], **overrides: Any) -> dict[str, Any]:
    branch = request.get("branch_contract") if isinstance(request.get("branch_contract"), Mapping) else {}
    patch = {
        "schema": "ATLASQUANT_AION_DEVELOPER_PATCH_VALIDATION_V1",
        "validation_id": "DEVPATCHVAL-1",
        "state": "READY_FOR_PATCH_REVIEW",
        "builder_request_id": request.get("request_id"),
        "preflight_id": preflight.get("preflight_id"),
        "patch_digest": "DEVPATCH-ABC",
        "revision_binding": {
            "baseline_ref": branch.get("baseline_ref"),
            "candidate_ref": branch.get("candidate_ref"),
            "refs_match_approved_request": True,
            "revision_content_verified": True,
        },
        "blockers": [],
        "patch_applied": False,
        "execution_authorized": False,
        "executor_attached": False,
    }
    args = {
        "content_attestation": attestation_for_documents(request, preflight, patch),
        "human_patch_reviewed": True,
        "human_patch_reviewer": "reviewer-independent",
        "human_patch_review_refs": ["review:patch:1"],
    }
    args.update(overrides)
    return build_runner_contract(request, preflight, patch, **args)


def _test_contract_integrity_surface(world: _World) -> list[dict[str, str]]:
    """Bind candidate tests and mandatory gates to request_id and preflight_id."""
    findings: list[dict[str, str]] = []
    try:
        request = build_builder_sandbox_request(
            world.snapshot,
            world.approved,
            branch="cursor/admin-fix",
            baseline_ref="base@a",
            candidate_ref="cursor/admin-fix@b",
        )
        preflight = _preflight_call(request)
        runner = _runner_from_pair(request, preflight)
        ready = (
            request.get("state") == "READY_FOR_BUILDER_SANDBOX"
            and preflight.get("state") == "READY_FOR_EXECUTOR_DESIGN_REVIEW"
            and runner.get("state") == "READY_FOR_RUNNER_DESIGN_REVIEW"
            and bool(request.get("test_contract_manifest_id"))
            and request.get("execution_authorized") is False
            and preflight.get("execution_authorized") is False
            and runner.get("execution_authorized") is False
            and runner.get("commands_executed") is False
            and runner.get("runs_tests") is False
            and runner.get("subprocess_called") is False
            and runner.get("network_called") is False
        )
    except (TypeError, ValueError):
        request = {}
        preflight = {}
        ready = False

    def _both_reject(candidate: Mapping[str, Any], baseline: Mapping[str, Any]) -> bool:
        pre_status, _pre_result = _invoke(lambda: _preflight_call(candidate))
        run_status, _run_result = _invoke(lambda: _runner_from_pair(candidate, baseline))
        return pre_status == "REJECT" and run_status == "REJECT"

    def _record(invariant_id: str, module: str, description: str, closed: bool) -> None:
        findings.append(_finding(
            invariant_id,
            module,
            description if closed else description + " A cadeia aceitou o contrato adulterado.",
            "BLOCKED_BY_DESIGN" if closed else "GAP",
            "" if closed else "HIGH",
        ))

    mutated_tests = deepcopy(request) if ready else {}
    if ready:
        contract = deepcopy(mutated_tests["test_contract"])
        contract["candidate_tests"] = list(contract["candidate_tests"]) + [
            str(contract["candidate_tests"][0]) + "::lineage_probe"
        ]
        mutated_tests["test_contract"] = contract
    _record(
        "test_contract.candidate_tests_mutated_after_request_id",
        "atlasquant_aion_developer_sandbox_preflight",
        "Trocar candidate_tests e manter request_id faz Preflight e Runner rejeitarem.",
        ready and _both_reject(mutated_tests, preflight),
    )

    mutated_gates = deepcopy(request) if ready else {}
    if ready:
        contract = deepcopy(mutated_gates["test_contract"])
        contract["mandatory_gates"] = list(contract["mandatory_gates"]) + ["UI_SMOKE"]
        mutated_gates["test_contract"] = contract
    _record(
        "test_contract.mandatory_gates_mutated_after_request_id",
        "atlasquant_aion_developer_sandbox_preflight",
        "Trocar mandatory_gates e manter request_id faz Preflight e Runner rejeitarem.",
        ready and _both_reject(mutated_gates, preflight),
    )

    removed = deepcopy(request) if ready else {}
    if ready:
        contract = deepcopy(removed["test_contract"])
        contract["mandatory_gates"] = [
            gate for gate in contract["mandatory_gates"] if gate != "ROLLBACK_REVIEW"
        ]
        removed["test_contract"] = contract
        removed = bind_builder_request_lineage(removed)
    removed_preflight = _sealed_preflight(removed) if ready else {}
    _record(
        "test_contract.required_gate_removed",
        "atlasquant_aion_developer_sandbox_preflight",
        "Remover um gate obrigatorio depois da autorizacao falha fechado.",
        ready and _both_reject(removed, removed_preflight),
    )

    arbitrary = deepcopy(request) if ready else {}
    if ready:
        contract = deepcopy(arbitrary["test_contract"])
        contract["mandatory_gates"] = ["ANYTHING"]
        arbitrary["test_contract"] = contract
        arbitrary = bind_builder_request_lineage(arbitrary)
    arbitrary_preflight = _sealed_preflight(arbitrary) if ready else {}
    _record(
        "test_contract.arbitrary_gate",
        "atlasquant_aion_developer_sandbox_preflight",
        "Um gate arbitrario nao satisfaz o conjunto obrigatorio.",
        ready and _both_reject(arbitrary, arbitrary_preflight),
    )

    as_string = deepcopy(request) if ready else {}
    if ready:
        contract = deepcopy(as_string["test_contract"])
        contract["candidate_tests"] = "test_module.py"
        as_string["test_contract"] = contract
    _record(
        "test_contract.candidate_tests_string",
        "atlasquant_aion_developer_builder_sandbox",
        "candidate_tests string nao vira lista de caracteres.",
        ready and _both_reject(as_string, preflight),
    )

    gates_string = deepcopy(request) if ready else {}
    if ready:
        contract = deepcopy(gates_string["test_contract"])
        contract["mandatory_gates"] = "QUALITY_TESTS"
        gates_string["test_contract"] = contract
    _record(
        "test_contract.mandatory_gates_string",
        "atlasquant_aion_developer_builder_sandbox",
        "mandatory_gates string nao vira lista de caracteres.",
        ready and _both_reject(gates_string, preflight),
    )

    review_status = "REJECT"
    if ready:
        review_status, _review_result = _invoke(
            lambda: _runner_from_pair(request, preflight, human_patch_review_refs="review:1")
        )
    _record(
        "test_contract.review_refs_string",
        "atlasquant_aion_developer_runner_contract",
        "human_patch_review_refs string nao conta como evidencia.",
        ready and review_status == "REJECT",
    )

    element_closed = False
    if ready:
        samples = []
        tests_bad = deepcopy(request)
        tests_bad["test_contract"] = deepcopy(tests_bad["test_contract"])
        tests_bad["test_contract"]["candidate_tests"] = list(tests_bad["test_contract"]["candidate_tests"]) + [1]
        samples.append(tests_bad)
        gates_bad = deepcopy(request)
        gates_bad["test_contract"] = deepcopy(gates_bad["test_contract"])
        gates_bad["test_contract"]["mandatory_gates"] = list(gates_bad["test_contract"]["mandatory_gates"]) + [None]
        samples.append(gates_bad)
        files_bad = deepcopy(request)
        files_bad["scope"] = deepcopy(files_bad["scope"])
        files_bad["scope"]["requested_files"] = list(files_bad["scope"]["requested_files"]) + [True]
        samples.append(files_bad)
        authorized_bad = deepcopy(request)
        authorized_bad["scope"] = deepcopy(authorized_bad["scope"])
        authorized_bad["scope"]["authorized_files"] = list(authorized_bad["scope"]["authorized_files"]) + [1.5]
        samples.append(authorized_bad)
        review_elements, _ignored = _invoke(
            lambda: _runner_from_pair(
                request,
                preflight,
                human_patch_review_refs=["review:patch:1", {"ref": 1}],
            )
        )
        element_closed = all(_both_reject(sample, preflight) for sample in samples) and review_elements == "REJECT"
    _record(
        "test_contract.non_string_elements",
        "atlasquant_aion_developer_runner_contract",
        "Elemento nao-string dentro das colecoes de seguranca e rejeitado.",
        element_closed,
    )
    return findings


def _resource_budget_surface(_world: _World) -> list[dict[str, str]]:
    """Reject bool, string and float budgets before they can share an int digest."""
    findings: list[dict[str, str]] = []

    def _preflight_for(request: Mapping[str, Any], **overrides: Any) -> dict[str, Any]:
        kwargs = {
            "environment_kind": "ISOLATED_WORKTREE",
            "environment_id": "sandbox-001",
            "isolated_worktree": True,
            "repository_root_bound": True,
            "network_disabled": True,
            "secrets_mounted": False,
            "command_policy": "ALLOWLIST_ONLY",
            "runtime_seconds": 900,
            "memory_mb": 2048,
            "output_bytes": 2_000_000,
            "max_commands": 24,
        }
        kwargs.update(overrides)
        return build_sandbox_preflight(request, **kwargs)

    def _record(invariant_id: str, module: str, description: str, closed: bool) -> None:
        findings.append(_finding(
            invariant_id,
            module,
            description if closed else description + " A coercao de tipo ainda foi aceita.",
            "BLOCKED_BY_DESIGN" if closed else "GAP",
            "" if closed else "HIGH",
        ))

    def _initial(field: str, value: Any) -> bool:
        status, result = _invoke(lambda: _preflight_for(_sealed_runner_request(["test_module.py"]), **{field: value}))
        if status != "REJECT" or not isinstance(result, BaseException):
            return False
        if isinstance(result, Mapping):
            budget = result.get("resource_budget")
            if isinstance(budget, Mapping) and budget.get(field) == value:
                return False
        return True

    for invariant_id, value, description in (
        ("budget.runtime_true_initial", True, "runtime_seconds True nao vira 1 nem gera preflight pronto."),
        ("budget.runtime_false_initial", False, "runtime_seconds False nao vira 0."),
        ("budget.runtime_numeric_string", "900", "runtime_seconds string numerica nao vira inteiro."),
        ("budget.runtime_integral_float", 1.0, "runtime_seconds 1.0 nao e intercambiavel com 1."),
        ("budget.runtime_fractional_float", 1.9, "runtime_seconds 1.9 nao e truncado para 1."),
        ("budget.runtime_none", None, "runtime_seconds ausente ou None e rejeitado."),
    ):
        _record(
            invariant_id,
            "atlasquant_aion_developer_sandbox_preflight",
            description,
            _initial("runtime_seconds", value),
        )
    _record(
        "budget.max_commands_true_initial",
        "atlasquant_aion_developer_sandbox_preflight",
        "max_commands True nao gera preflight valido.",
        _initial("max_commands", True),
    )
    _record(
        "budget.runtime_list_and_dict",
        "atlasquant_aion_developer_sandbox_preflight",
        "Lista ou dict no budget e rejeitado.",
        _initial("runtime_seconds", []) and _initial("runtime_seconds", {}),
    )

    try:
        request = _sealed_runner_request(["test_module.py"])
        preflight = _preflight_for(request, runtime_seconds=1, max_commands=1)
        runner = _runner_from_pair(request, preflight)
        ready = (
            preflight.get("state") == "READY_FOR_EXECUTOR_DESIGN_REVIEW"
            and runner.get("state") == "READY_FOR_RUNNER_DESIGN_REVIEW"
            and preflight.get("execution_authorized") is False
            and runner.get("execution_authorized") is False
            and type(preflight["resource_budget"]["runtime_seconds"]) is int
            and preflight["resource_budget"]["runtime_seconds"] == 1
            and preflight["resource_budget"]["max_commands"] == 1
        )
    except (TypeError, ValueError):
        request, preflight, runner = {}, {}, {}
        ready = False

    def _mutate(document: Mapping[str, Any], field: str, value: Any) -> dict[str, Any]:
        mutated = deepcopy(dict(document))
        mutated["resource_budget"] = dict(mutated.get("resource_budget") or {})
        mutated["resource_budget"][field] = value
        return mutated

    runtime_mutated = _mutate(preflight, "runtime_seconds", True) if ready else {}
    runtime_id_status, _runtime_id = _invoke(lambda: expected_preflight_id(runtime_mutated)) if ready else ("REJECT", None)
    runtime_run_status, _runtime_run = (
        _invoke(lambda: _runner_from_pair(request, runtime_mutated)) if ready else ("REJECT", None)
    )
    _record(
        "budget.runtime_mutated_to_true_keeps_id",
        "atlasquant_aion_developer_runner_contract",
        "Mutar runtime_seconds para True e manter preflight_id falha na revalidacao.",
        ready
        and runtime_mutated.get("preflight_id") == preflight.get("preflight_id")
        and runtime_id_status == "REJECT"
        and runtime_run_status == "REJECT",
    )

    commands_mutated = _mutate(preflight, "max_commands", True) if ready else {}
    commands_id_status, _commands_id = _invoke(lambda: expected_preflight_id(commands_mutated)) if ready else ("REJECT", None)
    commands_run_status, _commands_run = (
        _invoke(lambda: _runner_from_pair(request, commands_mutated)) if ready else ("REJECT", None)
    )
    _record(
        "budget.max_commands_mutated_to_true_keeps_id",
        "atlasquant_aion_developer_runner_contract",
        "Mutar max_commands para True e manter preflight_id falha na revalidacao.",
        ready
        and commands_mutated.get("preflight_id") == preflight.get("preflight_id")
        and commands_id_status == "REJECT"
        and commands_run_status == "REJECT",
    )

    recompute_status, recompute_result = (
        _invoke(lambda: expected_preflight_id(runtime_mutated)) if ready else ("REJECT", None)
    )
    _record(
        "budget.recompute_rejects_true",
        "atlasquant_aion_developer_sandbox_preflight",
        "Recalcular preflight_id com runtime_seconds True continua rejeitado.",
        ready and recompute_status == "REJECT" and not isinstance(recompute_result, str),
    )

    try:
        wide_request = _sealed_runner_request(["test_module.py"])
        wide = _preflight_for(wide_request)
        wide_runner = _runner_from_pair(wide_request, wide)
        wide_ready = (
            wide.get("state") == "READY_FOR_EXECUTOR_DESIGN_REVIEW"
            and wide_runner.get("state") == "READY_FOR_RUNNER_DESIGN_REVIEW"
            and wide_runner.get("commands_executed") is False
        )
    except (TypeError, ValueError):
        wide_request, wide, wide_runner = {}, {}, {}
        wide_ready = False

    runner_closed = False
    if wide_ready:
        runner_closed = True
        for field, value in (("runtime_seconds", "900"), ("runtime_seconds", 1.9), ("max_commands", True)):
            mutated = _mutate(wide, field, value)
            status, _result = _invoke(lambda mutated=mutated: _runner_from_pair(wide_request, mutated))
            if status != "REJECT":
                runner_closed = False
    _record(
        "budget.runner_revalidates_exact_int",
        "atlasquant_aion_developer_runner_contract",
        "Runner revalida o budget e rejeita string, float e bool.",
        runner_closed,
    )

    policy_closed = False
    if wide_ready:
        policy_closed = True
        for field, value in (("runtime_seconds", True), ("max_commands", True), ("output_bytes", "2000000")):
            mutated = _mutate(wide_runner, field, value)
            status, _result = _invoke(lambda mutated=mutated: build_command_policy_contract(mutated))
            if status != "REJECT":
                policy_closed = False
    _record(
        "budget.command_policy_revalidates_exact_int",
        "atlasquant_aion_developer_command_policy",
        "Command policy revalida o budget e rejeita bool e string.",
        policy_closed,
    )
    return findings


def _distinct_roles() -> dict[str, str]:
    return {
        "builder_principal_id": "prn_builder01",
        "reviewer_principal_id": "prn_reviewer1",
        "breaker_principal_id": "prn_breaker01",
        "approver_principal_id": "prn_approver1",
        "attestor_principal_id": "prn_attestor1",
    }


def _pin_claim(name: str, path: str, digest: str) -> dict[str, Any]:
    return {
        "logical_name": name,
        "absolute_path": path,
        "sha256": digest,
        "file_size_bytes": 128,
        "version_claim": "claim-only",
        "verification_evidence_refs": ["evidence:pin:" + name],
    }


def _attestation_pinning_surface(_world: _World) -> list[dict[str, str]]:
    """Fail closed on forged attestation, principal collisions and unpinning."""
    findings: list[dict[str, str]] = []
    builder = _sealed_runner_request(["test_module.py"])
    preflight = _sealed_preflight(builder)
    patch = {
        "schema": "ATLASQUANT_AION_DEVELOPER_PATCH_VALIDATION_V1",
        "validation_id": "DEVPATCHVAL-1",
        "state": "READY_FOR_PATCH_REVIEW",
        "builder_request_id": builder["request_id"],
        "preflight_id": preflight["preflight_id"],
        "patch_digest": "DEVPATCH-ABC",
        "revision_binding": {
            "baseline_ref": "main@aaa",
            "candidate_ref": "cursor/fix@bbb",
            "refs_match_approved_request": True,
            "revision_content_verified": True,
        },
        "blockers": [],
        "patch_applied": False,
        "execution_authorized": False,
        "executor_attached": False,
    }
    good = attestation_for_documents(builder, preflight, patch)
    pins = [
        _pin_claim("python", "/usr/bin/python3", "ab" * 32),
        _pin_claim("git", "/usr/bin/git", "cd" * 32),
    ]

    def _run(attestation: Any, patch_doc: Mapping[str, Any] = patch) -> dict[str, Any]:
        return build_runner_contract(
            builder,
            preflight,
            patch_doc,
            content_attestation=attestation,
            human_patch_reviewed=True,
            human_patch_reviewer="reviewer-1",
            human_patch_review_refs=["review:patch:1"],
        )

    def _reject(invariant_id: str, module: str, description: str, fn: Callable[[], Any]) -> None:
        status, _result = _invoke(fn)
        closed = status == "REJECT"
        findings.append(_finding(
            invariant_id,
            module,
            description if closed else description + " Aceito.",
            "BLOCKED_BY_DESIGN" if closed else "GAP",
            "" if closed else "HIGH",
        ))

    def _policy(invariant_id: str, description: str, fn: Callable[[], Any], blocker: str) -> None:
        status, result = _invoke(fn)
        closed = (
            status == "ACCEPT"
            and _state_closed(result, blocker)
            and isinstance(result, Mapping)
            and result.get("executable_pinning_verified") is False
            and result.get("state") != "READY_FOR_EXECUTION"
        )
        findings.append(_finding(
            invariant_id,
            "atlasquant_aion_developer_command_policy",
            description if closed else description + " A politica aceitou o desvio.",
            "BLOCKED_BY_DESIGN" if closed else "GAP",
            "" if closed else "HIGH",
        ))

    forged = {
        "schema": "ATLASQUANT_AION_DEVELOPER_CONTENT_ATTESTATION_V1",
        "content_attestation_id": "DEVATT-" + ("F" * 18),
        "content_binding_structurally_bound": True,
        "content_binding_independently_verified": False,
        "content_binding_verified": True,
        "builder_request_id": builder["request_id"],
        "test_contract_manifest_id": builder["test_contract_manifest_id"],
        "preflight_id": preflight["preflight_id"],
        "patch_validation_id": patch["validation_id"],
        "patch_digest": patch["patch_digest"],
        "baseline_ref": "main@aaa",
        "candidate_ref": "cursor/fix@bbb",
        "baseline_commit_sha": "a" * 40,
        "candidate_commit_sha": "b" * 40,
        "baseline_tree_sha": "c" * 40,
        "candidate_tree_sha": "d" * 40,
        "verification_method": "STRUCTURAL_MANIFEST_V1",
        "verification_evidence_refs": ["evidence:forged:1"],
        "attestor_principal_id": "prn_attestor1",
    }
    _reject(
        "attestation.forged",
        "atlasquant_aion_developer_content_attestation",
        "Attestation forjada com content_binding_verified e id inventado e rejeitada.",
        lambda: _run(forged),
    )
    other = attestation_for_documents(
        builder,
        preflight,
        patch,
        verification_evidence_refs=["evidence:other:1"],
    )
    stolen = dict(good)
    stolen["content_attestation_id"] = other["content_attestation_id"]
    _reject(
        "attestation.stolen_id",
        "atlasquant_aion_developer_content_attestation",
        "content_attestation_id copiado de outra attestation e rejeitado.",
        lambda: _run(stolen),
    )

    def _mutate(field: str, value: Any) -> dict[str, Any]:
        mutated = dict(good)
        mutated[field] = value
        return mutated

    _reject(
        "attestation.patch_digest_mutated",
        "atlasquant_aion_developer_runner_contract",
        "patch_digest alterado depois da attestation e rejeitado.",
        lambda: _run(_mutate("patch_digest", "DEVPATCH-MUTATED")),
    )
    _reject(
        "attestation.candidate_sha_mutated",
        "atlasquant_aion_developer_runner_contract",
        "SHA do commit candidato alterado depois da attestation e rejeitado.",
        lambda: _run(_mutate("candidate_commit_sha", "e" * 40)),
    )
    _reject(
        "attestation.baseline_sha_mutated",
        "atlasquant_aion_developer_runner_contract",
        "SHA do commit baseline alterado depois da attestation e rejeitado.",
        lambda: _run(_mutate("baseline_commit_sha", "f" * 40)),
    )
    _reject(
        "attestation.tree_sha_mutated",
        "atlasquant_aion_developer_runner_contract",
        "SHA de tree alterado depois da attestation e rejeitado.",
        lambda: _run(_mutate("candidate_tree_sha", "9" * 40)),
    )
    _reject(
        "attestation.request_id_mismatch",
        "atlasquant_aion_developer_runner_contract",
        "Attestation de outro builder_request_id e rejeitada.",
        lambda: _run(attestation_for_documents(
            builder, preflight, patch, builder_request_id="DEVBUILD-OTHERREQUEST1",
        )),
    )
    _reject(
        "attestation.preflight_id_mismatch",
        "atlasquant_aion_developer_runner_contract",
        "Attestation de outro preflight_id e rejeitada.",
        lambda: _run(attestation_for_documents(
            builder, preflight, patch, preflight_id="DEVPREF-OTHERREQUEST01",
        )),
    )
    _reject(
        "attestation.validation_id_mismatch",
        "atlasquant_aion_developer_runner_contract",
        "Attestation de outro validation_id e rejeitada.",
        lambda: _run(attestation_for_documents(
            builder, preflight, patch, patch_validation_id="DEVPATCHVAL-OTHER",
        )),
    )
    replay_patch = dict(patch)
    replay_patch["patch_digest"] = "DEVPATCH-OTHER"
    replay_patch["validation_id"] = "DEVPATCHVAL-2"
    _reject(
        "attestation.replay_other_patch",
        "atlasquant_aion_developer_runner_contract",
        "Attestation de um patch reapresentada em outro patch e rejeitada.",
        lambda: _run(good, replay_patch),
    )
    collided = _distinct_roles()
    collided["attestor_principal_id"] = collided["builder_principal_id"]
    _reject(
        "principal.duplicate_ids",
        "atlasquant_aion_developer_principal_identity",
        "O mesmo principal_id em dois papeis e rejeitado.",
        lambda: assert_independent_principals(collided),
    )
    cyrillic_display = "\u0410lice"
    same_principal = classify_actor_pair(
        {"display_actor": "Alice", "principal_id": "prn_attestor1"},
        {"display_actor": cyrillic_display, "principal_id": "prn_attestor1"},
    ) == "SAME_PRINCIPAL"
    distinct_labels = classify_actor_pair(
        {"display_actor": "Alice", "principal_id": "prn_builder01"},
        {"display_actor": "Alice", "principal_id": "prn_reviewer1"},
    ) == "DISTINCT_PRINCIPALS"
    role_status, _role_result = _invoke(lambda: assert_independent_principals({
        **_distinct_roles(),
        "builder_principal_id": "prn_attestor1",
        "attestor_principal_id": "prn_attestor1",
    }))
    display_closed = same_principal and distinct_labels and role_status == "REJECT"
    findings.append(_finding(
        "principal.same_id_distinct_display",
        "atlasquant_aion_developer_principal_identity",
        "O mesmo principal_id com displays latino e cirilico e o mesmo ator e nao separa papeis."
        if display_closed else
        "Displays parecidos ainda separam papeis ou displays iguais foram fundidos.",
        "BLOCKED_BY_DESIGN" if display_closed else "GAP",
        "" if display_closed else "HIGH",
    ))
    _reject(
        "principal.empty",
        "atlasquant_aion_developer_principal_identity",
        "principal_id vazio e rejeitado.",
        lambda: require_principal_id(""),
    )
    _reject(
        "principal.control_or_invisible",
        "atlasquant_aion_developer_principal_identity",
        "principal_id com controle ou caractere invisivel e rejeitado.",
        lambda: require_principal_id("prn_builder01" + "\u200b"),
    )
    _reject(
        "pinning.relative_path",
        "atlasquant_aion_developer_executable_pinning",
        "Caminho relativo de executavel e rejeitado.",
        lambda: build_executable_pinning_spec([
            _pin_claim("python", "usr/bin/python3", "ab" * 32),
            pins[1],
        ]),
    )
    _reject(
        "pinning.malformed_sha256",
        "atlasquant_aion_developer_executable_pinning",
        "SHA-256 malformado e rejeitado.",
        lambda: build_executable_pinning_spec([
            _pin_claim("python", "/usr/bin/python3", "AB" * 32),
            pins[1],
        ]),
    )
    _reject(
        "pinning.extra_executable",
        "atlasquant_aion_developer_executable_pinning",
        "Executavel extra fora de python e git e rejeitado.",
        lambda: build_executable_pinning_spec(pins + [
            _pin_claim("bash", "/usr/bin/bash", "ef" * 32),
        ]),
    )
    _reject(
        "pinning.python_without_git",
        "atlasquant_aion_developer_executable_pinning",
        "Pin somente de python, sem git, e rejeitado.",
        lambda: build_executable_pinning_spec([pins[0]]),
    )
    _policy(
        "command.path_lookup_enabled",
        "PATH lookup habilitado fica BLOCKED.",
        lambda: _command_probe(path_lookup_allowed=True),
        "PATH_LOOKUP_NOT_ALLOWED",
    )
    _policy(
        "command.caller_environment_override",
        "Override de ambiente do caller fica BLOCKED.",
        lambda: _command_probe(requested_environment={"CUSTOM": "1"}),
        "CALLER_ENVIRONMENT_OVERRIDES_NOT_ALLOWED",
    )
    _policy(
        "command.pythonpath_injection",
        "PYTHONPATH injetado fica BLOCKED.",
        lambda: _command_probe(requested_environment={"PYTHONPATH": "/tmp/injected"}),
        "INHERITED_ENVIRONMENT_KEY_NOT_ALLOWED",
    )
    _policy(
        "command.pythonstartup_injection",
        "PYTHONSTARTUP injetado fica BLOCKED.",
        lambda: _command_probe(requested_environment={"PYTHONSTARTUP": "/tmp/startup.py"}),
        "INHERITED_ENVIRONMENT_KEY_NOT_ALLOWED",
    )
    _policy(
        "command.home_injection",
        "HOME injetado fica BLOCKED.",
        lambda: _command_probe(requested_environment={"HOME": "/tmp/home"}),
        "INHERITED_ENVIRONMENT_KEY_NOT_ALLOWED",
    )
    _policy(
        "command.git_config_injection",
        "GIT_CONFIG injetado fica BLOCKED.",
        lambda: _command_probe(requested_environment={"GIT_CONFIG": "/tmp/gitconfig"}),
        "INHERITED_ENVIRONMENT_KEY_NOT_ALLOWED",
    )
    _policy(
        "command.pycache_inside_worktree",
        "pycache dentro da worktree fica BLOCKED.",
        lambda: _command_probe(pycache_prefix="<ISOLATED_WORKTREE>/__pycache__"),
        "PYCACHE_INSIDE_WORKTREE",
    )
    _policy(
        "command.pycache_inside_repository",
        "pycache dentro do repositorio fica BLOCKED.",
        lambda: _command_probe(pycache_prefix="<REPOSITORY_ROOT>/__pycache__"),
        "PYCACHE_INSIDE_REPOSITORY",
    )
    _reject(
        "pinning.fake_verified_true",
        "atlasquant_aion_developer_executable_pinning",
        "executable_pinning_verified=True sem probe e rejeitado.",
        lambda: build_executable_pinning_spec(pins, executable_pinning_verified=True),
    )
    status, result = _invoke(lambda: build_runner_contract(
        builder,
        preflight,
        patch,
        content_attestation=None,
        human_patch_reviewed=True,
        human_patch_reviewer="reviewer-1",
        human_patch_review_refs=["review:patch:1"],
    ))
    boolean_status, _boolean = _invoke(lambda: build_runner_contract(
        builder,
        preflight,
        patch,
        content_binding_verified=True,
        content_binding_ref="tree:123",
        human_patch_reviewed=True,
        human_patch_reviewer="reviewer-1",
        human_patch_review_refs=["review:patch:1"],
    ))
    boolean_closed = (
        status == "ACCEPT"
        and _state_closed(result, "CONTENT_ATTESTATION_REQUIRED")
        and isinstance(result, Mapping)
        and result.get("content_binding_structurally_bound") is False
        and result.get("content_binding_independently_verified") is False
        and boolean_status == "REJECT"
    )
    findings.append(_finding(
        "runner.boolean_binding_without_attestation",
        "atlasquant_aion_developer_runner_contract",
        "content_binding_verified=True sem attestation nao promove o runner."
        if boolean_closed else
        "Um booleano de content binding ainda promove o runner.",
        "BLOCKED_BY_DESIGN" if boolean_closed else "GAP",
        "" if boolean_closed else "HIGH",
    ))
    _policy(
        "command.compileall_without_cache_policy",
        "compileall com writes_repo falso e sem politica de cache fica BLOCKED.",
        lambda: _command_probe(drop_cache_policy=True),
        "COMPILEALL_CACHE_POLICY_REQUIRED",
    )
    _reject(
        "attestation.mutated_after_seal",
        "atlasquant_aion_developer_content_attestation",
        "Payload alterado depois da attestation, mantendo o id, e rejeitado.",
        lambda: _run(_mutate("verification_evidence_refs", ["evidence:mutated:1"])),
    )
    return findings


def _runner_policy_integrity_surface(_world: _World) -> list[dict[str, str]]:
    """A sealed runner or command policy must not survive with a stale id."""
    findings: list[dict[str, str]] = []
    runner = _runner_probe(["test_module.py"])
    policy = build_command_policy_contract(runner)
    ready = (
        runner.get("state") == "READY_FOR_RUNNER_DESIGN_REVIEW"
        and policy.get("state") == "READY_FOR_EXECUTABLE_PINNING_REVIEW"
        and runner.get("execution_authorized") is False
        and policy.get("execution_authorized") is False
    )

    def _reject(invariant_id: str, description: str, fn: Callable[[], Any]) -> None:
        status, _result = _invoke(fn)
        closed = ready and status == "REJECT"
        findings.append(_finding(
            invariant_id,
            "atlasquant_aion_developer_command_policy",
            description if closed else description + " O id antigo ainda foi aceito.",
            "BLOCKED_BY_DESIGN" if closed else "GAP",
            "" if closed else "HIGH",
        ))

    def _stale_runner(mutate: Callable[[dict[str, Any]], None]) -> Callable[[], Any]:
        def run() -> Any:
            cloned = deepcopy(runner)
            mutate(cloned)
            if cloned.get("runner_contract_id") != runner.get("runner_contract_id"):
                return {"state": "RESEALED"}
            return build_command_policy_contract(cloned)
        return run

    _reject(
        "runner_policy.runtime_stale_id",
        "runtime_seconds 900 para 600 com o id antigo e rejeitado.",
        _stale_runner(lambda cloned: cloned["resource_budget"].__setitem__("runtime_seconds", 600)),
    )
    _reject(
        "runner_policy.memory_stale_id",
        "memory_mb alterado com o id antigo e rejeitado.",
        _stale_runner(lambda cloned: cloned["resource_budget"].__setitem__("memory_mb", 256)),
    )
    _reject(
        "runner_policy.output_stale_id",
        "output_bytes alterado com o id antigo e rejeitado.",
        _stale_runner(lambda cloned: cloned["resource_budget"].__setitem__("output_bytes", 4096)),
    )
    _reject(
        "runner_policy.max_commands_stale_id",
        "max_commands alterado com o id antigo e rejeitado.",
        _stale_runner(lambda cloned: cloned["resource_budget"].__setitem__("max_commands", 8)),
    )
    _reject(
        "runner_policy.targets_stale_id",
        "tests.targets alterado com o id antigo e rejeitado.",
        _stale_runner(lambda cloned: cloned["tests"]["targets"].append("test_module.py::extra")),
    )

    def _drop_gate(cloned: dict[str, Any]) -> Any:
        for gate in REQUIRED_MANDATORY_GATES:
            trial = deepcopy(cloned)
            trial["tests"]["mandatory_gates"] = [
                item for item in trial["tests"]["mandatory_gates"] if item != gate
            ]
            if trial.get("runner_contract_id") != runner.get("runner_contract_id"):
                return {"state": "RESEALED", "gate": gate}
            status, _result = _invoke(lambda trial=trial: build_command_policy_contract(trial))
            if status != "REJECT":
                return {"state": "ACCEPTED", "gate": gate}
        raise ValueError("every removed mandatory gate kept a stale id")

    _reject(
        "runner_policy.mandatory_gate_stale_id",
        "Cada mandatory gate removido com o id antigo e rejeitado.",
        lambda: _drop_gate(runner),
    )
    _reject(
        "runner_policy.reviewer_stale_id",
        "Reviewer alterado com o id antigo e rejeitado.",
        _stale_runner(lambda cloned: cloned["review"].__setitem__("human_patch_reviewer", "other-reviewer")),
    )
    _reject(
        "runner_policy.review_ref_stale_id",
        "Review ref alterado com o id antigo e rejeitado.",
        _stale_runner(lambda cloned: cloned["review"]["human_patch_review_refs"].append("review:other")),
    )
    _reject(
        "runner_policy.builder_request_id_stale",
        "builder_request_id alterado com o id antigo e rejeitado.",
        _stale_runner(lambda cloned: cloned["lineage"].__setitem__("builder_request_id", "DEVBUILD-OTHERREQUEST1")),
    )
    _reject(
        "runner_policy.preflight_id_stale",
        "preflight_id alterado com o id antigo e rejeitado.",
        _stale_runner(lambda cloned: cloned["lineage"].__setitem__("preflight_id", "DEVPREF-OTHERREQUEST01")),
    )
    _reject(
        "runner_policy.patch_validation_id_stale",
        "patch_validation_id alterado com o id antigo e rejeitado.",
        _stale_runner(lambda cloned: cloned["lineage"].__setitem__("patch_validation_id", "DEVPATCHVAL-OTHER")),
    )
    _reject(
        "runner_policy.patch_digest_stale",
        "patch_digest alterado com o id antigo e rejeitado.",
        _stale_runner(lambda cloned: cloned["lineage"].__setitem__("patch_digest", "DEVPATCH-OTHER")),
    )
    _reject(
        "runner_policy.attestation_id_stale",
        "content_attestation_id alterado com o id antigo e rejeitado.",
        _stale_runner(lambda cloned: cloned["lineage"].__setitem__("content_attestation_id", "DEVATT-" + ("A" * 18))),
    )
    _reject(
        "runner_policy.structurally_bound_stale",
        "content_binding_structurally_bound alterado com o id antigo e rejeitado.",
        _stale_runner(lambda cloned: cloned.__setitem__("content_binding_structurally_bound", False)),
    )
    _reject(
        "runner_policy.argv_stale",
        "argv alterado com o id antigo e rejeitado.",
        _stale_runner(lambda cloned: cloned["command_plan"][1]["argv"].append("--verbose")),
    )
    _reject(
        "runner_policy.executable_stale",
        "executable alterado com o id antigo e rejeitado.",
        _stale_runner(lambda cloned: cloned["command_plan"][0].__setitem__("executable", "/tmp/python")),
    )
    _reject(
        "runner_policy.cwd_stale",
        "cwd alterado com o id antigo e rejeitado.",
        _stale_runner(lambda cloned: cloned["command_plan"][2].__setitem__("cwd", "/tmp")),
    )
    _reject(
        "runner_policy.shell_stale",
        "shell false para true com o id antigo e rejeitado.",
        _stale_runner(lambda cloned: cloned["command_plan"][2].__setitem__("shell", True)),
    )
    _reject(
        "runner_policy.network_stale",
        "network false para true com o id antigo e rejeitado.",
        _stale_runner(lambda cloned: cloned["command_plan"][2].__setitem__("network", True)),
    )
    _reject(
        "runner_policy.writes_repo_stale",
        "writes_repo false para true com o id antigo e rejeitado.",
        _stale_runner(lambda cloned: cloned["command_plan"][2].__setitem__("writes_repo", True)),
    )
    _reject(
        "runner_policy.pycache_prefix_stale",
        "pycache_prefix alterado com o id antigo e rejeitado.",
        _stale_runner(lambda cloned: cloned["command_plan"][0].__setitem__(
            "pycache_prefix", "<ISOLATED_WORKTREE>/__pycache__",
        )),
    )
    _reject(
        "runner_policy.ephemeral_cache_stale",
        "may_write_ephemeral_cache alterado com o id antigo e rejeitado.",
        _stale_runner(lambda cloned: cloned["command_plan"][0].__setitem__("may_write_ephemeral_cache", False)),
    )
    _reject(
        "runner_policy.path_lookup_stale",
        "path_lookup_allowed false para true com o id antigo e rejeitado.",
        _stale_runner(lambda cloned: cloned.__setitem__("path_lookup_allowed", True)),
    )
    _reject(
        "runner_policy.parent_env_stale",
        "parent_environment_inheritance false para true com o id antigo e rejeitado.",
        _stale_runner(lambda cloned: cloned.__setitem__("parent_environment_inheritance", True)),
    )
    _reject(
        "runner_policy.caller_env_flag_stale",
        "caller_environment_overrides_allowed false para true com o id antigo e rejeitado.",
        _stale_runner(lambda cloned: cloned.__setitem__("caller_environment_overrides_allowed", True)),
    )

    def _authority(cloned: dict[str, Any]) -> Any:
        for flag in (
            "execution_authorized",
            "executor_attached",
            "commands_executed",
            "writes_files",
            "runs_tests",
            "network_called",
            "subprocess_called",
            "automatic_commit",
            "automatic_merge",
            "automatic_deploy",
            "production_change_allowed",
            "real_trading_enabled",
            "tool_output_is_authority",
        ):
            trial = deepcopy(cloned)
            trial[flag] = True
            if trial.get("runner_contract_id") != runner.get("runner_contract_id"):
                return {"state": "RESEALED", "flag": flag}
            status, _result = _invoke(lambda trial=trial: build_command_policy_contract(trial))
            if status != "REJECT":
                return {"state": "ACCEPTED", "flag": flag}
        raise ValueError("every authority flag kept a stale id")

    _reject(
        "runner_policy.authority_flag_stale",
        "Authority flag false para true com o id antigo e rejeitada.",
        lambda: _authority(runner),
    )

    def _nested(cloned: dict[str, Any]) -> None:
        cloned["tests"]["targets"] = list(cloned["tests"]["targets"]) + ["test_other.py"]
        cloned["review"]["human_patch_review_refs"] = list(cloned["review"]["human_patch_review_refs"])
        cloned["review"]["human_patch_review_refs"][0] = "review:copied"
        cloned["command_plan"][0]["argv"] = list(cloned["command_plan"][0]["argv"])
        cloned["command_plan"][0]["argv"][-1] = "<MUTATED_SCOPE>"

    _reject(
        "runner_policy.deepcopy_nested_stale",
        "Deep-copy com mutacao aninhada e id antigo e rejeitado.",
        _stale_runner(_nested),
    )

    def _policy_budget() -> None:
        mutated = deepcopy(policy)
        mutated["resource_budget"]["runtime_seconds"] = 600
        if mutated.get("command_policy_id") != policy.get("command_policy_id"):
            return {"state": "RESEALED"}
        return assert_command_policy_integrity(mutated)

    _reject(
        "command_policy.mutated_keeps_id",
        "Command policy alterada com o id antigo e rejeitada.",
        _policy_budget,
    )

    def _policy_env() -> None:
        mutated = deepcopy(policy)
        mutated["fixed_environment"]["PYTHONHASHSEED"] = "1"
        if mutated.get("command_policy_id") != policy.get("command_policy_id"):
            return {"state": "RESEALED"}
        return assert_command_policy_integrity(mutated)

    _reject(
        "command_policy.fixed_environment_stale",
        "fixed_environment alterado com o id antigo e rejeitado.",
        _policy_env,
    )

    def _policy_plan() -> None:
        mutated = deepcopy(policy)
        mutated["validated_command_plan"][0]["argv"] = ["-m", "compileall", "-q", "<MUTATED>"]
        if mutated.get("command_policy_id") != policy.get("command_policy_id"):
            return {"state": "RESEALED"}
        return assert_command_policy_integrity(mutated)

    _reject(
        "command_policy.validated_plan_stale",
        "validated_command_plan alterado com o id antigo e rejeitado.",
        _policy_plan,
    )

    def _chain() -> None:
        builder = _sealed_runner_request(["test_module.py"])
        preflight = _sealed_preflight(builder)
        patch = {
            "schema": "ATLASQUANT_AION_DEVELOPER_PATCH_VALIDATION_V1",
            "validation_id": "DEVPATCHVAL-1",
            "state": "READY_FOR_PATCH_REVIEW",
            "builder_request_id": builder["request_id"],
            "preflight_id": preflight["preflight_id"],
            "patch_digest": "DEVPATCH-ABC",
            "revision_binding": {
                "baseline_ref": "main@aaa",
                "candidate_ref": "cursor/fix@bbb",
                "refs_match_approved_request": True,
                "revision_content_verified": True,
            },
            "blockers": [],
            "patch_applied": False,
            "execution_authorized": False,
            "executor_attached": False,
        }
        attestation = attestation_for_documents(builder, preflight, patch)
        environment = build_environment_contract()
        pinning = build_executable_pinning_spec([
            {
                "logical_name": "python",
                "absolute_path": "/usr/bin/python3",
                "sha256": "ab" * 32,
                "file_size_bytes": 128,
                "version_claim": "claim-only",
                "verification_evidence_refs": ["evidence:pin:python"],
            },
            {
                "logical_name": "git",
                "absolute_path": "/usr/bin/git",
                "sha256": "cd" * 32,
                "file_size_bytes": 128,
                "version_claim": "claim-only",
                "verification_evidence_refs": ["evidence:pin:git"],
            },
        ])
        fresh = build_os_sandbox_design_review(
            policy,
            pinning,
            attestation,
            environment,
            runner_contract=runner,
        )
        if fresh.get("state") != "READY_FOR_OS_SANDBOX_DESIGN_REVIEW" or fresh.get("execution_authorized") is not False:
            return fresh
        stale_runner = deepcopy(runner)
        stale_runner["resource_budget"]["runtime_seconds"] = 600
        stale_policy = deepcopy(policy)
        stale_policy["fixed_environment"]["PYTHONHASHSEED"] = "1"
        build_os_sandbox_design_review(
            stale_policy,
            pinning,
            attestation,
            environment,
            runner_contract=stale_runner,
        )

    _reject(
        "runner_policy.chained_boundary_stale",
        "Runner e policy adulterados sao rejeitados na fronteira seguinte.",
        _chain,
    )
    return findings


def audit_developer_chain() -> dict[str, Any]:
    """Inspect the local Developer contracts and return a deterministic report."""
    world = _World()
    try:
        findings = []
        findings.extend(_lineage(world))
        findings.extend(_scope(world))
        findings.extend(_branches(world))
        findings.extend(_candidates(world))
        findings.extend(_identities(world))
        findings.extend(_authorization(world))
        findings.extend(_rollback_and_tests(world))
        findings.extend(_workflow_release_authority(world))
        findings.extend(_secrets_and_limits(world))
        findings.extend(_residual_surface(world))
        findings.extend(_contract_gap_surface(world))
        findings.extend(_test_contract_integrity_surface(world))
        findings.extend(_resource_budget_surface(world))
        findings.extend(_attestation_pinning_surface(world))
        findings.extend(_runner_policy_integrity_surface(world))
    finally:
        world.close()

    gaps = [item for item in findings if item["classification"] == "GAP"]
    blocked = [item for item in findings if item["classification"] == "BLOCKED_BY_DESIGN"]
    passed = [item for item in findings if item["classification"] == "PASS"]
    by_severity = {
        severity: [item["invariant_id"] for item in gaps if item["severity"] == severity]
        for severity in SEVERITIES
    }
    return {
        "schema": SCHEMA,
        "state": "GAPS_PRESENT" if gaps else "NO_GAPS",
        "cases_total": len(findings),
        "gap_count": len(gaps),
        "blocked_by_design_count": len(blocked),
        "pass_count": len(passed),
        "findings": findings,
        "gaps": gaps,
        "gaps_by_severity": by_severity,
        "modules": [
            "atlasquant_aion_developer_intelligence",
            "atlasquant_aion_developer_package",
            "atlasquant_aion_developer_diagnostics",
            "atlasquant_aion_developer_correction",
            "atlasquant_aion_developer_evidence_gate",
            "atlasquant_aion_developer_implementation",
            "atlasquant_aion_developer_builder_sandbox",
            "atlasquant_aion_developer_engine",
        ],
        "executes_repository_code": False,
        "writes_existing_files": False,
        "network_called": False,
        "subprocess_called": False,
        "automatic_commit": False,
        "automatic_merge": False,
        "automatic_deploy": False,
        "real_trading_enabled": False,
        "tool_output_is_authority": False,
        "symlink_physical_boundary_verified": False,
        "hardlink_physical_boundary_verified": False,
        "report_digest": sha256(
            json.dumps(findings, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()[:20],
    }


def format_audit_report(report: Mapping[str, Any]) -> str:
    lines = [
        "AION Developer Adversarial Audit",
        str(report.get("state") or ""),
        f"{int(report.get('cases_total') or 0)} cases",
        f"{int(report.get('gap_count') or 0)} gaps",
        f"{int(report.get('blocked_by_design_count') or 0)} blocked",
        f"{int(report.get('pass_count') or 0)} pass",
    ]
    for item in list(report.get("gaps") or []):
        if not isinstance(item, Mapping):
            continue
        lines.append(
            " | ".join([
                str(item.get("invariant_id") or ""),
                str(item.get("severity") or ""),
                str(item.get("module") or ""),
                str(item.get("description") or ""),
            ])
        )
    return "\n".join(lines)


def main() -> int:
    report = audit_developer_chain()
    print(format_audit_report(report))
    return 1 if int(report.get("gap_count") or 0) else 0


if __name__ == "__main__":
    raise SystemExit(main())
