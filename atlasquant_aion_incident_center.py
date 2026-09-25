"""AION security incident-center contracts.

This module consolidates already-available local evidence into a read-only
incident view. It does not rotate secrets, disable accounts, roll back releases,
change feature flags, deploy, publish, bill, or execute trading.

The center is intentionally conservative:
- only explicit signals become incidents;
- UNKNOWN stays UNKNOWN instead of being promoted to healthy;
- rollback is a review recommendation, never an automatic action;
- secret exposure requires out-of-band provider rotation by an authorized human.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping, Sequence
import hashlib
import json

from atlasquant_aion_observability import normalize_events
from atlasquant_release_guard import should_rollback

SCHEMA="ATLASQUANT_AION_INCIDENT_CENTER_V1"

SEVERITIES=("INFO","LOW","MEDIUM","HIGH","CRITICAL")
INCIDENT_KINDS=(
    "CHECKPOINT_INTEGRITY",
    "APPLICATION_HEALTH",
    "ENGINE",
    "SECRET_EXPOSURE",
    "ACCOUNT_ACCESS",
    "OBSERVABILITY",
    "PRODUCTION_IDENTITY",
    "SOURCE_RELIABILITY",
    "COST_GOVERNANCE",
)

_SEVERITY_RANK={name:idx for idx,name in enumerate(SEVERITIES)}


def _now()->str:
    return datetime.now(timezone.utc).isoformat()


def _bool_or_none(value:Any)->bool|None:
    return value if isinstance(value,bool) else None


def _incident_id(kind:str, source:str, detail:str)->str:
    seed=json.dumps([kind,source,detail],ensure_ascii=False,sort_keys=True)
    return "INC-"+hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12].upper()


def _row(
    kind:str,
    severity:str,
    title:str,
    detail:str,
    *,
    source:str,
    evidence_state:str="CONFIRMED",
    response_key:str="generic",
)->dict[str,Any]:
    sev=severity if severity in SEVERITIES else "MEDIUM"
    evidence=str(evidence_state or "UNKNOWN").upper()
    if evidence not in {"CONFIRMED","UNKNOWN","INFERENCE"}:
        evidence="UNKNOWN"
    return {
        "incident_id":_incident_id(kind,source,detail),
        "kind":kind,
        "severity":sev,
        "title":str(title or "")[:180],
        "detail":str(detail or "")[:1200],
        "source":str(source or "")[:240],
        "evidence_state":evidence,
        "status":"OPEN",
        "response_key":response_key,
        "automatic_containment":False,
        "automatic_rollback":False,
        "automatic_secret_rotation":False,
        "automatic_account_mutation":False,
        "real_orders_enabled":False,
    }


def _event_incidents(events:Sequence[Mapping[str,Any]]|None)->list[dict[str,Any]]:
    out=[]
    for event in normalize_events(events):
        severity=str(event.get("severity") or "INFO").upper()
        if severity not in {"WARNING","ERROR","CRITICAL"}:
            continue
        mapped={"WARNING":"MEDIUM","ERROR":"HIGH","CRITICAL":"CRITICAL"}[severity]
        event_type=str(event.get("event_type") or "event")
        message=str(event.get("message") or "")
        kind="OBSERVABILITY"
        response_key="generic"
        lower=(event_type+" "+message).casefold()
        if "secret" in lower or "credential" in lower or "token" in lower:
            kind="SECRET_EXPOSURE"
            response_key="secret"
        elif "account" in lower or "login" in lower or "entitlement" in lower:
            kind="ACCOUNT_ACCESS"
            response_key="access"
        elif "engine" in lower or "motor" in lower:
            kind="ENGINE"
            response_key="engine"
        out.append(_row(
            kind,
            mapped,
            f"Evento {severity}: {event_type}",
            message or "Evento relevante sem mensagem adicional.",
            source=f"checkpoint.operating.events:{event.get('event_id')}",
            evidence_state=str(event.get("truth_state") or "UNKNOWN"),
            response_key=response_key,
        ))
    return out


def collect_incidents(
    *,
    checkpoint:Mapping[str,Any]|None=None,
    runtime_result:Mapping[str,Any]|None=None,
    system_context:Mapping[str,Any]|None=None,
    account_audit:Mapping[str,Any]|None=None,
)->dict[str,Any]:
    """Collect explicit incident signals without performing containment."""
    cp=dict(checkpoint or {})
    runtime=dict(runtime_result or {})
    system=dict(system_context or {})
    audit=dict(account_audit or {})
    incidents=[]

    integrity=runtime.get("integrity") if isinstance(runtime.get("integrity"),Mapping) else {}
    integrity_state=str(integrity.get("state") or "UNKNOWN").upper()
    if integrity_state=="MISMATCH":
        mismatches=", ".join(str(x) for x in list(integrity.get("mismatches",[]) or [])[:8])
        incidents.append(_row(
            "CHECKPOINT_INTEGRITY",
            "CRITICAL",
            "Divergência no Checkpoint Mestre",
            "Os digests persistidos divergem"
            +(f" em: {mismatches}." if mismatches else "."),
            source="runtime_result.integrity",
            response_key="integrity",
        ))
    elif integrity_state=="MIGRATION_REQUIRED":
        incidents.append(_row(
            "CHECKPOINT_INTEGRITY",
            "MEDIUM",
            "Checkpoint requer migração estrutural",
            "A estrutura persistida precisa ser migrada antes de voltar ao estado V6 totalmente confirmado.",
            source="runtime_result.integrity",
            response_key="integrity_migration",
        ))

    app_boot=_bool_or_none(system.get("app_boot_ok"))
    health=_bool_or_none(system.get("health_check_ok"))
    critical_engine=_bool_or_none(system.get("critical_engine_error"))
    data_breach=_bool_or_none(system.get("data_integrity_breach"))
    error_rate=system.get("error_rate_pct")
    max_rate=system.get("max_error_rate_pct",5.0)

    if app_boot is False:
        incidents.append(_row(
            "APPLICATION_HEALTH","CRITICAL",
            "Aplicação não inicializou",
            "Sinal explícito de boot inválido recebido no contexto do sistema.",
            source="system_context.app_boot_ok",
            response_key="production",
        ))
    if health is False:
        incidents.append(_row(
            "APPLICATION_HEALTH","CRITICAL",
            "Health check falhou",
            "Sinal explícito de health check inválido recebido no contexto do sistema.",
            source="system_context.health_check_ok",
            response_key="production",
        ))
    if critical_engine is True:
        incidents.append(_row(
            "ENGINE","CRITICAL",
            "Erro crítico do motor",
            "O contexto do sistema marcou erro crítico do motor.",
            source="system_context.critical_engine_error",
            response_key="engine",
        ))
    if data_breach is True and integrity_state!="MISMATCH":
        incidents.append(_row(
            "CHECKPOINT_INTEGRITY","CRITICAL",
            "Violação de integridade de dados",
            "O contexto do sistema marcou violação explícita de integridade.",
            source="system_context.data_integrity_breach",
            response_key="integrity",
        ))

    if system.get("secret_exposure_confirmed") is True:
        incidents.append(_row(
            "SECRET_EXPOSURE","CRITICAL",
            "Exposição de segredo confirmada",
            "Um segredo/credencial foi explicitamente marcado como exposto. O valor não é exibido aqui.",
            source="system_context.secret_exposure_confirmed",
            response_key="secret",
        ))

    identity=str(system.get("production_identity_state") or "").upper()
    if identity in {"MISMATCH","STALE","UNKNOWN_DEPLOY"}:
        incidents.append(_row(
            "PRODUCTION_IDENTITY","HIGH",
            "Identidade da produção não corresponde à fonte esperada",
            f"Estado informado da identidade de produção: {identity}.",
            source="system_context.production_identity_state",
            response_key="production_identity",
        ))

    reliability=system.get("reliability") if isinstance(system.get("reliability"),Mapping) else {}
    data_guardian=(
        reliability.get("data_guardian")
        if isinstance(reliability.get("data_guardian"),Mapping)
        else {}
    )
    reconciliation=(
        data_guardian.get("reconciliation")
        if isinstance(data_guardian.get("reconciliation"),Mapping)
        else {}
    )
    critical_conflicts=int(reconciliation.get("critical_conflict_count") or 0)
    conflicts=int(reconciliation.get("conflict_count") or 0)
    if critical_conflicts>0:
        incidents.append(_row(
            "SOURCE_RELIABILITY","CRITICAL",
            "Conflito crítico entre fontes confirmadas",
            (
                f"{critical_conflicts} conflito(s) crítico(s) entre fontes confirmadas. "
                "O AION mantém a afirmação em conflito e não escolhe silenciosamente uma fonte."
            ),
            source="system_context.reliability.data_guardian",
            response_key="source_reliability",
        ))
    elif conflicts>0:
        incidents.append(_row(
            "SOURCE_RELIABILITY","HIGH",
            "Fontes confirmadas divergem",
            f"{conflicts} conflito(s) de fonte exigem reconciliação antes de afirmação forte.",
            source="system_context.reliability.data_guardian",
            response_key="source_reliability",
        ))

    cost_guardian=(
        reliability.get("cost_guardian")
        if isinstance(reliability.get("cost_guardian"),Mapping)
        else {}
    )
    cost_state=str(cost_guardian.get("state") or "").upper()
    if cost_state=="BLOCKED_LIMIT":
        incidents.append(_row(
            "COST_GOVERNANCE","MEDIUM",
            "Limite de custo atingido",
            "O Cost Guardian indica que o teto aprovado foi atingido; fallback pago automático permanece proibido.",
            source="system_context.reliability.cost_guardian",
            response_key="cost_governance",
        ))

    if audit:
        review=(
            int(audit.get("user_accounts_without_effective_entitlement") or 0)
            +int(audit.get("duplicate_effective_user_accounts") or 0)
            +int(audit.get("orphan_effective_entitlements") or 0)
        )
        if review>0:
            incidents.append(_row(
                "ACCOUNT_ACCESS","HIGH",
                "Divergência Conta × Entitlement",
                f"{review} divergência(s) de acesso comercial exigem revisão; nenhuma correção automática foi executada.",
                source="account_entitlement_audit",
                response_key="access",
            ))

    operating=cp.get("operating") if isinstance(cp.get("operating"),Mapping) else {}
    incidents.extend(_event_incidents(operating.get("events") if isinstance(operating,Mapping) else []))

    # Rollback is advisory only, and only when all required inputs are actual booleans.
    rollback_review=False
    rollback_reasons=[]
    if None not in {app_boot,health,critical_engine,data_breach}:
        try:
            rb=should_rollback(
                app_boot_ok=bool(app_boot),
                health_check_ok=bool(health),
                critical_engine_error=bool(critical_engine),
                data_integrity_breach=bool(data_breach),
                error_rate_pct=error_rate if error_rate is not None else 0.0,
                max_error_rate_pct=max_rate,
            )
            rollback_review=bool(rb.get("rollback"))
            rollback_reasons=[str(x) for x in list(rb.get("reasons") or [])]
        except Exception:
            rollback_review=True
            rollback_reasons=["Evidência de rollback inválida; revisão humana necessária."]

    dedup={}
    for item in incidents:
        dedup[item["incident_id"]]=item
    rows=list(dedup.values())
    rows.sort(key=lambda row:(
        -_SEVERITY_RANK.get(str(row.get("severity") or "INFO"),0),
        str(row.get("kind") or ""),
        str(row.get("incident_id") or ""),
    ))
    counts={sev:0 for sev in SEVERITIES}
    for row in rows:
        counts[row["severity"]]+=1

    highest="INFO"
    for sev in SEVERITIES:
        if counts[sev]:
            highest=sev

    return {
        "schema":SCHEMA,
        "generated_at":_now(),
        "incidents":rows,
        "total":len(rows),
        "counts":counts,
        "highest_severity":highest,
        "has_critical":counts["CRITICAL"]>0,
        "rollback_review_recommended":rollback_review,
        "rollback_reasons":rollback_reasons,
        "automatic_containment":False,
        "automatic_rollback":False,
        "automatic_secret_rotation":False,
        "automatic_account_mutation":False,
        "real_orders_enabled":False,
        "executes_action":False,
    }


def incident_response_plan(incident:Mapping[str,Any]|None)->dict[str,Any]:
    """Return a human-review response plan without performing any step."""
    item=dict(incident or {})
    kind=str(item.get("kind") or "OBSERVABILITY")
    key=str(item.get("response_key") or "generic")
    common=[
        "Preservar evidências e não ampliar permissões durante o diagnóstico.",
        "Manter trading real e ações externas bloqueados.",
        "Confirmar a origem do sinal antes de declarar causa ou resolução.",
    ]
    specific={
        "integrity":[
            "Bloquear escrita normal do Checkpoint enquanto houver divergência.",
            "Comparar digests e revisar a origem da alteração.",
            "Usar histórico/rollback do Checkpoint apenas com revisão íntegra e aprovação explícita.",
        ],
        "integrity_migration":[
            "Revisar o relatório de migração do Checkpoint.",
            "Aplicar migração condicional somente contra o SHA atual e com aprovação explícita.",
            "Reler e confirmar a integridade após a escrita.",
        ],
        "secret":[
            "Revogar/rotacionar a credencial no provedor autorizado fora deste painel.",
            "Verificar repositório, ambiente, logs e artefatos para exposição residual.",
            "Nunca reutilizar o valor comprometido.",
        ],
        "access":[
            "Revisar conta, perfil e entitlement sem alterar login automaticamente.",
            "Corrigir somente após evidência comercial/administrativa confirmada.",
            "Reauditar Conta × Entitlement depois da mudança autorizada.",
        ],
        "engine":[
            "Preservar logs/inputs do motor e isolar a regressão.",
            "Bloquear promoção automática e manter decisões críticas em revisão humana.",
            "Executar Quality/Shadow/Paper aplicáveis antes de considerar recuperação.",
        ],
        "production":[
            "Preservar logs do deploy afetado e localizar o último commit verde conhecido.",
            "Comparar fonte/deploy e executar rollback somente por processo autorizado.",
            "Após recuperação, rodar Health, Browser Smoke desktop/mobile e Build Identity.",
        ],
        "production_identity":[
            "Não tratar HTTP 200/health isolado como prova de código atual.",
            "Confirmar fingerprint/build identity contra a fonte esperada.",
            "Só depois validar comportamento funcional na produção.",
        ],
        "source_reliability":[
            "Preservar os valores divergentes e as fontes que os forneceram.",
            "Revalidar frescor, identidade e qualidade de cada fonte antes de escolher qualquer valor.",
            "Manter a afirmação dependente em UNKNOWN/CONFLICT até haver reconciliação verificável.",
        ],
        "cost_governance":[
            "Manter fallback pago automático desligado.",
            "Revisar consumo estimado, quota e teto aprovado antes de nova solicitação paga.",
            "Preferir rota gratuita/local quando ela puder cumprir a tarefa com segurança.",
        ],
        "generic":[
            "Classificar o componente afetado e reunir evidências adicionais.",
            "Aplicar contenção manual apenas se houver causa/evidência suficiente.",
            "Registrar causa, mitigação e validação antes de encerrar o incidente.",
        ],
    }.get(key,[])
    steps=common+specific
    return {
        "schema":SCHEMA,
        "incident_id":str(item.get("incident_id") or ""),
        "kind":kind,
        "severity":str(item.get("severity") or "INFO"),
        "steps":steps,
        "requires_human_review":True,
        "automatic_containment":False,
        "automatic_rollback":False,
        "automatic_secret_rotation":False,
        "real_orders_enabled":False,
        "executes_action":False,
    }


def incident_center_rows(snapshot:Mapping[str,Any]|None)->list[dict[str,Any]]:
    rows=[]
    for item in list((snapshot or {}).get("incidents",[]) or []):
        if not isinstance(item,Mapping):
            continue
        rows.append({
            "Severidade":item.get("severity"),
            "Tipo":item.get("kind"),
            "Incidente":item.get("title"),
            "Evidência":item.get("evidence_state"),
            "Origem":item.get("source"),
            "Estado":item.get("status"),
        })
    return rows


__all__=[
    "SCHEMA","SEVERITIES","INCIDENT_KINDS",
    "collect_incidents","incident_response_plan","incident_center_rows",
]
