"""AtlasQuant DEV pre-release readiness audit.

This module is offline/read-only. It checks whether the DEV tree contains the
expected research/backtest/runtime-safety contracts before a human considers a
separate Runtime activation.

It does NOT promote branches, execute live providers, compile Pine in
TradingView, or claim production readiness.
"""
from __future__ import annotations

from pathlib import Path
import math
from typing import Any, Mapping
import json

from atlasquant_runtime_store import evaluate_runtime_branch, DEFAULT_RUNTIME_BRANCH
from atlasquant_tradingview_parity import validate_tradingview_parity
from atlasquant_backtest_snapshot_history import DEFAULT_HISTORY_DIR


ROOT=Path(__file__).resolve().parent

REQUIRED_FILES=(
    "usd_macro_pro_v4_cloud.py",
    "atlasquant_operational_backtest.py",
    "atlasquant_strategy_replay.py",
    "atlasquant_fvg_replay.py",
    "atlasquant_ote_replay.py",
    "atlasquant_crt_replay.py",
    "atlasquant_amd_replay.py",
    "atlasquant_strategy_comparator.py",
    "atlasquant_strategy_stability.py",
    "atlasquant_strategy_walkforward.py",
    "atlasquant_strategy_friction.py",
    "atlasquant_strategy_parameter_robustness.py",
    "atlasquant_backtest_evidence.py",
    "atlasquant_backtest_snapshot.py",
    "atlasquant_backtest_snapshot_history.py",
    "atlasquant_runtime_store.py",
    "atlasquant_release_guard.py",
    "atlasquant_release_candidate.py",
    "atlasquant_source_parity.py",
    "atlasquant_access_control.py",
    "atlasquant_access_panel.py",
    "atlasquant_account_portal.py",
    "atlasquant_account_change_audit.py",
    "atlasquant_registry_admin.py",
    "atlasquant_commercial_launch_guard.py",
    "atlasquant_commercial_security_evidence.py",
    "atlasquant_branch_drift.py",
    "atlasquant_validation_readiness.py",
    "atlasquant_evidence_bundle.py",
    "atlasquant_sales_center.py",
    "atlasquant_user_bootstrap.py",
    "atlasquant_platform_center.py",
    "atlasquant_academy.py",
    "docs/release/ACCESS_CONTROL_SETUP.md",
    "docs/release/SALES_ADMIN_OPERATIONS.md",
    "docs/manifest.webmanifest",
    "docs/sw.js",
    "tradingview/atlasquant_bos_choch_ob_strategy_v1.pine",
    "tradingview/atlasquant_fvg_strategy_v1.pine",
    "tradingview/atlasquant_ote_strategy_v1.pine",
    "tradingview/atlasquant_crt_strategy_v1.pine",
    "tradingview/atlasquant_amd_strategy_v1.pine",
    ".github/workflows/autopilot-v107.yml",
    ".github/workflows/quality-tests.yml",
    ".github/workflows/atlasquant-integration-gate.yml",
    ".github/workflows/atlasquant-source-parity.yml",
    ".github/workflows/atlasquant-ui-smoke.yml",
    ".github/workflows/production-health.yml",
    ".github/workflows/production-browser-smoke.yml",
    "atlasquant_integration_gate.py",
    ".github/workflows/atlasquant-checkpoint.yml",
    "docs/continuidade/PLANO_ATIVACAO_RUNTIME.md",
)


def _check(name: str, ok: bool, detail: str) -> dict[str,Any]:
    return {"name":name,"ok":bool(ok),"detail":str(detail)}


