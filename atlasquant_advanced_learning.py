"""AtlasQuant guided Advanced learning path.

Educational presentation only. It explains the layers used by AtlasQuant and
keeps learning connected to the Radar without changing any market score, gate,
risk limit or execution behavior.
"""
from __future__ import annotations

from typing import Any

import streamlit as st

SCHEMA="ATLASQUANT_GUIDED_ADVANCED_V1"

ADVANCED_MODULES=(
    {
        "id":"start",
        "tab":"Comece aqui",
        "title":"🧭 Comece por aqui",
        "intro":"Antes de olhar BUY/SELL, entenda as camadas que constroem uma leitura de mercado.",
        "why":"O objetivo é sair da análise isolada e aprender a juntar contexto, preço, risco e evidência.",
        "market":"O mercado pode mudar quando macro, notícia, fluxo, liquidez ou regime mudam. Nenhuma camada isolada manda sozinha.",
        "atlas":"O Radar fica na frente. Esta trilha explica, em ordem, de onde vem cada parte da leitura.",
        "example":"Você vê EUR/USD no Radar. Em vez de entrar pelo gráfico sozinho, abre o porquê e confere macro, evento, estrutura, timing e risco.",
        "pitfalls":("Pular direto para o sinal.","Confundir score com certeza.","Ignorar NÃO OPERAR."),
        "radar":"No Radar, use 'Por que está assim?' como porta de entrada para as camadas.",
    },
    {
        "id":"macro",
        "tab":"Macro",
        "title":"🌍 Macroeconomia",
        "intro":"Macroeconomia estuda a economia como um todo: inflação, emprego, crescimento, juros e bancos centrais.",
        "why":"Esses fatores mudam expectativas de juros e fluxo de capital, que são centrais para moedas e índices.",
        "market":"CPI, PCE, Payroll, PIB, PMI/ISM e decisões de bancos centrais podem alterar a narrativa do mercado.",
        "atlas":"AtlasQuant organiza crescimento, inflação, emprego, juros e narrativa dos bancos centrais antes de olhar o timing técnico.",
        "example":"Inflação persistente pode reduzir a expectativa de cortes. O efeito no USD depende do que o mercado já esperava e do restante dos dados.",
        "pitfalls":("Usar um indicador sozinho.","Comparar só com o número anterior.","Ignorar o que já estava precificado."),
        "radar":"A camada macro ajuda a explicar o lado que merece investigação; não vira ordem automática.",
    },
    {
        "id":"micro",
        "tab":"Micro",
        "title":"🏭 Microeconomia",
        "intro":"Microeconomia olha empresas, setores, consumidores, oferta, demanda, custos, preços e incentivos.",
        "why":"Ela é especialmente útil para ações e setores e também ajuda a entender canais que depois aparecem nos dados macro.",
        "market":"Margens, estoques, demanda, custos de insumos, crédito e comportamento de empresas/consumidores podem afetar ativos e setores.",
        "atlas":"A camada micro deve ser usada quando houver dados adequados ao ativo. Ela não substitui macro em Forex.",
        "example":"Uma alta de custos pode pressionar margem de empresas; em escala maior, pressões de custos também podem aparecer em indicadores de preços.",
        "pitfalls":("Tratar micro como sinônimo de macro.","Usar dado de uma empresa para explicar uma moeda inteira.","Ignorar setor e contexto."),
        "radar":"Quando aplicável, a microeconomia entra como contexto adicional, com fonte e qualidade explícitas.",
    },
    {
        "id":"geopolitics",
        "tab":"Geopolítica",
        "title":"🌐 Geopolítica",
        "intro":"Geopolítica observa como conflitos, sanções, comércio, energia, rotas estratégicas e decisões entre países afetam risco e fluxo.",
        "why":"Choques geopolíticos podem mudar petróleo, inflação esperada, ativos de proteção, cadeias de suprimento e apetite por risco.",
        "market":"O impacto não é fixo: depende do evento, duração, surpresa, ativos envolvidos e do regime que já existia.",
        "atlas":"AtlasQuant deve tratar geopolítica como risco/contexto documentado, separado de opinião e sem inventar causalidade.",
        "example":"Uma interrupção relevante de energia pode alterar expectativas de inflação e crescimento, mas a reação de cada ativo precisa ser observada no contexto.",
        "pitfalls":("Transformar manchete em ordem.","Assumir correlação fixa.","Confundir opinião política com análise de mercado."),
        "radar":"Eventos relevantes elevam cautela e podem reduzir a confiança ou acionar AGUARDAR.",
    },
    {
        "id":"fundamental",
        "tab":"Fundamental",
        "title":"📚 Análise Fundamentalista",
        "intro":"Análise fundamentalista estuda os fatores econômicos e financeiros que sustentam o valor e o comportamento de um ativo.",
        "why":"Ela ajuda a separar movimento de curto prazo de mudanças mais profundas na tese.",
        "market":"Em moedas, juros, crescimento, inflação e balanço externo pesam muito; em empresas entram receita, lucro, caixa, dívida e valuation.",
        "atlas":"O sistema adapta a camada fundamental ao tipo de ativo e mostra quais fatores realmente estão disponíveis.",
        "example":"Uma empresa pode subir tecnicamente enquanto fundamentos pioram; uma moeda pode ter gráfico forte enquanto o diferencial de juros perde suporte.",
        "pitfalls":("Aplicar a mesma lista de fundamentos a todo ativo.","Ignorar horizonte de tempo.","Confundir valuation com timing."),
        "radar":"Fundamentos ajudam a construir contexto; timing e risco continuam em camadas separadas.",
    },
    {
        "id":"news",
        "tab":"Indicadores",
        "title":"📰 Indicadores econômicos & notícias",
        "intro":"Anterior mostra a leitura passada; consenso é a expectativa antes da divulgação; atual é o número publicado.",
        "why":"Mercado reage muito à surpresa: a diferença entre o que saiu e o que estava esperado, junto de revisões e contexto.",
        "market":"Acima, em linha ou abaixo do consenso não têm o mesmo significado para todo indicador. Payroll, desemprego, inflação e atividade precisam de lógica própria.",
        "atlas":"O calendário deve explicar anterior, consenso, atual, surpresa, importância, cenário provável e o que pode invalidar a leitura.",
        "example":"Payroll acima do consenso pode parecer forte, mas salários, desemprego e revisões podem contar outra história.",
        "pitfalls":("Usar regra 'acima = moeda sobe' para tudo.","Ignorar revisão.","Operar segundos antes de release sem entender o risco."),
        "radar":"O Protetor de Notícias sinaliza risco de evento e o botão 'Por que isso importa agora?' liga o calendário ao Radar.",
    },
    {
        "id":"technical",
        "tab":"Técnica",
        "title":"📈 Análise Técnica",
        "intro":"Análise técnica organiza o comportamento do preço: tendência, estrutura, níveis, volatilidade e confirmação.",
        "why":"Ela ajuda no timing e na invalidação, mas não explica sozinha todos os movimentos.",
        "market":"Suporte, resistência, tendência, candles e estrutura mostram o que o preço está fazendo, não uma certeza sobre o próximo movimento.",
        "atlas":"A técnica entra depois do contexto e é usada junto de dados frescos, evento, risco e estrutura maior.",
        "example":"Um suporte pode funcionar várias vezes e depois ser varrido. Por isso o sistema procura liquidez, confirmação e contexto.",
        "pitfalls":("Achar que suporte é parede.","Entrar antes da confirmação.","Ignorar notícia de alto impacto."),
        "radar":"H4/H1/M15 e regime ajudam a dizer se o contexto merece atenção, aguardar ou evitar.",
    },
    {
        "id":"ict-smc",
        "tab":"ICT/SMC",
        "title":"🧠 ICT / SMC",
        "intro":"ICT/SMC organizam conceitos como liquidez, displacement, MSS/BOS/CHOCH, FVG, OTE, Order Block, AMD/PO3 e timing.",
        "why":"O foco é observar estrutura e liquidez de forma testável, sem tratar 'institucional' como algo invisível que sabemos com certeza.",
        "market":"Sweeps, deslocamento, mudança de estrutura e retorno a zonas podem formar modelos repetíveis, mas cada modelo precisa ser formalizado e testado.",
        "atlas":"Cada modelo tem catálogo, backtest, Paper e Passaporte próprios. Evidências iguais não são contadas duas vezes.",
        "example":"FVG não é entrada automática: primeiro contexto, depois displacement/zona, retorno, confirmação e invalidação.",
        "pitfalls":("Marcar qualquer gap como FVG.","Ver manipulação em todo movimento.","Escolher setup depois de saber se deu gain."),
        "radar":"O Radar mostra confluência e conflito; o setup só ganha peso depois de evidência suficiente.",
    },
    {
        "id":"sessions",
        "tab":"Sessões",
        "title":"🕒 Sessões & horários",
        "intro":"Ásia, Londres e Nova York têm características diferentes de liquidez, volatilidade e participação.",
        "why":"Um operacional pode funcionar bem em uma sessão e mal em outra. Horário precisa entrar no backtest.",
        "market":"Sobreposição de sessões e eventos econômicos podem mudar velocidade e volatilidade.",
        "atlas":"O usuário escolhe sua disponibilidade: Ásia+Londres, Nova York+continuidade ou todos os horários. O Radar prioriza sem fabricar sinal.",
        "example":"Quem só opera à noite não precisa receber a mesma prioridade de quem acompanha Nova York durante o dia.",
        "pitfalls":("Achar que sessão define direção.","Misturar resultados de sessões sem segmentar.","Forçar entrada porque a killzone começou."),
        "radar":"O perfil de sessão reorganiza onde olhar primeiro; viés, score e Gate não são alterados.",
    },
    {
        "id":"evidence",
        "tab":"Evidências",
        "title":"🧪 Backtest, Walk-Forward, Paper & Evidências",
        "intro":"Uma ideia só vira candidata séria depois de sobreviver a testes fora da amostra e observação prospectiva.",
        "why":"Backtest sozinho pode enganar por ajuste ao passado. Por isso o AtlasQuant separa etapas de validação.",
        "market":"Regime, ativo, sessão, custos, amostra e período mudam o resultado de um operacional.",
        "atlas":"Escada: Backtest → estabilidade temporal → Walk-Forward/OOS → fricção/parâmetros → Paper/Forward → revisão humana.",
        "example":"Um setup com ótimo backtest mas Paper fraco não é promovido; o Passaporte mostra a lacuna.",
        "pitfalls":("Escolher o maior lucro recente.","Ignorar drawdown/custos.","Usar informação futura no backtest."),
        "radar":"Só evidência suficientemente estável deve influenciar como o Radar apresenta um modelo.",
    },
    {
        "id":"radar",
        "tab":"Juntar tudo",
        "title":"🎯 Como tudo chega ao Radar",
        "intro":"O Radar é o resumo final, não o começo do raciocínio.",
        "why":"Ele economiza tempo ao juntar camadas, mostrar conflitos e dizer quando não existe cenário limpo.",
        "market":"Uma leitura pode mudar quando chega dado novo, evento, alteração de regime ou perda de confirmação.",
        "atlas":"Fundamental/Macro → SMC → ICT → Price Action → Safety. O sistema expõe fatores a favor, contra, ausentes e qualidade dos dados.",
        "example":"Viés de alta com evento de alto impacto próximo e M15 sem confirmação pode terminar em AGUARDAR, mesmo com macro favorável.",
        "pitfalls":("Ler prioridade como chance de lucro.","Forçar viés.","Ignorar confiança que envelheceu."),
        "radar":"Radar bom também sabe dizer: 'não há oportunidade boa agora'.",
    },
)


