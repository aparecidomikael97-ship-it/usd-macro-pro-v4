"""AtlasQuant Academy V1 — structured in-app learning.

Educational/presentation-only. This module never changes scores, gates, weights,
provider calls, branch state or trading permissions.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence
import re
import json
import streamlit as st

SCHEMA="ATLASQUANT_ACADEMY_V1"

ACADEMY_TOPICS=(
    {
        "id":"macro-foundations","category":"Macroeconomia","title":"Fundamentos de macro para Forex","level":"Iniciante",
        "summary":"Leia crescimento, inflação, emprego e juros como partes do mesmo ciclo econômico.",
        "watch":"Compare direção e surpresa dos dados, não um indicador isolado.",
        "forex":"Economia mais forte e política monetária relativamente mais apertada tendem a sustentar a moeda.",
        "pitfall":"Transformar uma regra geral em certeza de movimento imediato.",
    },
    {
        "id":"inflation","category":"Macroeconomia","title":"Inflação","level":"Iniciante",
        "summary":"Inflação mede a velocidade de aumento dos preços; persistência importa tanto quanto o número cheio.",
        "watch":"Tendência, núcleo, consenso e reação do banco central.",
        "forex":"Inflação resistente pode adiar cortes ou elevar expectativa de juros, afetando a moeda.",
        "pitfall":"Assumir que inflação alta sempre fortalece a moeda sem olhar crescimento e reação do BC.",
    },
    {
        "id":"cpi","category":"Indicadores","title":"CPI / IPC e Core CPI","level":"Iniciante",
        "summary":"CPI mede preços ao consumidor; o núcleo reduz itens mais voláteis para mostrar persistência.",
        "watch":"Atual x consenso x anterior, mensal e anual, com atenção ao Core CPI.",
        "forex":"Surpresa inflacionária muda expectativas de juros e pode mover USD rapidamente.",
        "pitfall":"Olhar só o headline e ignorar núcleo ou revisões.",
    },
    {
        "id":"pce","category":"Indicadores","title":"PCE e Core PCE","level":"Intermediário",
        "summary":"Medidas de inflação de consumo acompanhadas de perto pelo Federal Reserve.",
        "watch":"Core PCE, tendência anual e compatibilidade com a meta do Fed.",
        "forex":"Leitura persistente pode alterar o caminho esperado dos juros americanos.",
        "pitfall":"Tratar PCE como repetição sem importância do CPI.",
    },
    {
        "id":"ppi","category":"Indicadores","title":"PPI / IPP","level":"Intermediário",
        "summary":"Mede preços recebidos por produtores e ajuda a observar pressões de custos.",
        "watch":"Componentes, tendência e se a pressão chega ao consumidor.",
        "forex":"Pode reforçar ou contrariar a narrativa de inflação e juros.",
        "pitfall":"Usar PPI sozinho como sinal direcional definitivo.",
    },
    {
        "id":"nfp","category":"Indicadores","title":"Payroll / NFP","level":"Iniciante",
        "summary":"Mostra a variação do emprego não agrícola nos EUA.",
        "watch":"Payroll, desemprego, salários e revisões em conjunto.",
        "forex":"Mercado de trabalho resistente pode manter o Fed mais cauteloso com cortes.",
        "pitfall":"Operar apenas pelo número de empregos e ignorar salários/revisões.",
    },
    {
        "id":"unemployment-wages","category":"Indicadores","title":"Desemprego e salários","level":"Intermediário",
        "summary":"Desemprego mostra folga no trabalho; salários ajudam a medir pressão de renda e inflação.",
        "watch":"Taxa de desemprego, participação e Average Hourly Earnings.",
        "forex":"Combinação forte ou fraca altera a leitura do ciclo e expectativas do BC.",
        "pitfall":"Interpretar pequenas variações sem contexto da tendência.",
    },
    {
        "id":"pmi-ism","category":"Indicadores","title":"PMI / ISM","level":"Iniciante",
        "summary":"Pesquisas rápidas de atividade empresarial em manufatura e serviços.",
        "watch":"Nível 50, direção, novos pedidos, emprego e preços pagos.",
        "forex":"Mudanças de atividade podem antecipar revisões de crescimento e política monetária.",
        "pitfall":"Achar que acima de 50 significa automaticamente moeda forte.",
    },
    {
        "id":"gdp","category":"Indicadores","title":"PIB / GDP","level":"Iniciante",
        "summary":"Mede a produção agregada da economia e ajuda a classificar expansão ou desaceleração.",
        "watch":"Trimestre, anualização, composição e revisões.",
        "forex":"Crescimento relativo forte pode sustentar juros e fluxos para a moeda.",
        "pitfall":"Ignorar que PIB é atrasado e frequentemente revisado.",
    },
    {
        "id":"central-banks","category":"Bancos centrais","title":"Bancos centrais e juros","level":"Iniciante",
        "summary":"Fed, ECB, BoE, BoJ e outros G8 influenciam moedas pela política monetária.",
        "watch":"Taxa atual, guidance, projeções, votação, coletiva e balanço.",
        "forex":"O diferencial esperado de juros entre duas moedas é central para muitos movimentos de FX.",
        "pitfall":"Comparar apenas a taxa atual e ignorar a trajetória esperada.",
    },
    {
        "id":"hawkish-dovish","category":"Bancos centrais","title":"Hawkish x Dovish","level":"Iniciante",
        "summary":"Hawkish indica maior preocupação com inflação; dovish, maior tolerância a política mais frouxa.",
        "watch":"Mudanças de linguagem em comunicado, ata e coletiva.",
        "forex":"Mudança de tom pode mover a curva de juros antes da taxa oficial mudar.",
        "pitfall":"Classificar uma fala por uma frase isolada.",
    },
    {
        "id":"fomc-dotplot","category":"Bancos centrais","title":"FOMC, projeções e dot plot","level":"Intermediário",
        "summary":"O FOMC define a política do Fed; projeções ajudam a mapear o caminho esperado dos juros.",
        "watch":"Decisão, statement, SEP/dot plot e coletiva do presidente do Fed.",
        "forex":"Reprecificação da trajetória de juros altera Treasury yields e USD.",
        "pitfall":"Tratar o dot plot como promessa fixa.",
    },
    {
        "id":"calendar-surprise","category":"Execução macro","title":"Calendário e surpresa econômica","level":"Iniciante",
        "summary":"A reação depende muito da diferença entre o publicado e o que o mercado esperava.",
        "watch":"Atual, consenso, anterior/revisado, importância e horário.",
        "forex":"Surpresa relevante pode mudar narrativa, volatilidade e diferencial de moedas.",
        "pitfall":"Comparar atual somente com o anterior e esquecer o consenso.",
    },
    {
        "id":"dxy-crossasset","category":"Intermarket","title":"DXY, yields e cross-asset","level":"Intermediário",
        "summary":"DXY, Treasury yields, ações, ouro e risco ajudam a conferir a narrativa do USD.",
        "watch":"2Y/10Y, DXY, equities, ouro e correlações que podem mudar por regime.",
        "forex":"Confirmações intermarket aumentam contexto; divergências pedem cautela.",
        "pitfall":"Assumir correlação fixa em todos os regimes.",
    },
    {
        "id":"relative-strength","category":"Forex","title":"Força relativa das 8 moedas","level":"Iniciante",
        "summary":"Forex é comparação: importa qual moeda está relativamente mais forte ou fraca.",
        "watch":"USD, EUR, GBP, JPY, CHF, CAD, AUD e NZD em uma escala consistente.",
        "forex":"Combinar forte x fraca tende a produzir contexto mais limpo que pares equilibrados.",
        "pitfall":"Confundir score relativo com probabilidade de lucro.",
    },
    {
        "id":"liquidity-structure","category":"ICT / SMC","title":"Liquidez, BOS e CHOCH","level":"Intermediário",
        "summary":"Estrutura organiza continuidade/mudança; liquidez ajuda a mapear onde ordens podem estar concentradas.",
        "watch":"Swing highs/lows, sweep, deslocamento e confirmação de estrutura.",
        "forex":"Serve como camada de timing depois do contexto macro e dos gates.",
        "pitfall":"Usar um BOS isolado contra contexto maior.",
    },
    {
        "id":"fvg","category":"ICT / SMC","title":"FVG e displacement","level":"Intermediário",
        "summary":"FVG representa desequilíbrio de preço após deslocamento rápido.",
        "watch":"Qualidade do displacement, posição no range e confluência com liquidez/estrutura.",
        "forex":"Pode ajudar a planejar uma zona de retorno, não a direção macro.",
        "pitfall":"Marcar todo gap como FVG operacional.",
    },
    {
        "id":"ote","category":"ICT / SMC","title":"OTE","level":"Intermediário",
        "summary":"OTE é uma zona de retração usada como referência de entrada dentro de um contexto já definido.",
        "watch":"Swing válido, direção HTF e confirmação no timeframe de execução.",
        "forex":"Ajuda no timing e relação risco/retorno quando o contexto permanece válido.",
        "pitfall":"Forçar Fibonacci em swings sem estrutura.",
    },
    {
        "id":"crt-amd","category":"ICT / SMC","title":"CRT e AMD","level":"Avançado",
        "summary":"CRT e AMD organizam fases de range, manipulação e expansão como modelos de contexto/timing.",
        "watch":"Range definido, sweep/manipulação, deslocamento e alvo de liquidez.",
        "forex":"Podem complementar o modelo técnico sem substituir macro ou gestão de risco.",
        "pitfall":"Enxergar o padrão depois do fato e assumir que sempre se repetirá.",
    },
    {
        "id":"technical-to-liquidity","category":"Fundamentos técnicos","title":"Do suporte/resistência para liquidez","level":"Iniciante",
        "summary":"Suportes, resistências e pullbacks continuam úteis, mas podem ser relidos como regiões onde ordens e stops se concentram.",
        "watch":"Topos/fundos repetidos, máximas/mínimas anteriores, reação após varredura e mudança de estrutura.",
        "forex":"A ponte ajuda quem vem da análise técnica tradicional a entender por que o preço às vezes rompe uma região antes de reagir.",
        "pitfall":"Achar que toda resistência será manipulada ou que toda varredura garante reversão.",
    },
    {
        "id":"liquidity-sweeps","category":"ICT / SMC","title":"Liquidez e varredura (sweep)","level":"Iniciante",
        "summary":"Liquidez costuma se concentrar perto de extremos visíveis; um sweep é a passagem pelo extremo seguida de avaliação da resposta do preço.",
        "watch":"PDH/PDL, PWH/PWL, Asia High/Low, equal highs/lows, deslocamento e confirmação posterior.",
        "forex":"Ajuda a localizar zonas onde o preço pode buscar ordens antes de continuar ou reverter.",
        "pitfall":"Entrar contra o movimento apenas porque uma máxima ou mínima foi tocada.",
    },
    {
        "id":"bos-choch-mss","category":"ICT / SMC","title":"BOS, CHOCH e MSS","level":"Intermediário",
        "summary":"BOS descreve continuidade estrutural; CHOCH/MSS ajudam a observar possível mudança depois de liquidez e deslocamento.",
        "watch":"Swing realmente confirmado, fechamento além do nível, displacement e contexto do timeframe maior.",
        "forex":"Serve como confirmação de estrutura para timing; não substitui o viés macro ou os gates.",
        "pitfall":"Chamar qualquer rompimento pequeno de mudança estrutural válida.",
    },
    {
        "id":"order-block","category":"ICT / SMC","title":"Order Block","level":"Intermediário",
        "summary":"Order Block é uma zona de origem associada a deslocamento/estrutura; precisa de contexto e validação, não apenas da última vela contrária.",
        "watch":"Liquidez anterior, displacement, quebra/mudança estrutural, posição no dealing range e reação posterior.",
        "forex":"Pode ajudar a planejar região de interesse depois que direção e risco já estão definidos.",
        "pitfall":"Marcar toda vela contrária como Order Block e ignorar invalidação.",
    },
    {
        "id":"breaker-mitigation","category":"ICT / SMC","title":"Breaker e Mitigation Block","level":"Avançado",
        "summary":"Breaker reaproveita uma zona que falhou e mudou de função; mitigation busca retorno a uma origem relevante para reequilíbrio/mitigação.",
        "watch":"Zona original, falha/invalidação, deslocamento, mudança estrutural e teste posterior.",
        "forex":"São PD Arrays avançados para contexto/timing e exigem leitura clara da estrutura.",
        "pitfall":"Renomear qualquer suporte/resistência rompido como Breaker sem sequência estrutural.",
    },
    {
        "id":"sessions-killzones","category":"ICT / SMC","title":"Sessões, Killzones e liquidez","level":"Iniciante",
        "summary":"Ásia, Londres e Nova York criam ranges, extremos e janelas de liquidez que podem organizar o timing do dia.",
        "watch":"Asia High/Low, abertura de Londres, New York AM/PM, sweep do range e evento macro próximo.",
        "forex":"Ajuda a contextualizar quando um sweep/MSS ocorre e evita tratar todos os horários como iguais.",
        "pitfall":"Usar horário de sessão como sinal sem estrutura, dados frescos ou contexto macro.",
    },
    {
        "id":"volume-profile","category":"Volume / contexto","title":"Volume Profile no Forex","level":"Avançado",
        "summary":"Volume Profile organiza atividade por faixa de preço, mas em Forex spot a fonte de volume não representa um livro centralizado de todo o mercado.",
        "watch":"Fonte do dado, POC, Value Area, HVN/LVN e relação com estrutura/liquidez.",
        "forex":"Pode complementar contexto e zonas de aceitação/rejeição quando a metodologia da fonte é documentada.",
        "pitfall":"Apresentar tick volume ou volume de um provedor como volume consolidado de todo o Forex.",
    },
    {
        "id":"vwap-opening-range","category":"Execução técnica","title":"VWAP e Opening Range","level":"Intermediário",
        "summary":"VWAP e Opening Range podem funcionar como referências objetivas de localização e comportamento intradiário.",
        "watch":"Fonte do preço/volume, janela da abertura, aceitação/rejeição e confluência com sessão/estrutura.",
        "forex":"São candidatos de pesquisa para setups simples, mas precisam de backtest e Forward/Paper separados.",
        "pitfall":"Otimizar janela ou regra depois de olhar o resultado e chamar isso de validação.",
    },
    {
        "id":"risk","category":"Gestão","title":"Risco e NÃO OPERAR","level":"Iniciante",
        "summary":"Preservar capital faz parte do sistema; ficar fora é uma decisão válida.",
        "watch":"Dados stale, eventos próximos, conflito de regime, hard/soft blocks e drawdown.",
        "forex":"O melhor setup é descartado quando integridade, risco ou confirmação não passam.",
        "pitfall":"Confundir alta prioridade com obrigação de entrar.",
    },
    {
        "id":"atlasquant-reading","category":"AtlasQuant","title":"Como ler o AtlasQuant","level":"Iniciante",
        "summary":"Comece pelo Radar de Oportunidades, depois leia motivo, dados, Safety Core, timing e invalidação.",
        "watch":"Radar, modo Iniciante/Avançado, Data Confidence, Safety Core, M15, Gate, contexto e plano operacional.",
        "forex":"A interface resume camadas já calculadas; ela não transforma score em certeza.",
        "pitfall":"Pular diretamente para BUY/SELL sem ler bloqueios e qualidade.",
    },
)


def _norm(value: object)->str:
    return re.sub(r"\s+"," ",str(value or "").strip()).casefold()


def academy_catalog(category: str | None = None, level: str | None = None)->list[dict[str,str]]:
    rows=[dict(x) for x in ACADEMY_TOPICS]
    if category:
        key=_norm(category)
        rows=[x for x in rows if _norm(x.get("category"))==key]
    if level:
        key=_norm(level)
        rows=[x for x in rows if _norm(x.get("level"))==key]
    return rows


def academy_search(query: object)->list[dict[str,str]]:
    q=_norm(query)
    if not q:
        return academy_catalog()
    return [
        dict(x) for x in ACADEMY_TOPICS
        if q in _norm(" ".join(str(x.get(k,"")) for k in ("id","category","title","summary","watch","forex","pitfall")))
    ]


def academy_topic(topic_id: object)->dict[str,str] | None:
    key=_norm(topic_id)
    return next((dict(x) for x in ACADEMY_TOPICS if _norm(x.get("id"))==key),None)


def academy_progress(completed_ids: Sequence[object] | None)->dict[str,Any]:
    valid={str(x["id"]) for x in ACADEMY_TOPICS}
    done={str(x).strip() for x in (completed_ids or []) if str(x).strip() in valid}
    total=len(valid)
    return {
        "completed":len(done),
        "total":total,
        "pct":round((len(done)/total*100.0) if total else 0.0,1),
        "completed_ids":tuple(sorted(done)),
    }


def academy_minimum_text_ready()->bool:
    required={
        "macro-foundations","inflation","cpi","pce","ppi","nfp","unemployment-wages",
        "pmi-ism","gdp","central-banks","hawkish-dovish","fomc-dotplot",
        "calendar-surprise","dxy-crossasset","relative-strength","liquidity-structure",
        "fvg","ote","crt-amd","technical-to-liquidity","liquidity-sweeps",
        "bos-choch-mss","order-block","breaker-mitigation","sessions-killzones",
        "volume-profile","vwap-opening-range","risk","atlasquant-reading",
    }
    ids={str(x["id"]) for x in ACADEMY_TOPICS}
    return required.issubset(ids) and len(ids)==len(ACADEMY_TOPICS)


def render_academy_panel()->dict[str,Any]:
    st.markdown("### 🎓 AtlasQuant Academy")
    st.caption("Trilha educativa dentro do app. Conteúdo não altera scores, gates ou decisões do motor.")

    categories=sorted({str(x["category"]) for x in ACADEMY_TOPICS})
    levels=["Todos","Iniciante","Intermediário","Avançado"]
    c1,c2=st.columns(2)
    with c1:
        category=st.selectbox("Tema",["Todos",*categories],key="aq_academy_category")
    with c2:
        level=st.selectbox("Nível",levels,key="aq_academy_level")

    query=st.text_input("Buscar aula",placeholder="Ex.: CPI, Fed, liquidez, risco",key="aq_academy_query")
    rows=academy_search(query)
    if category!="Todos":
        rows=[x for x in rows if x["category"]==category]
    if level!="Todos":
        rows=[x for x in rows if x["level"]==level]

    completed=list(st.session_state.get("aq_academy_completed",[]))
    progress=academy_progress(completed)
    st.progress(progress["pct"]/100.0,text=f"Progresso nesta sessão: {progress['completed']}/{progress['total']} aulas")

    if not rows:
        st.info("Nenhuma aula encontrada com estes filtros.")
        return {"visible":0,**progress,"text_ready":academy_minimum_text_ready()}

    labels={f"{x['title']} · {x['level']}":x for x in rows}
    chosen=st.selectbox("Aula",list(labels),key="aq_academy_topic")
    item=labels[chosen]

    st.markdown(
        f"""<div class="ux-card">
        <div class="ux-accent">📘 {item['title']}</div>
        <p><b>Resumo:</b> {item['summary']}</p>
        <p><b>O que observar:</b> {item['watch']}</p>
        <p><b>Ligação com Forex:</b> {item['forex']}</p>
        <p><b>Erro comum:</b> {item['pitfall']}</p>
        </div>""",
        unsafe_allow_html=True,
    )

    from atlasquant_academy_visuals import render_concept_visual
    if render_concept_visual(item["id"]):
        st.caption("Animação didática local · sem chamada externa e sem efeito no motor.")

    done=item["id"] in set(progress["completed_ids"])
    if st.checkbox("Marcar esta aula como concluída",value=done,key=f"aq_academy_done_{item['id']}"):
        if not done:
            completed.append(item["id"])
    else:
        completed=[x for x in completed if x!=item["id"]]
    st.session_state["aq_academy_completed"]=list(dict.fromkeys(completed))

    from atlasquant_academy_media import academy_video_script
    from atlasquant_academy_video_blueprints import video_blueprint
    media=academy_video_script(item["id"])
    blueprint=video_blueprint(item["id"])
    if media:
        with st.expander("🎬 Roteiro do vídeo curto",expanded=False):
            st.caption(f"Roteiro pronto · duração estimada: {media['estimated_seconds']}s · vídeo ainda não renderizado")
            for scene in media["scenes"]:
                st.markdown(f"**{scene['order']}. {scene['title']}** — {scene['text']}")
            st.download_button(
                "Baixar roteiro do vídeo",
                data=media["narration"],
                file_name=f"atlasquant_academy_{item['id']}_roteiro.txt",
                mime="text/plain",
                key=f"aq_academy_video_script_{item['id']}",
            )
    if blueprint:
        with st.expander("🎞 Storyboard animado detalhado",expanded=False):
            mins=max(1,round(float(blueprint["total_seconds"])/60.0))
            st.caption(f"Plano didático · ~{mins} min · limite máximo 20 min · vídeo ainda não renderizado")
            st.markdown(f"**Gancho:** {blueprint['hook']}")
            for scene in blueprint["scenes"]:
                st.markdown(
                    f"**{scene['order']}. {scene['title']} · {scene['seconds']}s**  \\n"
                    f"🎨 {scene['visual']}  \\n"
                    f"🎓 {scene['teaching']}"
                )
            st.download_button(
                "Baixar storyboard JSON",
                data=json.dumps(blueprint,ensure_ascii=False,indent=2),
                file_name=f"atlasquant_{item['id']}_storyboard.json",
                mime="application/json",
                key=f"aq_academy_storyboard_{item['id']}",
            )
    st.info("Roteiros e storyboards estão preparados; renderização/publicação da mídia continua como etapa externa separada.")
    return {"visible":len(rows),**academy_progress(completed),"text_ready":academy_minimum_text_ready()}


__all__=[
    "SCHEMA","ACADEMY_TOPICS","academy_catalog","academy_search","academy_topic",
    "academy_progress","academy_minimum_text_ready","render_academy_panel",
]