def run_dev_preflight(
    *,
    root: str | Path | None = None,
    parity_report: Mapping[str,Any] | None = None,
) -> dict[str,Any]:
    base=Path(root) if root is not None else ROOT
    checks=[]

    missing=[path for path in REQUIRED_FILES if not (base/path).is_file()]
    checks.append(_check(
        "required_files",
        not missing,
        "Arquivos essenciais presentes." if not missing else "Ausentes: "+", ".join(missing),
    ))

    app=(base/"usd_macro_pro_v4_cloud.py").read_text(encoding="utf-8") if (base/"usd_macro_pro_v4_cloud.py").is_file() else ""
    panel=(base/"atlasquant_backtest_panel.py").read_text(encoding="utf-8") if (base/"atlasquant_backtest_panel.py").is_file() else ""
    workflow=(base/".github/workflows/autopilot-v107.yml").read_text(encoding="utf-8") if (base/".github/workflows/autopilot-v107.yml").is_file() else ""
    gitignore=(base/".gitignore").read_text(encoding="utf-8") if (base/".gitignore").is_file() else ""

    checks.append(_check(
        "backtest_ui_integrated",
        "from atlasquant_backtest_panel import render_operational_backtest_panel" in app
        and "render_operational_backtest_panel()" in app,
        "Backtest avançado importado e renderizado no app DEV.",
    ))

    access_panel=(base/"atlasquant_access_panel.py").read_text(encoding="utf-8") if (base/"atlasquant_access_panel.py").is_file() else ""
    account_portal=(base/"atlasquant_account_portal.py").read_text(encoding="utf-8") if (base/"atlasquant_account_portal.py").is_file() else ""
    gate_import="from atlasquant_access_panel import render_access_gate" in app
    gate_call=app.find("render_access_gate()")
    first_provider=app.find("def _get(")
    checks.append(_check(
        "private_access_gate_integrated",
        gate_import and gate_call>=0 and first_provider>=0 and gate_call<first_provider
        and 'environment=="PRODUCTION"' in access_panel,
        "Login fail-closed integrado antes da coleta principal e obrigatório em PRODUCTION.",
    ))
    checks.append(_check(
        "role_portal_integrated",
        "from atlasquant_account_portal import render_account_portal" in app
        and 'with abas[16]:' in app
        and 'render_account_portal(_ATLASQUANT_ACCESS)' in app
        and '"Trading real","DESATIVADO"' in account_portal,
        "Portal USER/SALES/ADMIN integrado sem habilitar trading real.",
    ))

    platform_center=(base/"atlasquant_platform_center.py").read_text(encoding="utf-8") if (base/"atlasquant_platform_center.py").is_file() else ""
    checks.append(_check(
        "platform_center_integrated",
        "from atlasquant_platform_center import render_platform_center" in app
        and 'with abas[17]:' in app
        and "render_platform_center()" in app
        and '"Google Play","Distribuição atual":"PENDENTE"' in platform_center
        and '"Apple App Store","Distribuição atual":"PENDENTE"' in platform_center,
        "Central multiplataforma integrada sem confundir PWA com publicação nativa.",
    ))

    sales_center=(base/"atlasquant_sales_center.py").read_text(encoding="utf-8") if (base/"atlasquant_sales_center.py").is_file() else ""
    registry_admin=(base/"atlasquant_registry_admin.py").read_text(encoding="utf-8") if (base/"atlasquant_registry_admin.py").is_file() else ""
    academy=(base/"atlasquant_academy.py").read_text(encoding="utf-8") if (base/"atlasquant_academy.py").is_file() else ""
    experience=(base/"experience_v103.py").read_text(encoding="utf-8") if (base/"experience_v103.py").is_file() else ""
    checks.append(_check(
        "academy_text_curriculum_ready",
        "ACADEMY_TOPICS" in academy
        and "academy_minimum_text_ready" in academy
        and "render_academy_panel" in academy
        and "from atlasquant_academy import render_academy_panel" in experience
        and "render_academy_panel()" in experience
        and '"academy_text_ready":bool(academy_minimum_text_ready())' in sales_center,
        "Academy textual estruturada está integrada; vídeos permanecem uma etapa separada.",
    ))
    checks.append(_check(
        "sales_center_integrated",
        "from atlasquant_sales_center import render_sales_center" in app
        and 'with abas[18]:' in app
        and "render_sales_center(_ATLASQUANT_ACCESS)" in app
        and "Área comercial restrita aos perfis SALES e ADMIN autenticados." in sales_center,
        "Portal SALES integrado e protegido por perfil autenticado.",
    ))

    launch_guard=(base/"atlasquant_commercial_launch_guard.py").read_text(encoding="utf-8") if (base/"atlasquant_commercial_launch_guard.py").is_file() else ""
    checks.append(_check(
        "commercial_launch_fail_closed",
        "automatic_launch" in launch_guard
        and '"automatic_launch":False' in launch_guard
        and '"status":"REVIEWABLE" if not blockers else "BLOCKED"' in launch_guard
        and "Venda pública ainda BLOQUEADA" in sales_center,
        "Venda pública permanece fail-closed e exige revisão humana.",
    ))
    security_evidence=(base/"atlasquant_commercial_security_evidence.py").read_text(encoding="utf-8") if (base/"atlasquant_commercial_security_evidence.py").is_file() else ""
    checks.append(_check(
        "commercial_security_evidence_bounded",
        '"external_legal_verified":False' in security_evidence
        and '"external_data_licensing_verified":False' in security_evidence
        and '"external_billing_verified":False' in security_evidence
        and "automatic_launch=True" not in security_evidence
        and "real_orders=True" not in security_evidence,
        "Evidência interna de segurança não certifica requisitos externos nem habilita lançamento/trading.",
    ))

    checks.append(_check(
        "account_registry_non_destructive",
        "apply_non_destructive_change" in registry_admin
        and "destructive account removal is not allowed" in registry_admin
        and "automatic" not in registry_admin.lower(),
        "Administração de contas exporta mudanças para revisão e bloqueia remoção destrutiva.",
    ))

    account_audit=(base/"atlasquant_account_change_audit.py").read_text(encoding="utf-8") if (base/"atlasquant_account_change_audit.py").is_file() else ""
    checks.append(_check(
        "account_change_audit_safe",
        '"contains_password":False' in account_audit
        and '"contains_password_hash":False' in account_audit
        and '"automatic_apply":False' in account_audit,
        "Mudanças administrativas geram manifesto sem credenciais e sem aplicação automática.",
    ))

    integration_gate=(base/".github/workflows/atlasquant-integration-gate.yml").read_text(encoding="utf-8") if (base/".github/workflows/atlasquant-integration-gate.yml").is_file() else ""
    production_health=(base/".github/workflows/production-health.yml").read_text(encoding="utf-8") if (base/".github/workflows/production-health.yml").is_file() else ""
    production_browser=(base/".github/workflows/production-browser-smoke.yml").read_text(encoding="utf-8") if (base/".github/workflows/production-browser-smoke.yml").is_file() else ""
    integration_ui_smoke=(base/".github/workflows/atlasquant-ui-smoke.yml").read_text(encoding="utf-8") if (base/".github/workflows/atlasquant-ui-smoke.yml").is_file() else ""
    checks.append(_check(
        "source_integration_gate_manual",
        "branches: [atlasquant-integration]" in integration_gate
        and "contents: read" in integration_gate
        and "origin/main...HEAD" in integration_gate
        and "evaluate_integration_candidate" in integration_gate
        and "git merge" not in integration_gate
        and "git push" not in integration_gate,
        "Gate de integração é source-only, baseado no main atual e não faz merge/push.",
    ))
    source_parity_workflow=(base/".github/workflows/atlasquant-source-parity.yml").read_text(encoding="utf-8") if (base/".github/workflows/atlasquant-source-parity.yml").is_file() else ""
    checks.append(_check(
        "runtime_source_parity_observational",
        "branches: [atlasquant-runtime, atlasquant-integration]" in source_parity_workflow
        and "permissions:\n  contents: read" in source_parity_workflow
        and "origin/atlasquant-integration" in source_parity_workflow
        and "compare_source_trees" in source_parity_workflow
        and "git push" not in source_parity_workflow
        and "update-ref" not in source_parity_workflow,
        "Paridade de fonte Runtime↔Integration é observacional, read-only e não sincroniza automaticamente.",
    ))
    checks.append(_check(
        "production_observability_read_only",
        "permissions:\n  contents: read" in production_health
        and "permissions:\n  contents: read" in production_browser
        and "contents: write" not in production_health
        and "contents: write" not in production_browser
        and "branches: [main]" in production_health
        and "branches: [main, atlasquant-integration]" in production_browser
        and "Warm production service" in production_browser
        and "_stcore/health" in production_health
        and "_stcore/health" in production_browser
        and 'for render_attempt in range(1, 7)' in production_browser
        and 'page.reload(wait_until="domcontentloaded"' in production_browser
        and 'page.on("pageerror"' in production_browser
        and "actions/upload-artifact@v7" in production_browser,
        "Health permanece main-scoped; browser smoke é read-only, resiliente a cold start e preserva evidência diagnóstica.",
    ))

    checks.append(_check(
        "integration_ui_smoke_read_only",
        "branches: [atlasquant-integration]" in integration_ui_smoke
        and "permissions:\n  contents: read" in integration_ui_smoke
        and "contents: write" not in integration_ui_smoke
        and 'ATLASQUANT_ENV: "LOCAL"' in integration_ui_smoke
        and 'ATLASQUANT_AUTH_REQUIRED: "false"' in integration_ui_smoke
        and 'ATLASQUANT_OFFLINE_SMOKE: "true"' in integration_ui_smoke
        and '"width":390' in integration_ui_smoke
        and '"width":1440' in integration_ui_smoke
        and 'page.locator(".aq-hero").count()' in integration_ui_smoke
        and '"ATLASQUANT" in body_text' in integration_ui_smoke
        and '"Carregando dados macroeconômicos globais" in body_text' in integration_ui_smoke
        and "horizontal_overflow_px" in integration_ui_smoke
        and "stException" in integration_ui_smoke
        and "secrets." not in integration_ui_smoke,
        "Candidato possui smoke local desktop/mobile offline, sem segredos, que exige o hero AtlasQuant realmente renderizado.",
    ))

    provider_markers=(
        "api.twelvedata.com",
        "api.stlouisfed.org",
        "newsapi.org",
        "requests.get(",
        "requests.post(",
        "requests.put(",
    )
    panel_hits=[marker for marker in provider_markers if marker in panel]
    checks.append(_check(
        "backtest_panel_offline",
        not panel_hits,
        "Painel de Backtest sem chamadas diretas a provedores."
        if not panel_hits else "Marcadores de rede encontrados: "+", ".join(panel_hits),
    ))

    runtime_policy=evaluate_runtime_branch(DEFAULT_RUNTIME_BRANCH)
    main_policy=evaluate_runtime_branch("main")
    dev_policy=evaluate_runtime_branch("atlasquant-dev")
    checks.append(_check(
        "runtime_branch_policy",
        runtime_policy.safe_for_runtime_writes
        and not main_policy.safe_for_runtime_writes
        and not dev_policy.safe_for_runtime_writes,
        "Runtime dedicada aceita escrita; main/DEV rejeitam escrita operacional.",
    ))

    checks.append(_check(
        "autopilot_targets_runtime",
        'GITHUB_DATA_BRANCH: "atlasquant-runtime"' in workflow
        and 'GITHUB_BRANCH_HISTORICO: "atlasquant-runtime"' in workflow
        and 'GITHUB_BRANCH_HISTORICO: "main"' not in workflow,
        "Workflow de Autopilot aponta para atlasquant-runtime.",
    ))
    checkpoint=(base/".github/workflows/atlasquant-checkpoint.yml").read_text(encoding="utf-8") if (base/".github/workflows/atlasquant-checkpoint.yml").is_file() else ""
    branch_drift=(base/"atlasquant_branch_drift.py").read_text(encoding="utf-8") if (base/"atlasquant_branch_drift.py").is_file() else ""
    checks.append(_check(
        "source_checkpoint_excludes_runtime_evidence",
        "RUNTIME_MUTABLE_PATHS" in checkpoint
        and "paths-ignore:" in checkpoint
        and "automatic_merge_allowed" in branch_drift
        and '"automatic_merge_allowed":False' in branch_drift,
        "Checkpoint de fonte exclui evidência mutável e reconciliação de branch permanece manual.",
    ))

    history_parts={str(x).lower() for x in DEFAULT_HISTORY_DIR.parts}
    checks.append(_check(
        "research_history_isolated",
        "dados" not in history_parts and ".atlasquant_research/" in gitignore,
        "Histórico de pesquisa fora de dados/ e ignorado pelo Git.",
    ))

    if parity_report is None:
        parity_report=validate_tradingview_parity()
    parity_ok=str(parity_report.get("status") or "")=="OK" and int(parity_report.get("failed") or 0)==0
    checks.append(_check(
        "tradingview_python_static_parity",
        parity_ok,
        f"Paridade estática: {parity_report.get('passed',0)} OK / {parity_report.get('failed',0)} falha(s).",
    ))

    failed=[x for x in checks if not x["ok"]]
    return {
        "schema":"ATLASQUANT_DEV_PREFLIGHT_V1",
        "status":"DEV_PREFLIGHT_OK" if not failed else "DEV_PREFLIGHT_BLOCKED",
        "checks":checks,
        "passed":len(checks)-len(failed),
        "failed":len(failed),
        "blockers":[x["name"] for x in failed],
        "manual_runtime_activation_required":True,
        "runtime_promotion_performed":False,
        "limitations":[
            "Não executa provedores live nem valida credenciais.",
            "Não compila Pine dentro do TradingView.",
            "Não substitui health check pós-deploy da Runtime.",
            "Não promove DEV para Runtime/Main.",
        ],
    }


