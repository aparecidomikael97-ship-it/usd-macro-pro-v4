"""AtlasQuant Academy — trilhas educacionais integradas ao aplicativo.

Camada educacional: não altera motor de decisão, scores, Gate, scanner ou histórico.
Os roteiros de vídeo são originais e servem como base para produção das aulas.
"""
from __future__ import annotations

from typing import Any

import streamlit as st


ACADEMY_TRACKS: list[dict[str, Any]] = [
    {
        "id": "macro_forex",
        "titulo": "📈 Macro & Forex",
        "descricao": "Do ciclo econômico à leitura prática de moedas e pares.",
        "aulas": [
            {
                "id": "macro_01",
                "titulo": "1. Ciclo econômico e direção da moeda",
                "duracao": "12–15 min",
                "objetivo": "Entender como crescimento, inflação, juros e moeda se conectam.",
                "resumo": "O Forex reage ao que o mercado espera para crescimento, inflação e juros. A ideia central é comparar economias: qual banco central tende a apertar ou afrouxar mais?",
                "roteiro": [
                    "Explique PIB, inflação, emprego e juros como quatro peças do mesmo ciclo.",
                    "Mostre por que economia forte pode sustentar juros mais altos e favorecer a moeda.",
                    "Mostre o caminho inverso: atividade fraca → inflação cede → cortes ficam mais prováveis.",
                    "Feche com a regra prática: no Forex, compare duas moedas; não analise uma isoladamente.",
                ],
                "pratica": "Escolha EUR/USD e escreva em uma frase qual economia parece mais forte e por quê.",
                "checklist": ["Crescimento", "Inflação", "Emprego", "Banco central", "Juros relativos"],
            },
            {
                "id": "macro_02",
                "titulo": "2. Inflação: CPI, Core CPI, PCE e PPI",
                "duracao": "15–18 min",
                "objetivo": "Saber qual dado mede o quê e como a surpresa afeta o USD.",
                "resumo": "CPI e Core CPI mostram inflação ao consumidor; PCE é referência importante para o Fed; PPI observa preços ao produtor. O mercado reage principalmente ao resultado versus consenso.",
                "roteiro": [
                    "Defina CPI, Core CPI, PCE, Core PCE e PPI em linguagem simples.",
                    "Explique por que Core exclui itens mais voláteis e ajuda a medir persistência.",
                    "Mostre Real × Consenso × Anterior e diferencie surpresa positiva/negativa.",
                    "Conecte inflação persistente com Fed mais hawkish e juros altos por mais tempo.",
                ],
                "pratica": "Pegue um CPI fictício de 3,2% vs consenso 3,0% e descreva o primeiro impacto provável no USD.",
                "checklist": ["Real", "Consenso", "Anterior", "Core", "Reação do Treasury 2Y"],
            },
            {
                "id": "macro_03",
                "titulo": "3. Emprego: NFP, desemprego, salários e ADP",
                "duracao": "15–18 min",
                "objetivo": "Ler o mercado de trabalho como bloco, e não só o Payroll.",
                "resumo": "NFP mostra criação de vagas, desemprego mede folga no mercado de trabalho e salários ajudam a medir pressão inflacionária. Um único número raramente conta a história inteira.",
                "roteiro": [
                    "Explique Payroll/NFP, Unemployment Rate, Average Hourly Earnings e ADP.",
                    "Mostre combinações: NFP forte + salários fortes; NFP forte + desemprego subindo; etc.",
                    "Explique por que revisões de meses anteriores podem mudar a leitura.",
                    "Conecte emprego forte com expectativa de Fed menos dovish.",
                ],
                "pratica": "Monte uma conclusão usando NFP, desemprego e salários juntos em uma única frase.",
                "checklist": ["NFP", "Desemprego", "Salários", "Revisões", "Fed"],
            },
            {
                "id": "macro_04",
                "titulo": "4. Federal Reserve: FOMC, dot plot e hawkish/dovish",
                "duracao": "18–22 min",
                "objetivo": "Entender a decisão de juros e, principalmente, a narrativa do Fed.",
                "resumo": "A taxa atual importa, mas o mercado negocia o caminho futuro dos juros. Comunicado, coletiva, dot plot e discursos podem mudar a precificação mesmo sem alteração da taxa.",
                "roteiro": [
                    "Explique Fed Funds, FOMC e faixa-alvo.",
                    "Defina hawkish, dovish e neutro.",
                    "Mostre o que é dot plot e por que expectativas futuras mexem com o USD.",
                    "Ensine a comparar fala atual com a reunião anterior para detectar mudança de narrativa.",
                ],
                "pratica": "Leia uma frase hipotética do Fed e classifique: hawkish, dovish ou neutra.",
                "checklist": ["Taxa", "Comunicado", "Coletiva", "Dot plot", "Mudança de narrativa"],
            },
            {
                "id": "macro_05",
                "titulo": "5. Treasury 2Y, 10Y, juros reais e dólar",
                "duracao": "12–15 min",
                "objetivo": "Usar os juros de mercado como confirmação da narrativa macro.",
                "resumo": "O Treasury 2Y reage fortemente às expectativas de política monetária. O 10Y incorpora também crescimento, inflação e prêmio de prazo. O dólar costuma responder à mudança relativa de rendimentos.",
                "roteiro": [
                    "Explique 2Y e 10Y sem entrar em matemática pesada.",
                    "Mostre por que o 2Y é sensível ao Fed.",
                    "Explique juros reais como rendimento nominal menos inflação esperada.",
                    "Conecte Treasury, USD e pares como EUR/USD e USD/JPY.",
                ],
                "pratica": "Se o 2Y sobe forte após CPI acima do consenso, descreva o que você procuraria no USD.",
                "checklist": ["2Y", "10Y", "Juros reais", "USD", "Confirmação"],
            },
            {
                "id": "macro_06",
                "titulo": "6. PIB, ISM e PMI: atividade econômica",
                "duracao": "14–17 min",
                "objetivo": "Identificar aceleração ou desaceleração antes da decisão do banco central.",
                "resumo": "PIB é amplo e trimestral; ISM/PMI são mais rápidos e ajudam a enxergar a direção da atividade. Acima de 50 geralmente sinaliza expansão nos índices de difusão.",
                "roteiro": [
                    "Explique PIB real, ISM Industrial, ISM Serviços e PMI.",
                    "Mostre por que serviços têm peso importante na economia dos EUA.",
                    "Ensine a olhar tendência e surpresa, não apenas o nível absoluto.",
                    "Conecte atividade forte com inflação, emprego e expectativa de juros.",
                ],
                "pratica": "Compare ISM Serviços 56 com consenso 52 e escreva o efeito macro inicial.",
                "checklist": ["PIB", "ISM Industrial", "ISM Serviços", "50 pontos", "Surpresa"],
            },
            {
                "id": "macro_07",
                "titulo": "7. Força das 8 moedas e comparação de pares",
                "duracao": "16–20 min",
                "objetivo": "Comparar USD, EUR, GBP, JPY, CHF, CAD, AUD e NZD antes de escolher o par.",
                "resumo": "Um par é uma comparação. A melhor leitura surge quando uma moeda tem fundamentos claramente mais fortes e a outra mais fracos, com qualidade de dados suficiente.",
                "roteiro": [
                    "Explique score relativo de 0 a 100 sem tratá-lo como probabilidade de gain.",
                    "Compare juros, inflação, crescimento, emprego e narrativa do banco central.",
                    "Mostre como ler base e cotada em EUR/USD, GBP/USD e USD/JPY.",
                    "Explique por que força relativa precisa ser confirmada por estrutura e timing.",
                ],
                "pratica": "Escolha a moeda mais forte e a mais fraca no ranking e forme um par coerente.",
                "checklist": ["Base", "Cotada", "Diferença macro", "Qualidade", "Direção"],
            },
            {
                "id": "macro_08",
                "titulo": "8. Calendário econômico e Surprise Engine",
                "duracao": "18–22 min",
                "objetivo": "Ler notícia antes, durante e depois do release sem operar só pela cor do calendário.",
                "resumo": "O calendário organiza risco. Antes do dado, o consenso representa a expectativa. Depois, a diferença entre real e consenso gera surpresa; a reação depende também da narrativa já precificada.",
                "roteiro": [
                    "Explique anterior, consenso, real e revisão.",
                    "Mostre surpresa favorável/desfavorável ao USD para inflação, emprego e atividade.",
                    "Explique por que o mesmo dado pode gerar reação diferente conforme o que já estava precificado.",
                    "Finalize com checklist pré-release, release e pós-release.",
                ],
                "pratica": "Simule um release e escreva: surpresa, reação inicial e o que precisa confirmar no preço.",
                "checklist": ["Anterior", "Consenso", "Real", "Revisão", "Narrativa precificada"],
            },
        ],
    },
    {
        "id": "ict_smc",
        "titulo": "🧠 ICT & Smart Money",
        "descricao": "Estrutura, liquidez, localização e timing depois da direção macro.",
        "aulas": [
            {
                "id": "ict_01",
                "titulo": "1. Top-down: W1 → D1 → H4 → H1 → M15",
                "duracao": "14–18 min",
                "objetivo": "Usar cada timeframe para uma função específica.",
                "resumo": "W1/D1 definem contexto; H4/H1 confirmam estrutura; M15 serve para gatilho e timing.",
                "roteiro": [
                    "Defina a função de W1, D1, H4, H1 e M15.",
                    "Explique por que o M15 não deve escolher a direção macro.",
                    "Mostre alinhamento e conflito entre timeframes.",
                    "Conecte a leitura ao Scanner Técnico do AtlasQuant.",
                ],
                "pratica": "Escreva uma leitura top-down em cinco linhas, uma por timeframe.",
                "checklist": ["W1", "D1", "H4", "H1", "M15"],
            },
            {
                "id": "ict_02",
                "titulo": "2. Liquidez: BSL, SSL e sweeps",
                "duracao": "15–18 min",
                "objetivo": "Mapear onde o preço pode buscar liquidez e reconhecer varreduras.",
                "resumo": "BSL fica acima de máximas; SSL abaixo de mínimas. Sweep é a busca do nível seguida de rejeição ou retorno.",
                "roteiro": [
                    "Defina BSL e SSL com exemplos simples.",
                    "Mostre máximas/mínimas anteriores e Asia High/Low como referências.",
                    "Explique sweep versus rompimento verdadeiro.",
                    "Conecte sweep com direção macro e confirmação M15.",
                ],
                "pratica": "Marque BSL e SSL num gráfico e escreva qual lado faz sentido com o viés macro.",
                "checklist": ["BSL", "SSL", "Asia High/Low", "Sweep", "Rejeição"],
            },
            {
                "id": "ict_03",
                "titulo": "3. BOS, CHoCH e mudança de estrutura",
                "duracao": "14–17 min",
                "objetivo": "Diferenciar continuação de mudança de comportamento.",
                "resumo": "BOS confirma continuidade de estrutura; CHoCH/MSS pode sinalizar mudança, mas precisa de contexto.",
                "roteiro": [
                    "Explique swing high e swing low.",
                    "Defina BOS e CHoCH/MSS.",
                    "Mostre falso rompimento versus fechamento estrutural.",
                    "Reforce que estrutura sem macro/localização pode gerar falso sinal.",
                ],
                "pratica": "Classifique três movimentos fictícios como BOS, CHoCH ou ruído.",
                "checklist": ["Swing", "BOS", "CHoCH/MSS", "Fechamento", "Contexto"],
            },
            {
                "id": "ict_04",
                "titulo": "4. Order Blocks e localização",
                "duracao": "14–18 min",
                "objetivo": "Usar Order Block como zona contextual, não como entrada automática.",
                "resumo": "Order Block é uma região associada ao deslocamento; sua qualidade depende de estrutura, liquidez e contexto.",
                "roteiro": [
                    "Defina Order Block bullish/bearish.",
                    "Explique mitigação e invalidação.",
                    "Mostre por que premium/discount melhora localização.",
                    "Conecte OB com sweep, FVG e direção macro.",
                ],
                "pratica": "Descreva o que tornaria um Order Block válido ou fraco.",
                "checklist": ["Deslocamento", "Mitigação", "Invalidação", "Premium/Discount", "Contexto"],
            },
            {
                "id": "ict_05",
                "titulo": "5. FVG, imbalance e deslocamento",
                "duracao": "12–16 min",
                "objetivo": "Entender desequilíbrio de preço e sua função no pullback.",
                "resumo": "FVG representa desequilíbrio entre candles. Pode servir como área de retorno, mas não garante reação.",
                "roteiro": [
                    "Explique FVG de forma visual e simples.",
                    "Mostre diferença entre FVG e gap tradicional.",
                    "Conecte deslocamento forte com criação de imbalance.",
                    "Use FVG apenas quando estrutura e direção estiverem alinhadas.",
                ],
                "pratica": "Identifique um FVG e escreva qual confirmação adicional exigiria.",
                "checklist": ["FVG", "Deslocamento", "Retorno", "Estrutura", "Confirmação"],
            },
            {
                "id": "ict_06",
                "titulo": "6. Killzones, Quarterly e perfis semanais",
                "duracao": "18–22 min",
                "objetivo": "Organizar o timing sem transformar horário em sinal.",
                "resumo": "Killzones e divisões temporais ajudam a organizar quando procurar liquidez, manipulação e expansão.",
                "roteiro": [
                    "Explique sessões da Ásia, Londres e Nova York.",
                    "Mostre Asia High/Low e janelas de maior liquidez.",
                    "Introduza Quarterly Theory como heurística temporal.",
                    "Explique perfis semanais como contexto, não como certeza.",
                ],
                "pratica": "Monte um plano de observação para Londres e Nova York sem prever direção pelo horário.",
                "checklist": ["Ásia", "Londres", "Nova York", "Quarterly", "Perfil semanal"],
            },
            {
                "id": "ict_07",
                "titulo": "7. Setup integrado: Macro → Liquidez → Gatilho",
                "duracao": "20–25 min",
                "objetivo": "Juntar tudo em uma rotina seletiva.",
                "resumo": "A execução só ganha prioridade quando macro, estrutura, localização, volatilidade e gatilho concordam.",
                "roteiro": [
                    "Comece pela moeda forte/fraca e o evento do dia.",
                    "Confirme W1/D1 e posição no range.",
                    "Mapeie liquidez, ADR e killzone.",
                    "Use H4/H1 para alinhamento e M15 para gatilho final.",
                ],
                "pratica": "Preencha o checklist completo de um par sem executar nenhuma ordem.",
                "checklist": ["Macro", "W1/D1", "Liquidez", "ADR", "H4/H1", "M15"],
            },
        ],
    },
    {
        "id": "atlasquant",
        "titulo": "🧭 Operação no AtlasQuant",
        "descricao": "Como usar cada bloco do aplicativo sem confundir score com certeza.",
        "aulas": [
            {
                "id": "aq_01",
                "titulo": "1. Painel Mestre: leitura em 60 segundos",
                "duracao": "10–12 min",
                "objetivo": "Saber priorizar pares usando o painel consolidado.",
                "resumo": "O Painel Mestre junta macro, Market Map, scanner técnico, ADR e Gate; índice integrado é ranking, não probabilidade.",
                "roteiro": [
                    "Leia Pares, Market Map e Scanner técnico atual.",
                    "Explique Estado, Índice Integrado e Gate.",
                    "Mostre por que EXECUTÁVEL exige mais que score alto.",
                    "Ensine a abrir o diagnóstico consolidado antes de qualquer decisão.",
                ],
                "pratica": "Escolha o melhor contexto e justifique usando pelo menos quatro campos.",
                "checklist": ["Estado", "Índice", "Gate", "ADR", "Técnica"],
            },
            {
                "id": "aq_02",
                "titulo": "2. Market Map e top-down operacional",
                "duracao": "12–15 min",
                "objetivo": "Interpretar W1/D1, liquidez, localização e evento.",
                "resumo": "Market Map organiza o cenário e impede que o scanner técnico opere fora de contexto.",
                "roteiro": [
                    "Leia W1 e D1.",
                    "Interprete localização acima/abaixo do range.",
                    "Use sweep e liquidez alvo.",
                    "Cheque risco de evento e ADR antes do gatilho.",
                ],
                "pratica": "Descreva um cenário de WAIT mesmo com técnica parcialmente alinhada.",
                "checklist": ["W1", "D1", "Localização", "Sweep", "Evento", "ADR"],
            },
            {
                "id": "aq_03",
                "titulo": "3. Scanner técnico automático",
                "duracao": "10–12 min",
                "objetivo": "Entender H4/H1/M15 e o modo automático.",
                "resumo": "O scanner atualiza pares ausentes/vencidos em lotes controlados, respeitando a cota da Twelve Data.",
                "roteiro": [
                    "Explique H4 como tendência/estrutura, H1 como pullback/alinhamento e M15 como gatilho.",
                    "Mostre o indicador Scanner técnico atual X/7.",
                    "Explique atualização automática e cooldown da Twelve Data.",
                    "Mostre quando usar o botão manual como reserva.",
                ],
                "pratica": "Observe um par com H4 verde, H1 amarelo e M15 vermelho e explique por que ainda é WAIT.",
                "checklist": ["H4", "H1", "M15", "Frescura", "Cooldown"],
            },
            {
                "id": "aq_04",
                "titulo": "4. Aba EUA e Fed",
                "duracao": "12–16 min",
                "objetivo": "Usar qualidade de dados, indicadores e narrativa do Fed.",
                "resumo": "A aba EUA mostra dados oficiais, frescura e score macro; a aba Fed contextualiza a política monetária.",
                "roteiro": [
                    "Cheque primeiro Qualidade dos dados.",
                    "Leia juros, inflação, emprego, PIB e Treasuries.",
                    "Use Auditoria dos dados para validar fonte e idade.",
                    "Compare score macro com narrativa hawkish/dovish.",
                ],
                "pratica": "Faça uma conclusão do USD usando três indicadores e o Fed.",
                "checklist": ["Qualidade", "FRED", "Fed", "2Y", "Conclusão"],
            },
            {
                "id": "aq_05",
                "titulo": "5. Moedas e Pares: força relativa",
                "duracao": "12–15 min",
                "objetivo": "Transformar ranking de moedas em hipótese de par.",
                "resumo": "O ranking ajuda a encontrar contraste de força; a aba Pares testa essa diferença dentro da matriz.",
                "roteiro": [
                    "Leia força das moedas sem tratar score como previsão.",
                    "Escolha contraste forte/fraco.",
                    "Valide qualidade das duas moedas.",
                    "Confirme no par com Market Map e scanner.",
                ],
                "pratica": "Forme dois pares candidatos e elimine um por baixa qualidade ou conflito técnico.",
                "checklist": ["Força", "Qualidade", "Par", "Market Map", "Scanner"],
            },
            {
                "id": "aq_06",
                "titulo": "6. Backtest, performance e diário",
                "duracao": "15–20 min",
                "objetivo": "Medir se o operacional funciona em vez de confiar na memória.",
                "resumo": "Backtest e diário servem para separar percepção de evidência: taxa de acerto, payoff, drawdown e contexto.",
                "roteiro": [
                    "Defina gain, loss, breakeven, payoff e drawdown.",
                    "Explique por que taxa de acerto sozinha não basta.",
                    "Registre setup, contexto macro, horário e resultado.",
                    "Revise amostras por setup antes de alterar regras.",
                ],
                "pratica": "Registre cinco operações fictícias com motivo de entrada e motivo de saída.",
                "checklist": ["Setup", "Resultado", "Risco", "Payoff", "Amostra"],
            },
            {
                "id": "aq_07",
                "titulo": "7. Rotina diária completa",
                "duracao": "15–18 min",
                "objetivo": "Ter uma sequência fixa antes, durante e depois da sessão.",
                "resumo": "Rotina reduz decisão impulsiva: macro semanal, calendário, força, Market Map, scanner, execução e revisão.",
                "roteiro": [
                    "Pré-mercado: calendário, macro e moedas.",
                    "Seleção: pares, W1/D1, Market Map e ADR.",
                    "Execução: H4/H1 e gatilho M15 apenas quando permitido.",
                    "Pós-mercado: diário, screenshot, resultado e revisão.",
                ],
                "pratica": "Use o checklist em um dia completo sem pular etapas.",
                "checklist": ["Calendário", "Macro", "Pares", "Market Map", "Scanner", "Diário"],
            },
        ],
    },
]


