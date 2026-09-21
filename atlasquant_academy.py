"""AtlasQuant Academy V1 — structured in-app learning.

Educational/presentation-only. This module never changes scores, gates, weights,
provider calls, branch state or trading permissions.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence
import re
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
        "id":"microeconomics-markets","category":"Macroeconomia","title":"Microeconomia aplicada ao mercado","level":"Intermediário",
        "summary":"Microeconomia ajuda a entender decisões de empresas e consumidores, custos, margens, oferta, demanda e transmissão de preços.",
        "watch":"Oferta e demanda, elasticidade, custos, estoques, margens e como choques setoriais podem aparecer em inflação e atividade.",
        "forex":"Ela complementa a macro: ajuda a explicar por que um choque de energia, crédito ou consumo pode mudar inflação, crescimento e expectativas de juros.",
        "pitfall":"Tentar transformar um dado de uma empresa ou setor em direção automática para uma moeda inteira.",
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
        "id":"g8-central-banks","category":"Bancos centrais","title":"ECB, BoE, BoJ e bancos centrais do G8","level":"Intermediário",
        "summary":"Além do Fed, ECB, BoE, BoJ, BoC, RBA, RBNZ e SNB moldam o valor relativo das principais moedas.",
        "watch":"Decisão, guidance, inflação doméstica, crescimento, mercado de trabalho, votação e diferenças de trajetória entre bancos centrais.",
        "forex":"EUR, GBP, JPY, CAD, AUD, NZD e CHF reagem ao que muda na política esperada de seu banco central em comparação com o outro lado do par.",
        "pitfall":"Analisar uma moeda só pelo Fed e ignorar o banco central da moeda base ou cotada.",
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
        "id":"geopolitics-fx","category":"Intermarket","title":"Geopolítica aplicada ao Forex","level":"Intermediário",
        "summary":"Conflitos, sanções, eleições, comércio e energia podem alterar risco, inflação, crescimento e fluxos entre moedas.",
        "watch":"Fato confirmado, fonte, ativos diretamente expostos, energia/commodities, reação de yields e se o efeito é temporário ou muda a narrativa macro.",
        "forex":"O impacto depende do canal econômico e do regime; moedas de refúgio, commodities e países mais expostos podem reagir de formas diferentes.",
        "pitfall":"Operar manchete isolada, rumor ou rótulo político sem separar fato, transmissão econômica e reação já precificada.",
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
        "id":"quarterly-theory","category":"ICT / SMC","title":"Quarterly Theory — ciclos e quarters","level":"Avançado",
        "summary":"Quarterly Theory organiza o tempo em quatro partes para estudar repetição de fases e contexto; é uma lente de leitura, não uma previsão garantida.",
        "watch":"Defina primeiro o período-mãe (ano, mês, semana, dia ou sessão), divida-o em Q1–Q4 e observe contexto, liquidez, acumulação/manipulação/distribuição e transições entre quarters.",
        "forex":"Use os quarters para organizar timing e narrativa junto de HTF, liquidez, CRT/AMD e contexto macro; a divisão temporal não substitui confirmação nem gestão de risco.",
        "pitfall":"Forçar todo ciclo a repetir a mesma sequência ou assumir que Q1/Q2/Q3/Q4 determinam direção sozinhos.",
    },
    {
        "id":"quarterly-multitimeframe","category":"ICT / SMC","title":"Quarterly — anual, mensal, semanal e diário","level":"Avançado",
        "summary":"O mesmo raciocínio de quatro partes pode ser aplicado em escalas diferentes, mantendo cada leitura vinculada ao seu período-mãe.",
        "watch":"Comece no timeframe maior, marque o quarter atual e só depois desça para semana, dia e sessão procurando alinhamento, deslocamento e liquidez.",
        "forex":"A leitura top-down ajuda a separar contexto de execução: o quarter maior dá referência e o menor pode ajudar no timing.",
        "pitfall":"Misturar quarters de períodos diferentes sem hierarquia e chamar qualquer movimento de confirmação.",
    },
    {
        "id":"quarterly-amd","category":"ICT / SMC","title":"Quarterly + AMD / Power of Three","level":"Avançado",
        "summary":"Quarterly pode ser estudado junto de AMD/Power of Three para descrever fases de acumulação, manipulação e distribuição dentro de uma janela temporal.",
        "watch":"Procure range/acumulação, tomada de liquidez ou falso rompimento e depois deslocamento/expansão; aceite também ciclos incompletos ou fora de ordem.",
        "forex":"Quando contexto macro, estrutura e liquidez concordam, a leitura temporal pode ajudar a planejar onde esperar confirmação e onde invalidar a hipótese.",
        "pitfall":"Tratar AMD como roteiro obrigatório ou entrar antecipadamente apenas porque um novo quarter começou.",
    },
    {
        "id":"quarterly-execution","category":"ICT / SMC","title":"Quarterly — checklist de leitura","level":"Avançado",
        "summary":"Uma leitura disciplinada separa período, contexto, liquidez, confirmação, alvo e invalidação antes de considerar uma execução.",
        "watch":"1) período-mãe; 2) quarter atual; 3) bias HTF; 4) liquidez; 5) sweep/manipulação; 6) displacement/BOS-CHOCH; 7) FVG/OTE; 8) alvo e invalidação.",
        "forex":"Use o checklist como filtro educacional e de timing; decisões continuam sujeitas ao Safety Core, dados válidos, risco e gates do AtlasQuant.",
        "pitfall":"Transformar o checklist em sinal automático ou ignorar notícias de alto impacto, dados stale e limites de risco.",
    },
    {
        "id":"crt-amd","category":"ICT / SMC","title":"CRT e AMD","level":"Avançado",
        "summary":"CRT e AMD organizam fases de range, manipulação e expansão como modelos de contexto/timing.",
        "watch":"Range definido, sweep/manipulação, deslocamento e alvo de liquidez.",
        "forex":"Podem complementar o modelo técnico sem substituir macro ou gestão de risco.",
        "pitfall":"Enxergar o padrão depois do fato e assumir que sempre se repetirá.",
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
        "summary":"Leia estado primeiro, depois motivo, dados, Safety Core, timing e invalidação.",
        "watch":"Central, Data Confidence, Safety Core, M15, Gate, contexto e plano operacional.",
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


ACADEMY_REQUIRED_TOPIC_IDS=frozenset({
    "macro-foundations","microeconomics-markets","inflation","cpi","pce","ppi",
    "nfp","unemployment-wages","pmi-ism","gdp","central-banks","g8-central-banks",
    "hawkish-dovish","fomc-dotplot","calendar-surprise","dxy-crossasset",
    "geopolitics-fx","relative-strength","liquidity-structure","fvg","ote",
    "quarterly-theory","quarterly-multitimeframe","quarterly-amd",
    "quarterly-execution","crt-amd","risk","atlasquant-reading",
})


def academy_coverage_report()->dict[str,Any]:
    ids=[str(x["id"]) for x in ACADEMY_TOPICS]
    unique=set(ids)
    missing=sorted(ACADEMY_REQUIRED_TOPIC_IDS-unique)
    duplicate_count=len(ids)-len(unique)
    media_ready=False
    try:
        # Local import avoids a module cycle during Academy startup.
        from atlasquant_academy_media import academy_video_scripts_ready
        media_ready=bool(academy_video_scripts_ready())
    except Exception:
        media_ready=False
    return {
        "schema":"ATLASQUANT_ACADEMY_COVERAGE_V1",
        "topics":len(ids),
        "unique_topics":len(unique),
        "required_topics":len(ACADEMY_REQUIRED_TOPIC_IDS),
        "missing_required":missing,
        "duplicate_ids":duplicate_count,
        "text_ready":not missing and duplicate_count==0,
        "video_scripts_ready":media_ready,
        "rendered_media_required_externally":True,
        "trading_side_effects":False,
    }


def academy_minimum_text_ready()->bool:
    report=academy_coverage_report()
    return bool(report["text_ready"])


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

    done=item["id"] in set(progress["completed_ids"])
    if st.checkbox("Marcar esta aula como concluída",value=done,key=f"aq_academy_done_{item['id']}"):
        if not done:
            completed.append(item["id"])
    else:
        completed=[x for x in completed if x!=item["id"]]
    st.session_state["aq_academy_completed"]=list(dict.fromkeys(completed))

    from atlasquant_academy_media import academy_video_script
    media=academy_video_script(item["id"])
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
    coverage=academy_coverage_report()
    st.caption(
        f"Cobertura Academy: {coverage['unique_topics']} aulas · "
        f"{coverage['required_topics']} requisitos curriculares mínimos cobertos."
    )
    st.info("Roteiros dos vídeos estão preparados; renderização/publicação de mídia continua como etapa externa separada.")
    return {"visible":len(rows),**academy_progress(completed),"text_ready":academy_minimum_text_ready(),"coverage":coverage}


__all__=[
    "SCHEMA","ACADEMY_TOPICS","academy_catalog","academy_search","academy_topic",
    "academy_progress","ACADEMY_REQUIRED_TOPIC_IDS","academy_coverage_report",
    "academy_minimum_text_ready","render_academy_panel",
]