def build_dev_readiness_manifest(
    preflight: Mapping[str,Any],
    *,
    dev_sha: str,
    quality_run_id: str | int,
    tests_total: int,
    tests_failed: int,
    compile_ok: bool,
) -> dict[str,Any]:
    """Combine static preflight with externally observed CI evidence."""
    def safe_count(value: Any) -> tuple[int,bool]:
        if isinstance(value,bool):
            return 0,False
        try:
            x=float(value)
            if not math.isfinite(x) or x < 0 or not x.is_integer():
                return 0,False
            return int(x),True
        except Exception:
            return 0,False
    total,total_valid=safe_count(tests_total)
    failed,failed_valid=safe_count(tests_failed)
    counts_valid=bool(total_valid and failed_valid and failed<=total)
    quality_ok=bool(compile_ok) and counts_valid and total>0 and failed==0
    preflight_ok=str(preflight.get("status") or "")=="DEV_PREFLIGHT_OK" and int(preflight.get("failed") or 0)==0

    blockers=[]
    if not preflight_ok:
        blockers.append("DEV_PREFLIGHT_BLOCKED")
    if not counts_valid:
        blockers.append("INVALID_TEST_EVIDENCE")
    if not compile_ok:
        blockers.append("COMPILE_FAILED")
    if total<=0:
        blockers.append("NO_TEST_EVIDENCE")
    if failed:
        blockers.append("QUALITY_TEST_FAILURES")

    return {
        "schema":"ATLASQUANT_DEV_READINESS_MANIFEST_V1",
        "dev_sha":str(dev_sha or ""),
        "quality_run_id":str(quality_run_id or ""),
        "tests_total":total,
        "tests_failed":failed,
        "compile_ok":bool(compile_ok),
        "quality_ok":quality_ok,
        "preflight_status":preflight.get("status"),
        "preflight_passed":int(preflight.get("passed") or 0),
        "preflight_failed":int(preflight.get("failed") or 0),
        "status":"DEV_VALIDATED_PENDING_RUNTIME_ACTIVATION"
        if quality_ok and preflight_ok else "DEV_BLOCKED",
        "blockers":blockers,
        "manual_runtime_activation_required":True,
        "runtime_health_check_pending":True,
        "runtime_promotion_performed":False,
        "notes":[
            "Manifesto descreve a DEV; não certifica produção.",
            "Ativação Runtime exige autorização específica e validação pós-deploy.",
        ],
    }


def readiness_manifest_json(manifest: Mapping[str,Any]) -> str:
    return json.dumps(dict(manifest),ensure_ascii=False,indent=2,sort_keys=True)
