"""Guided training for AION BUSINESS administrator.

Pure/offline training only. All companies, numbers and conversations returned by
this module are fictional fixtures. Nothing is sent, charged, published,
deployed or activated.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

SCHEMA = "ATLASQUANT_AION_BUSINESS_GUIDED_TRAINING_V1"
VERSION = "1"

SCENARIOS = (
    {
        "id": "CLINICA_LOCAL",
        "label": "Clínica local",
        "company": "Clínica Horizonte Demo",
        "segment": "Clínica",
        "situation": (
            "Recebe muitos contatos por WhatsApp, demora para responder em horários de pico "
            "e perde pacientes que pedem informação mas não agendam."
        ),
        "fixture": {
            "leads_open": 46,
            "avg_response_hours": 4.2,
            "abandoned_quotes": 11,
            "returning_customers_pct": 18,
        },
        "pain_points": (
            "atendimento_lento",
            "leads_sem_followup",
            "agendamento",
        ),
    },
    {
        "id": "IMOBILIARIA_LOCAL",
        "label": "Imobiliária",
        "company": "Imobiliária Norte Demo",
        "segment": "Imobiliária",
        "situation": (
            "Tem grande volume de leads de portais e redes sociais, mas a equipe não consegue "
            "qualificar todos com rapidez nem retomar quem parou de responder."
        ),
        "fixture": {
            "leads_open": 78,
            "avg_response_hours": 2.8,
            "abandoned_quotes": 23,
            "returning_customers_pct": 26,
        },
        "pain_points": (
            "qualificacao",
            "leads_sem_followup",
            "pipeline",
        ),
    },
    {
        "id": "SERVICO_LOCAL",
        "label": "Prestador de serviços",
        "company": "Prime Serviços Demo",
        "segment": "Prestador de Serviços",
        "situation": (
            "Faz divulgação irregular, responde orçamento manualmente e não acompanha quem "
            "pediu preço mas não fechou."
        ),
        "fixture": {
            "leads_open": 31,
            "avg_response_hours": 5.1,
            "abandoned_quotes": 14,
            "returning_customers_pct": 12,
        },
        "pain_points": (
            "divulgacao",
            "orcamentos",
            "leads_sem_followup",
            "retencao",
        ),
    },
)

TRAINING_FLOW = (
    {
        "id": "ENTENDER",
        "label": "1. Entender a empresa",
        "goal": "Explicar o problema em linguagem simples antes de falar de tecnologia.",
    },
    {
        "id": "DIAGNOSTICAR",
        "label": "2. Diagnosticar",
        "goal": "Separar sintomas, gargalos e dados que ainda precisam ser confirmados.",
    },
    {
        "id": "LER_RADAR",
        "label": "3. Ler o Radar",
        "goal": "Mostrar o que exige atenção sem sobrecarregar o cliente com detalhes técnicos.",
    },
    {
        "id": "MONTAR_PACOTE",
        "label": "4. Montar o pacote",
        "goal": "Combinar serviços que resolvem o conjunto do problema, não vender peças isoladas.",
    },
    {
        "id": "EXPLICAR_ENTREGA",
        "label": "5. Explicar a entrega",
        "goal": "Deixar claro o que será implantado, o que o cliente verá e como a manutenção funciona.",
    },
    {
        "id": "TRATAR_OBJECOES",
        "label": "6. Tratar objeções",
        "goal": "Responder dúvidas sem prometer resultado financeiro nem inventar capacidade.",
    },
    {
        "id": "FECHAR_PROXIMO_PASSO",
        "label": "7. Fechar o próximo passo",
        "goal": "Concluir com diagnóstico/proposta/implantação, sem pressão e com escopo definido.",
    },
)

OBJECTIONS = (
    {
        "id": "PRECO",
        "question": "Por que eu pagaria todo mês?",
        "answer": (
            "Porque o serviço não termina na instalação. A manutenção cobre acompanhamento, "
            "ajustes, revisão dos fluxos, métricas, suporte e evolução do que foi contratado. "
            "O valor final depende do escopo, volume e integrações."
        ),
    },
    {
        "id": "SUBSTITUI_PESSOAS",
        "question": "Isso vai substituir minha equipe?",
        "answer": (
            "O objetivo principal é retirar tarefas repetitivas e organizar o fluxo. A empresa "
            "decide onde manter revisão humana, atendimento humano e aprovações."
        ),
    },
    {
        "id": "GARANTIA_VENDAS",
        "question": "Você garante que minhas vendas vão aumentar?",
        "answer": (
            "Não. Podemos medir gargalos, melhorar processos e acompanhar indicadores, mas não "
            "prometemos resultado financeiro. O desempenho depende de vários fatores da empresa e do mercado."
        ),
    },
    {
        "id": "DADOS",
        "question": "Vocês vão ter acesso a todos os meus dados?",
        "answer": (
            "O acesso deve ser limitado ao necessário para o serviço contratado, com permissões "
            "definidas e revisão de segurança. Dados e integrações precisam ser combinados no onboarding."
        ),
    },
    {
        "id": "COMPLEXIDADE",
        "question": "Eu vou precisar aprender tecnologia?",
        "answer": (
            "A proposta é o contrário: o cliente recebe um painel simples, alertas, resultados e "
            "próximos passos. A complexidade técnica fica por trás do AION e da operação."
        ),
    },
)

PACKAGE_RULES = {
    "ATENDIMENTO_CONVERSAO": {
        "label": "Atendimento & Conversão",
        "signals": {
            "atendimento_lento",
            "leads_sem_followup",
            "agendamento",
            "qualificacao",
            "orcamentos",
        },
        "components": (
            "Atendimento inicial / FAQ",
            "Qualificação de leads",
            "Follow-up",
            "Agendamento ou próximo passo",
        ),
    },
    "MARKETING_VENDAS": {
        "label": "Marketing & Vendas",
        "signals": {"divulgacao", "conteudo", "criativos", "campanhas"},
        "components": (
            "Conteúdo e criativos",
            "Campanhas",
            "Acompanhamento de leads",
            "Relatório de desempenho",
        ),
    },
    "GESTAO_INTELIGENTE": {
        "label": "Gestão Inteligente",
        "signals": {"pipeline", "gestao", "metricas", "relatorios"},
        "components": (
            "CRM / pipeline",
            "Painel de resultados",
            "Relatórios AION",
            "Automações internas",
        ),
    },
    "AION_BUSINESS_COMPLETO": {
        "label": "AION Business Completo",
        "signals": {
            "atendimento_lento",
            "leads_sem_followup",
            "agendamento",
            "qualificacao",
            "orcamentos",
            "divulgacao",
            "conteudo",
            "criativos",
            "campanhas",
            "pipeline",
            "gestao",
            "metricas",
            "relatorios",
            "retencao",
        },
        "components": (
            "Atrair",
            "Atender",
            "Converter",
            "Reter",
        ),
    },
}


def _clean(value: Any, limit: int = 500) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _scenario(scenario_id: Any) -> dict[str, Any]:
    token = _clean(scenario_id, 80).upper()
    row = next((item for item in SCENARIOS if item["id"] == token), None)
    if row is None:
        row = SCENARIOS[0]
    return {
        **dict(row),
        "fixture": dict(row["fixture"]),
        "pain_points": list(row["pain_points"]),
    }


def scenario_catalog() -> list[dict[str, Any]]:
    return [
        {
            "id": item["id"],
            "label": item["label"],
            "company": item["company"],
            "segment": item["segment"],
            "situation": item["situation"],
        }
        for item in SCENARIOS
    ]


def training_session(scenario_id: Any = "CLINICA_LOCAL", *, step: Any = 1) -> dict[str, Any]:
    scenario = _scenario(scenario_id)
    try:
        index = int(step) - 1
    except Exception:
        index = 0
    index = min(max(index, 0), len(TRAINING_FLOW) - 1)
    current = dict(TRAINING_FLOW[index])
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "mode": "FICTIONAL_TRAINING",
        "scenario": scenario,
        "step": index + 1,
        "total_steps": len(TRAINING_FLOW),
        "current": current,
        "previous": dict(TRAINING_FLOW[index - 1]) if index > 0 else None,
        "next": dict(TRAINING_FLOW[index + 1]) if index + 1 < len(TRAINING_FLOW) else None,
        "real_client": False,
        "runtime_activated": False,
        "executes_action": False,
    }


def diagnostic_brief(scenario_id: Any = "CLINICA_LOCAL") -> dict[str, Any]:
    scenario = _scenario(scenario_id)
    points = list(scenario["pain_points"])
    primary = []
    if "atendimento_lento" in points:
        primary.append("Tempo de resposta")
    if "leads_sem_followup" in points:
        primary.append("Leads sem acompanhamento")
    if "qualificacao" in points:
        primary.append("Qualificação")
    if "agendamento" in points:
        primary.append("Agendamento")
    if "orcamentos" in points:
        primary.append("Orçamentos sem retorno")
    if "divulgacao" in points:
        primary.append("Consistência de divulgação")
    if "pipeline" in points:
        primary.append("Organização do pipeline")
    if "retencao" in points:
        primary.append("Retenção e reativação")
    return {
        "schema": SCHEMA,
        "scenario_id": scenario["id"],
        "company": scenario["company"],
        "segment": scenario["segment"],
        "summary": scenario["situation"],
        "priority_gaps": primary,
        "questions_to_confirm": [
            "Quantos contatos chegam por semana e por quais canais?",
            "Quanto tempo a equipe leva para responder?",
            "Onde os leads e clientes são registrados hoje?",
            "Qual parte do processo mais consome tempo?",
            "Quais números a empresa já acompanha com fonte confiável?",
        ],
        "truth_state": "FICTIONAL_FIXTURE",
        "executes_action": False,
    }


def package_fit(scenario_id: Any = "CLINICA_LOCAL") -> dict[str, Any]:
    """Suggest a training package from fictional pain signals only."""
    scenario = _scenario(scenario_id)
    signals = set(scenario["pain_points"])
    scores: list[tuple[int, str]] = []
    for package_id, spec in PACKAGE_RULES.items():
        if package_id == "AION_BUSINESS_COMPLETO":
            continue
        score = len(signals.intersection(spec["signals"]))
        scores.append((score, package_id))
    scores.sort(key=lambda item: (-item[0], item[1]))
    best_score, best_id = scores[0]
    # If two or more operational domains are strongly represented, use the
    # complete package as the training example rather than stacking add-ons.
    domains = 0
    if signals.intersection(PACKAGE_RULES["ATENDIMENTO_CONVERSAO"]["signals"]):
        domains += 1
    if signals.intersection(PACKAGE_RULES["MARKETING_VENDAS"]["signals"]):
        domains += 1
    if signals.intersection(PACKAGE_RULES["GESTAO_INTELIGENTE"]["signals"]):
        domains += 1
    if "retencao" in signals:
        domains += 1
    selected_id = "AION_BUSINESS_COMPLETO" if domains >= 3 else best_id
    selected = PACKAGE_RULES[selected_id]
    return {
        "schema": SCHEMA,
        "mode": "TRAINING_FIT",
        "scenario_id": scenario["id"],
        "package_id": selected_id,
        "package_label": selected["label"],
        "components": list(selected["components"]),
        "matched_signals": sorted(signals.intersection(selected["signals"])),
        "fit_score": best_score if selected_id != "AION_BUSINESS_COMPLETO" else len(signals),
        "pricing_defined": False,
        "requires_real_diagnostic_before_proposal": True,
        "promises_result": False,
        "executes_action": False,
    }


def delivery_walkthrough(scenario_id: Any = "CLINICA_LOCAL") -> dict[str, Any]:
    scenario = _scenario(scenario_id)
    fit = package_fit(scenario["id"])
    return {
        "schema": SCHEMA,
        "scenario_id": scenario["id"],
        "company": scenario["company"],
        "what_client_receives": [
            "Onboarding e definição do escopo",
            "Implantação do pacote contratado",
            "Portal/Radar simples com indicadores acordados",
            "Rotina de manutenção e suporte",
            "Relatório periódico com resultados observados e próximos passos",
        ],
        "what_client_sees": [
            "O que está acontecendo",
            "O que exige atenção",
            "O que já melhorou ou piorou com base em dados disponíveis",
            "O próximo passo recomendado para revisão",
        ],
        "maintenance_covers": [
            "Acompanhamento do funcionamento",
            "Ajustes de fluxo dentro do escopo",
            "Revisão de métricas",
            "Suporte e incidentes",
            "Evolução controlada do pacote",
        ],
        "package_label": fit["package_label"],
        "installation_plus_monthly_maintenance": True,
        "pricing_defined": False,
        "runtime_activated": False,
        "executes_action": False,
    }


def objection_catalog() -> list[dict[str, str]]:
    return [dict(item) for item in OBJECTIONS]


def objection_answer(objection_id: Any) -> dict[str, Any]:
    token = _clean(objection_id, 80).upper()
    item = next((row for row in OBJECTIONS if row["id"] == token), None)
    if item is None:
        return {
            "schema": SCHEMA,
            "state": "UNKNOWN_OBJECTION",
            "question": "",
            "answer": "Não invente uma resposta. Registre a dúvida, confirme o escopo e responda depois com evidência.",
            "promises_result": False,
            "executes_action": False,
        }
    return {
        "schema": SCHEMA,
        "state": "TRAINING_ANSWER",
        **dict(item),
        "promises_result": False,
        "executes_action": False,
    }


def simulated_sales_conversation(scenario_id: Any = "CLINICA_LOCAL") -> list[dict[str, str]]:
    scenario = _scenario(scenario_id)
    fit = package_fit(scenario["id"])
    return [
        {
            "speaker": "ADMIN",
            "text": (
                f"Antes de falar de tecnologia, quero entender o processo da {scenario['company']} "
                "e onde vocês mais perdem tempo ou oportunidades."
            ),
        },
        {
            "speaker": "CLIENTE_DEMO",
            "text": scenario["situation"],
        },
        {
            "speaker": "ADMIN",
            "text": (
                "O primeiro passo é um diagnóstico para confirmar volumes, canais, tempos e gargalos. "
                "Com isso, mostramos no Radar o que merece atenção."
            ),
        },
        {
            "speaker": "ADMIN",
            "text": (
                f"Neste exercício, o pacote que melhor encaixa é {fit['package_label']}, "
                "mas numa empresa real a proposta só é fechada depois do diagnóstico."
            ),
        },
        {
            "speaker": "CLIENTE_DEMO",
            "text": "E depois da instalação, como funciona?",
        },
        {
            "speaker": "ADMIN",
            "text": (
                "A empresa recebe o sistema combinado no escopo e continua com manutenção, suporte, "
                "métricas e ajustes recorrentes. O painel deve ser simples para quem usa."
            ),
        },
    ]


def training_scorecard(
    *,
    explained_problem_before_technology: Any = False,
    separated_fact_from_assumption: Any = False,
    explained_package_scope: Any = False,
    explained_installation_and_maintenance: Any = False,
    avoided_financial_guarantee: Any = False,
    explained_client_portal: Any = False,
    asked_for_next_step: Any = False,
) -> dict[str, Any]:
    checks = {
        "problem_first": explained_problem_before_technology is True,
        "truth_boundary": separated_fact_from_assumption is True,
        "package_scope": explained_package_scope is True,
        "delivery_model": explained_installation_and_maintenance is True,
        "no_financial_guarantee": avoided_financial_guarantee is True,
        "client_portal": explained_client_portal is True,
        "next_step": asked_for_next_step is True,
    }
    completed = sum(1 for value in checks.values() if value)
    total = len(checks)
    pct = round(completed / total * 100, 1)
    return {
        "schema": SCHEMA,
        "mode": "SELF_ASSESSMENT",
        "completed": completed,
        "total": total,
        "progress_pct": pct,
        "checks": checks,
        "training_complete": completed == total,
        "authorizes_sales": False,
        "authorizes_runtime": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "VERSION",
    "SCENARIOS",
    "TRAINING_FLOW",
    "OBJECTIONS",
    "PACKAGE_RULES",
    "scenario_catalog",
    "training_session",
    "diagnostic_brief",
    "package_fit",
    "delivery_walkthrough",
    "objection_catalog",
    "objection_answer",
    "simulated_sales_conversation",
    "training_scorecard",
]