def advanced_modules()->tuple[dict[str,Any],...]:
    return tuple(dict(x) for x in ADVANCED_MODULES)


def advanced_module(module_id:object)->dict[str,Any]|None:
    key=str(module_id or "").strip().casefold()
    return next((dict(x) for x in ADVANCED_MODULES if str(x["id"]).casefold()==key),None)


def guided_video_script(module_id:object)->dict[str,Any]|None:
    item=advanced_module(module_id)
    if item is None:
        return None
    narration=(
        f"{item['title']}. {item['intro']} "
        f"Por que importa: {item['why']} "
        f"No mercado: {item['market']} "
        f"No AtlasQuant: {item['atlas']} "
        f"Exemplo: {item['example']} "
        "Esta explicação é educacional e não representa garantia, recomendação ou ordem automática."
    )
    words=len(narration.split())
    return {
        "schema":SCHEMA,
        "module_id":item["id"],
        "narration":narration,
        "estimated_seconds":max(45,min(75,round(words/2.45))),
        "script_ready":True,
        "rendered_video":False,
        "published_video":False,
        "automatic_publish":False,
    }


def guided_learning_ready()->bool:
    ids=[str(x["id"]) for x in ADVANCED_MODULES]
    required={"start","macro","micro","geopolitics","fundamental","news","technical","ict-smc","sessions","evidence","radar"}
    return (
        required.issubset(ids)
        and len(ids)==len(set(ids))
        and all(guided_video_script(x["id"]) for x in ADVANCED_MODULES)
    )


