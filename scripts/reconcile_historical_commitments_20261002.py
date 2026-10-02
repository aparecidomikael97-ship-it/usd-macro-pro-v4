from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "docs/continuidade/aion_historical_commitments_2026-10-02.json"
STATE_IMPL = "IMPLEMENTADO / EM VALIDAÇÃO"
STATE_DEP = "DEPENDÊNCIA EXTERNA"

EVIDENCE_BY_DAY = {
    "2026-09-17": "docs/continuidade/HISTORICAL_EVIDENCE_2026-09-17.md",
    "2026-09-28": "docs/continuidade/HISTORICAL_EVIDENCE_2026-09-28.md",
    "2026-09-30": "docs/continuidade/HISTORICAL_EVIDENCE_2026-09-30.md",
    "2026-10-01": "docs/continuidade/HISTORICAL_EVIDENCE_2026-10-01.md",
}

ADDITIONS = [
    {
        "id": "D-2026-09-17-AUTOPILOT-PAPER-V116",
        "title": "Autopilot e Paper Trading V11.6 com fricção e auditoria",
        "state": STATE_IMPL,
        "domain": "trader",
        "source_date": "2026-09-17",
        "summary": "Preservar V11.1–V11.6: quota saver, Paper Trading checklist-gated, auditoria, derivação M15/H1/H4 e custos spread/slippage; sem ordem real.",
        "evidence": [EVIDENCE_BY_DAY["2026-09-17"]],
        "implemented": True,
        "validated": False,
    },
    {
        "id": "D-2026-09-17-TWELVE-DATA-PROD-SMOKE-BLOCK",
        "title": "Twelve Data e smoke de produção como bloqueios externos",
        "state": STATE_DEP,
        "domain": "data-runtime",
        "source_date": "2026-09-17",
        "summary": "Limite da Twelve Data e instabilidade/smoke de produção impedem tratar o runtime daquele dia como validação irrestrita.",
        "evidence": [EVIDENCE_BY_DAY["2026-09-17"]],
        "implemented": False,
        "validated": False,
    },
    {
        "id": "D-2026-09-17-PRIVATE-WINDOWS-BACKUP-FLOW",
        "title": "Fluxo privado Windows com backup antes de desenvolvimento",
        "state": "APROVADO / PENDENTE",
        "domain": "distribution",
        "source_date": "2026-09-17",
        "summary": "Manter estável → backup → desenvolvimento → testes → nova versão, preservando fonte, dados, pacote estável e histórico.",
        "evidence": [EVIDENCE_BY_DAY["2026-09-17"]],
        "implemented": False,
        "validated": False,
    },
    {
        "id": "D-2026-09-28-FOREX28-RADAR-LAB-FOUNDATION",
        "title": "Radar Forex 28 pares e Laboratório com evidência real",
        "state": STATE_IMPL,
        "domain": "trader",
        "source_date": "2026-09-28",
        "summary": "Preservar Radar 28 pares/TOP 10 e Laboratório/Replay com evidência real e no-lookahead.",
        "evidence": [EVIDENCE_BY_DAY["2026-09-28"]],
        "implemented": True,
        "validated": False,
    },
    {
        "id": "D-2026-09-28-AION-ADMIN-REPLAY-HEALTH-GOVERNANCE",
        "title": "Admin Copilot, Replay, Health, Freshness e release governado",
        "state": STATE_IMPL,
        "domain": "aion-core",
        "source_date": "2026-09-28",
        "summary": "Preservar Admin Copilot/onboarding, Replay point-in-time, Data Confidence/Freshness, System Health, Cost Center e release em estágios com gates fail-closed.",
        "evidence": [EVIDENCE_BY_DAY["2026-09-28"]],
        "implemented": True,
        "validated": False,
    },
    {
        "id": "D-2026-09-28-BUSINESS-TOPLEVEL-INTERFACE",
        "title": "AION Business e navegação premium como áreas integradas",
        "state": STATE_IMPL,
        "domain": "interface",
        "source_date": "2026-09-28",
        "summary": "Preservar Negócios como área de alto nível e os reparos de navegação/Painel Mestre/Radar sem criar autoridade autônoma.",
        "evidence": [EVIDENCE_BY_DAY["2026-09-28"]],
        "implemented": True,
        "validated": False,
    },
    {
        "id": "D-2026-10-01-NIGHTSHIFT-V1-RECOVERY",
        "title": "AION Core Nightshift V1 recuperado e integrado",
        "state": STATE_IMPL,
        "domain": "aion-core",
        "source_date": "2026-10-01",
        "summary": "Preservar recuperação Nightshift, bridge de runtime e cobertura de testes como base do endurecimento posterior do Core.",
        "evidence": [EVIDENCE_BY_DAY["2026-10-01"]],
        "implemented": True,
        "validated": False,
    },
    {
        "id": "D-2026-10-01-LIBRARY-FOUNDATION-INDEX-PDF",
        "title": "Biblioteca AION: Foundation, Index e PDF Ingestion",
        "state": STATE_IMPL,
        "domain": "library",
        "source_date": "2026-10-01",
        "summary": "Preservar Foundation, Index e PDF local com proveniência, quarentena, revisão explícita e isolamento tenant/workspace; sem OCR ou promoção automática.",
        "evidence": [EVIDENCE_BY_DAY["2026-10-01"]],
        "implemented": True,
        "validated": False,
    },
    {
        "id": "D-2026-10-01-LIBRARY-IDENTITY-ACL-DR-BLOCKERS",
        "title": "Identidade durável, ACL e DR continuam bloqueios reais",
        "state": STATE_DEP,
        "domain": "security",
        "source_date": "2026-10-01",
        "summary": "Sandboxes PostgreSQL/browser não substituem identidade durável, revogação autoritativa, witness externo, tombstone e DR independente.",
        "evidence": [EVIDENCE_BY_DAY["2026-10-01"]],
        "implemented": False,
        "validated": False,
    },
]