def academy_stats(completed_ids=None) -> dict[str, int]:
    completed = set(completed_ids or [])
    all_ids = [lesson["id"] for track in ACADEMY_TRACKS for lesson in track["aulas"]]
    done = sum(1 for lesson_id in all_ids if lesson_id in completed)
    return {"total": len(all_ids), "concluidas": done, "restantes": len(all_ids) - done}


def get_lesson(lesson_id: str):
    for track in ACADEMY_TRACKS:
        for lesson in track["aulas"]:
            if lesson["id"] == lesson_id:
                return lesson
    return None


def render_academy() -> None:
    completed_key = "atlasquant_academy_completed"
    completed = set(st.session_state.get(completed_key, []))
    stats = academy_stats(completed)

    st.markdown("### 🎓 AtlasQuant Academy")
    st.caption(
        "Trilha prática: Macro → ICT/SMC → uso do AtlasQuant. "
        "Os roteiros abaixo são material original para produzir os vídeos da Academy."
    )

    c1, c2, c3 = st.columns(3)
    c1.metric("Aulas", stats["total"])
    c2.metric("Concluídas", stats["concluidas"])
    c3.metric("Restantes", stats["restantes"])
    if stats["total"]:
        st.progress(stats["concluidas"] / stats["total"])

    track_titles = [track["titulo"] for track in ACADEMY_TRACKS]
    selected_track_title = st.selectbox("Trilha", track_titles, key="academy_track")
    track = next(track for track in ACADEMY_TRACKS if track["titulo"] == selected_track_title)
    st.caption(track["descricao"])

    lesson_titles = [lesson["titulo"] for lesson in track["aulas"]]
    selected_lesson_title = st.selectbox("Aula", lesson_titles, key="academy_lesson")
    lesson = next(lesson for lesson in track["aulas"] if lesson["titulo"] == selected_lesson_title)

    with st.container(border=True):
        st.markdown(f"#### {lesson['titulo']}")
        st.caption(f"⏱️ {lesson['duracao']}")
        st.markdown(f"**Objetivo:** {lesson['objetivo']}")
        st.markdown(f"**Resumo:** {lesson['resumo']}")

        st.markdown("##### 🎬 Roteiro do vídeo")
        for idx, item in enumerate(lesson["roteiro"], 1):
            st.markdown(f"{idx}. {item}")

        st.markdown("##### 🧪 Exercício prático")
        st.info(lesson["pratica"])

        st.markdown("##### ✅ Checklist")
        st.markdown(" · ".join(str(item) for item in lesson["checklist"]))

        is_done = lesson["id"] in completed
        new_done = st.checkbox(
            "Marcar esta aula como concluída",
            value=is_done,
            key=f"academy_done_{lesson['id']}",
        )
        if new_done and not is_done:
            completed.add(lesson["id"])
            st.session_state[completed_key] = sorted(completed)
            st.rerun()
        elif is_done and not new_done:
            completed.discard(lesson["id"])
            st.session_state[completed_key] = sorted(completed)
            st.rerun()

    with st.expander("📋 Ver programa completo"):
        for tr in ACADEMY_TRACKS:
            st.markdown(f"**{tr['titulo']}** — {tr['descricao']}")
            for lesson_item in tr["aulas"]:
                mark = "✅" if lesson_item["id"] in completed else "⬜"
                st.markdown(f"{mark} {lesson_item['titulo']} · {lesson_item['duracao']}")