def render_guided_advanced_learning()->dict[str,Any]:
    st.markdown("### 🧭 Trilha guiada do modo Avançado")
    st.caption(
        "Comece pelo primeiro módulo e avance em ordem. O Radar continua sendo a tela principal; "
        "esta trilha explica por que ele chegou a cada leitura."
    )

    tabs=st.tabs([str(x["tab"]) for x in ADVANCED_MODULES])
    for tab,item in zip(tabs,ADVANCED_MODULES):
        with tab:
            media=guided_video_script(item["id"])
            st.markdown(f"### {item['title']}")
            st.info("🎬 Vídeo curto de abertura — roteiro pronto. O vídeo final ainda será renderizado/publicado.")
            if media:
                with st.expander("Ver roteiro do vídeo de abertura",expanded=False):
                    st.write(media["narration"])
                    st.caption(f"Duração estimada: {media['estimated_seconds']}s")

            st.markdown(f"**Em uma frase:** {item['intro']}")
            st.markdown(f"**Por que isso importa:** {item['why']}")
            st.markdown(f"**O que pode mexer no mercado:** {item['market']}")
            st.markdown(f"**Como o AtlasQuant usa:** {item['atlas']}")
            st.markdown(f"**Exemplo simples:** {item['example']}")
            st.markdown("**Erros comuns:**")
            for pitfall in item["pitfalls"]:
                st.markdown(f"- {pitfall}")
            st.success("🎯 Ligação com o Radar: "+str(item["radar"]))

    st.warning(
        "A trilha ensina como interpretar o sistema. Ela não transforma conteúdo educacional em sinal "
        "nem promete taxa de acerto."
    )
    return {
        "schema":SCHEMA,
        "modules":len(ADVANCED_MODULES),
        "ready":guided_learning_ready(),
        "real_orders_enabled":False,
        "trading_side_effects":False,
    }


__all__=[
    "SCHEMA","ADVANCED_MODULES","advanced_modules","advanced_module",
    "guided_video_script","guided_learning_ready","render_guided_advanced_learning",
]