def _cell(value: object) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", " ")


def _render_narrative(data: dict[str, object]) -> None:
    commitments = list(data.get("commitments") or [])
    coverage = list(data.get("daily_coverage") or [])
    counts: dict[str, int] = {}
    for item in commitments:
        state = str(item.get("state") or "UNKNOWN")
        counts[state] = counts.get(state, 0) + 1
    uncovered = [row["date"] for row in coverage if row.get("state") != "COVERED_WITH_EVIDENCE"]
    lines = [
        "# AION — Reconciliação Histórica de Compromissos (15/09–02/10/2026)",
        "",
        "Este documento é gerado a partir do registro canônico `aion_historical_commitments_2026-10-02.json` e complementa, sem apagar, checkpoints anteriores.",
        "",
        "**Regra permanente:** aprovação não equivale a implementação; implementação não equivale a validação. Nada aqui concede autoridade para merge, deploy, gasto, publicação, persistência de produção ou trading real.",
        "",
        "## Resumo",
        "",
        f"- Compromissos rastreados: **{len(commitments)}**.",
        f"- Dias na janela: **{len(coverage)}**.",
        f"- Dias ainda exigindo varredura: **{', '.join(uncovered) if uncovered else 'nenhum'}**.",
        f"- Lacunas herdadas da reconciliação de 29/09: **{len(data.get('inherited_gaps') or [])}**.",
        "",
        "### Estados",
        "",
    ]
    lines += [f"- {state}: {counts[state]}" for state in sorted(counts)]
    lines += ["", "## Cobertura diária", "", "| Data | Cobertura | Compromissos | Fechado |", "|---|---|---:|---|"]
    for row in coverage:
        lines.append(f"| {_cell(row.get('date'))} | {_cell(row.get('state'))} | {len(row.get('commitment_ids') or [])} | {'SIM' if row.get('closed') else 'NÃO'} |")
    lines += ["", "> Cobertura com evidência não fecha automaticamente um dia; fechamento exige estados terminais e evidência explícita.", "", "## Compromissos", "", "| Data | ID | Estado | Área | Compromisso |", "|---|---|---|---|---|"]
    for item in sorted(commitments, key=lambda x: (str(x.get("source_date") or ""), str(x.get("id") or ""))):
        lines.append(f"| {_cell(item.get('source_date'))} | `{_cell(item.get('id'))}` | {_cell(item.get('state'))} | {_cell(item.get('domain'))} | {_cell(item.get('title'))} |")
    lines += ["", "## Lacunas herdadas", ""]
    for gap in data.get("inherited_gaps") or []:
        topic = _cell(gap.get("topic") or gap.get("title") or gap.get("summary") or "Lacuna herdada")
        reason = _cell(gap.get("reason"))
        suffix = f" — {reason}" if reason else ""
        lines.append(f"- **{_cell(gap.get('id'))}** — {_cell(gap.get('state'))}: {topic}{suffix}")
    lines += ["", "## Segurança e precedência", "", "- Requisitos antigos não são apagados quando uma decisão nova os substitui.", "- Pendências de Trader e Investimentos continuam rastreadas mesmo com Núcleo, Interface e Negócios priorizados.", "- Os oito papéis internos pertencem ao mesmo AION Core; não são oito IAs independentes.", "- Biblioteca não promove conhecimento automaticamente e preserva conflito, quarentena e rejeição para auditoria.", "- Produção tenant, trading real, merge e deploy continuam sujeitos aos gates e autorizações explícitas.", ""]
    (ROOT / "docs/continuidade/AION_HISTORICAL_COMMITMENTS_2026-10-02.md").write_text("\n".join(lines), encoding="utf-8")


def reconcile() -> dict[str, object]:
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    existing = {item.get("id") for item in data.get("commitments", [])}
    for item in ADDITIONS:
        if item["id"] not in existing:
            data["commitments"].append(item)
            existing.add(item["id"])

    for row in data.get("daily_coverage", []):
        day = row.get("date")
        if day in EVIDENCE_BY_DAY:
            row["state"] = "COVERED_WITH_EVIDENCE"
            refs = list(row.get("source_paths") or [])
            if EVIDENCE_BY_DAY[day] not in refs:
                refs.append(EVIDENCE_BY_DAY[day])
            row["source_paths"] = refs
            row["closed"] = False

    ids_by_day = {}
    for item in data.get("commitments", []):
        ids_by_day.setdefault(item.get("source_date"), []).append(item.get("id"))
    for row in data.get("daily_coverage", []):
        row["commitment_ids"] = sorted(
            item_id for item_id in ids_by_day.get(row.get("date"), []) if item_id
        )

    uncovered = [
        row.get("date")
        for row in data.get("daily_coverage", [])
        if row.get("state") != "COVERED_WITH_EVIDENCE"
    ]
    data["reconciliation_status"] = {
        "as_of": "2026-10-02",
        "coverage_complete_for_period": not uncovered,
        "historical_days_auto_closed": False,
        "rule": "Coverage evidence does not close commitments; terminal state still requires explicit evidence.",
    }
    MANIFEST.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _render_narrative(data)
    return {"commitments": len(data["commitments"]), "uncovered_days": uncovered}


if __name__ == "__main__":
    print(json.dumps(reconcile(), ensure_ascii=False))
