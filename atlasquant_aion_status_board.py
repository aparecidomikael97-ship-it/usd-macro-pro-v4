"""AION Master Status Board.

Pure/offline truth board that consolidates only evidence supplied by the
current AtlasQuant process. It never calls GitHub, Render, billing providers,
social networks, marketplaces or brokers, and it never converts absence of
evidence into a positive claim.

States:
- CONFIRMED: current execution supplied sufficient explicit evidence;
- BLOCKED: deliberately disabled by a local safety/feature gate;
- EXTERNAL_DEPENDENCY: feature is enabled but requires external proof/connector;
- UNKNOWN: current execution cannot prove the state.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

from atlasquant_aion_operations import queue_summary

SCHEMA="ATLASQUANT_AION_MASTER_STATUS_V1"
STATES=("CONFIRMED","BLOCKED","EXTERNAL_DEPENDENCY","UNKNOWN")


def _text(value:Any,limit:int=500)->str:
    return " ".join(str(value or "").replace("\x00","").split())[:limit]


def _item(
    item_id:str,
    label:str,
    *,
    area:str,
    state:str,
    detail:str,
    source:str,
    next_action:str="",
)->dict[str,Any]:
    normalized=str(state or "UNKNOWN").strip().upper()
    if normalized not in STATES:
        normalized="UNKNOWN"
    return {
        "id":_text(item_id,80),
        "label":_text(label,160),
        "area":_text(area,80),
        "state":normalized,
        "detail":_text(detail,700),
        "source":_text(source,220),
        "next_action":_text(next_action,500),
        "executes_action":False,
    }


def _external_feature_item(
    key:str,
    label:str,
    *,
    flags:Mapping[str,Any],
    system_context:Mapping[str,Any],
    area:str,
    next_action:str,
)->dict[str,Any]:
    enabled=bool(flags.get(key,False))
    evidence_key=f"{key}_confirmed"
    evidence=system_context.get(evidence_key)
    if not enabled:
        return _item(
            key,label,area=area,state="BLOCKED",
            detail=f"Feature flag {key} está desligada nesta execução.",
            source="AION feature flags",
            next_action=next_action,
        )
    if evidence is True:
        return _item(
            key,label,area=area,state="CONFIRMED",
            detail=f"A execução forneceu confirmação explícita para {key}.",
            source=f"system_context.{evidence_key}",
            next_action="",
        )
    return _item(
        key,label,area=area,state="EXTERNAL_DEPENDENCY",
        detail=(
            f"Feature flag {key} está ligada, mas a execução não forneceu "
            "evidência externa confirmada do conector/efeito."
        ),
        source="AION feature flags + system_context",
        next_action=next_action,
    )


def build_master_status_board(
    *,
    checkpoint:Mapping[str,Any]|None=None,
    runtime_result:Mapping[str,Any]|None=None,
    provider:Mapping[str,Any]|None=None,
    feature_flags:Mapping[str,Any]|None=None,
    system_context:Mapping[str,Any]|None=None,
    market_context:Mapping[str,Any]|None=None,
    account_entitlement_audit:Mapping[str,Any]|None=None,
    working_dirty:bool=False,
)->dict[str,Any]:
    cp=dict(checkpoint or {})
    runtime=dict(runtime_result or {})
    provider_state=dict(provider or {})
    flags=dict(feature_flags or {})
    system=dict(system_context or {})
    market=dict(market_context or {})
    commercial_audit=dict(account_entitlement_audit or {})

    items=[]

    system_confirmed=(
        str(system.get("truth_state") or "").upper()=="CONFIRMED"
        and bool(_text(system.get("source_build"),120))
    )
    items.append(_item(
        "app_runtime",
        "Runtime do aplicativo",
        area="system",
        state="CONFIRMED" if system_confirmed else "UNKNOWN",
        detail=(
            f"Build informado pelo processo: {_text(system.get('source_build'),120)}."
            if system_confirmed else
            "Esta execução não forneceu build + truth_state suficientes para confirmar o runtime."
        ),
        source="system_context",
        next_action="Confirmar identidade do build por uma fonte de produção independente." if not system_confirmed else "",
    ))

    runtime_status=str(runtime.get("status") or "UNKNOWN").upper()
    if runtime_status=="CONFIRMED":
        cp_state="CONFIRMED"
        cp_detail="Checkpoint Mestre do runtime foi carregado com confirmação explícita."
    elif runtime_status=="BLOCKED":
        cp_state="BLOCKED"
        cp_detail="Acesso ao Checkpoint Mestre foi bloqueado pela política/runtime."
    else:
        cp_state="UNKNOWN"
        cp_detail=f"Persistência runtime do Checkpoint Mestre não está confirmada ({runtime_status})."
    items.append(_item(
        "checkpoint_runtime",
        "Checkpoint Mestre runtime",
        area="memory",
        state=cp_state,
        detail=cp_detail,
        source="runtime_result.status",
        next_action="Validar credenciais/branch de runtime sem gravar segredo no código." if cp_state!="CONFIRMED" else "",
    ))

    items.append(_item(
        "working_checkpoint",
        "Alterações locais do Checkpoint",
        area="memory",
        state="BLOCKED" if working_dirty else "CONFIRMED",
        detail=(
            "Existem alterações locais ainda não confirmadas como persistidas no runtime."
            if working_dirty else
            "Não há alteração local pendente informada para o Checkpoint nesta sessão."
        ),
        source="AION session working state",
        next_action="Salvar no branch de runtime com aprovação explícita." if working_dirty else "",
    ))

    market_ok=bool(market.get("fresh_confirmed",False) and _text(market.get("summary"),800))
    items.append(_item(
        "market_freshness",
        "Leitura de mercado",
        area="trading",
        state="CONFIRMED" if market_ok else "UNKNOWN",
        detail=(
            _text(market.get("summary"),700)
            if market_ok else
            "Sem leitura de mercado fresca e explicitamente confirmada nesta tela."
        ),
        source="market_context",
        next_action="Atualizar a fonte de mercado antes de produzir viés/briefing factual." if not market_ok else "",
    ))

    pstate=str(provider_state.get("state") or "UNKNOWN").upper()
    external_flag=bool(flags.get("external_llm",False))
    if pstate=="EXTERNAL_READY" and external_flag:
        model_state="CONFIRMED"
        model_detail="Configuração externa está pronta para solicitações opt-in; isso não prova nenhuma chamada nem cobrança."
    elif not external_flag:
        model_state="BLOCKED"
        model_detail="IA externa está desligada por feature flag; modo local/custo zero permanece disponível."
    else:
        model_state="EXTERNAL_DEPENDENCY"
        model_detail=f"IA externa foi habilitada por flag, mas o provedor não está pronto ({pstate})."
    items.append(_item(
        "external_llm",
        "IA externa",
        area="central",
        state=model_state,
        detail=model_detail,
        source="provider_status + feature flags",
        next_action="Configurar provedor/preço/orçamento e aprovar cada solicitação." if model_state!="CONFIRMED" else "",
    ))

    external_specs=(
        ("social_publish","Publicação em redes sociais","studio","Conectar provedor social e validar publicação com aprovação explícita."),
        ("marketplace_publish","Publicação em marketplace","business","Conectar marketplace e validar publicação com aprovação explícita."),
        ("marketplace_orders","Pedidos de marketplace","business","Conectar fonte de pedidos antes de afirmar vendas."),
        ("payment_provider","Pagamento/assinatura","promotions","Conectar provedor e validar eventos assinados; não conceder acesso automaticamente."),
        ("promotion_activation","Ativação de promoções","promotions","Conectar registro/provedor e exigir evidência de ativação."),
        ("entitlement_activation","Ativação de entitlements","subscriptions","Conectar registro de assinaturas e exigir evidência externa confirmada."),
        ("production_deploy","Deploy de produção","development","Usar mecanismo de deploy aprovado e validar identidade exata do build."),
    )
    for key,label,area,next_action in external_specs:
        items.append(_external_feature_item(
            key,label,flags=flags,system_context=system,area=area,next_action=next_action,
        ))

    items.append(_item(
        "real_broker_execution",
        "Trading real",
        area="trading",
        state="BLOCKED",
        detail="Execução real em corretora permanece bloqueada por desenho, independentemente da feature flag.",
        source="AION Guardian contract",
        next_action="Nenhuma. Manter backtest/paper/forward separados de execução real.",
    ))

    operating=cp.get("operating") if isinstance(cp.get("operating"),Mapping) else {}
    tasks=operating.get("tasks") if isinstance(operating,Mapping) else []
    task_summary=queue_summary(tasks if isinstance(tasks,Sequence) and not isinstance(tasks,(str,bytes)) else [])
    waiting=int(task_summary.get("waiting_approval") or 0)
    blocked=int(task_summary.get("blocked") or 0)
    items.append(_item(
        "approval_queue",
        "Fila de aprovações",
        area="secretary",
        state="BLOCKED" if waiting or blocked else "CONFIRMED",
        detail=(
            f"{waiting} aguardando aprovação e {blocked} bloqueadas."
            if waiting or blocked else
            "Nenhuma tarefa aguardando aprovação ou marcada como bloqueada na fila atual."
        ),
        source="Checkpoint Mestre / operating.tasks",
        next_action="Revisar somente as ações sensíveis que realmente exigem decisão do administrador." if waiting or blocked else "",
    ))

    entitlement_section=cp.get("entitlements")
    entitlement_loaded=isinstance(entitlement_section,Mapping) and isinstance(entitlement_section.get("records"),list)
    items.append(_item(
        "entitlement_registry",
        "Registro local de entitlements",
        area="subscriptions",
        state="CONFIRMED" if entitlement_loaded else "UNKNOWN",
        detail=(
            "Estrutura de entitlements está presente no Checkpoint; isso não significa acesso comercial ativo."
            if entitlement_loaded else
            "Estrutura de entitlements não foi confirmada no Checkpoint desta execução."
        ),
        source="Checkpoint Mestre v5",
        next_action="Migrar/carregar Checkpoint v5 antes de administrar direitos de acesso." if not entitlement_loaded else "",
    ))

    audit_schema=str(commercial_audit.get("schema") or "")
    audit_available=audit_schema=="ATLASQUANT_ENTITLEMENT_ACCOUNT_AUDIT_V1"
    audit_accounts=int(commercial_audit.get("accounts_total") or 0) if audit_available else 0
    audit_users=int(commercial_audit.get("active_user_accounts") or 0) if audit_available else 0
    audit_missing=int(commercial_audit.get("user_accounts_without_effective_entitlement") or 0) if audit_available else 0
    audit_duplicates=int(commercial_audit.get("duplicate_effective_user_accounts") or 0) if audit_available else 0
    audit_orphans=int(commercial_audit.get("orphan_effective_entitlements") or 0) if audit_available else 0
    audit_issues=audit_missing+audit_duplicates+audit_orphans

    if not audit_available:
        commercial_state="UNKNOWN"
        commercial_detail="A execução não forneceu a auditoria Conta × Entitlement."
        commercial_next="Calcular a auditoria usando o registro de contas e o Checkpoint Mestre atual."
    elif runtime_status!="CONFIRMED":
        commercial_state="UNKNOWN"
        commercial_detail=(
            "A auditoria foi calculada, mas o Checkpoint Mestre runtime não está confirmado; "
            "não é seguro afirmar reconciliação comercial."
        )
        commercial_next="Confirmar o Checkpoint runtime antes de considerar direitos comerciais reconciliados."
    elif working_dirty:
        commercial_state="BLOCKED"
        commercial_detail=(
            "A auditoria usa alterações locais ainda não confirmadas como persistidas no runtime."
        )
        commercial_next="Revisar e salvar o Checkpoint Mestre antes de fechar a reconciliação comercial."
    elif audit_orphans>0:
        commercial_state="BLOCKED"
        commercial_detail=(
            f"{audit_orphans} entitlement(s) APP_ACCESS efetivo(s) não possuem conta correspondente. "
            "Nenhuma conta foi criada automaticamente."
        )
        commercial_next="Revisar referências órfãs sem provisionamento automático."
    elif audit_users<=0:
        commercial_state="UNKNOWN"
        commercial_detail=(
            f"Registro possui {audit_accounts} conta(s), mas nenhuma conta USER ativa para validar acesso comercial."
        )
        commercial_next="Não inferir clientes ativos; aguardar população USER configurada e evidência aplicável."
    elif audit_issues>0:
        commercial_state="BLOCKED"
        commercial_detail=(
            f"Auditoria encontrou {audit_missing} USER sem direito efetivo, "
            f"{audit_duplicates} com duplicidade e {audit_orphans} entitlement(s) órfão(s)."
        )
        commercial_next="Revisar divergências manualmente; enforcement continua desligado."
    else:
        commercial_state="CONFIRMED"
        commercial_detail=(
            f"{audit_users} conta(s) USER ativa(s) foram reconciliadas sem divergência com APP_ACCESS "
            "na evidência atual. Isso não prova pagamento nem habilita enforcement."
        )
        commercial_next=""

    items.append(_item(
        "commercial_access_audit",
        "Auditoria comercial Conta × Entitlement",
        area="subscriptions",
        state=commercial_state,
        detail=commercial_detail,
        source="configured user registry + entitlement audit + runtime checkpoint",
        next_action=commercial_next,
    ))

    counts={state:0 for state in STATES}
    for item in items:
        counts[item["state"]]+=1
    attention=[
        item for item in items
        if item["state"] in {"BLOCKED","EXTERNAL_DEPENDENCY","UNKNOWN"}
    ]
    return {
        "schema":SCHEMA,
        "states":list(STATES),
        "items":items,
        "counts":counts,
        "attention":attention,
        "has_unresolved":bool(attention),
        "real_orders_enabled":False,
        "automatic_external_actions":False,
    }


def status_rows(board:Mapping[str,Any]|None)->list[dict[str,Any]]:
    raw=(board or {}).get("items") if isinstance(board,Mapping) else []
    rows=[]
    for item in list(raw or []):
        if not isinstance(item,Mapping):
            continue
        rows.append({
            "Área":item.get("area"),
            "Item":item.get("label"),
            "Estado":item.get("state"),
            "Detalhe":item.get("detail"),
            "Próxima ação":item.get("next_action"),
        })
    return rows


__all__=["SCHEMA","STATES","build_master_status_board","status_rows"]
