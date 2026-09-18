"""AtlasQuant Academy — trilhas educacionais integradas ao aplicativo.

Camada educacional: não altera motor de decisão, scores, Gate, scanner ou histórico.
Os roteiros de vídeo são originais e servem como base para produção das aulas.
"""
from __future__ import annotations

from typing import Any

import html
import streamlit as st


MACRO_VIDEO_SCRIPTS: dict[str, list[dict[str, str]]] = {
    "macro_01": [
        {"bloco": "Abertura", "tela": "AtlasQuant > Moedas / Pares", "narracao": "Hoje você vai entender a lógica mais importante da macroeconomia aplicada ao Forex: crescimento, inflação, emprego e juros formam um ciclo. O objetivo não é decorar indicador; é descobrir qual moeda tem mais força relativa."},
        {"bloco": "Conceito", "tela": "Quadro simples com Crescimento → Inflação → Juros → Moeda", "narracao": "Quando a economia cresce com força, empresas produzem mais, contratam mais e a demanda aumenta. Se essa demanda pressiona preços, a inflação pode subir. O banco central reage com juros mais altos ou mantendo juros altos por mais tempo."},
        {"bloco": "Leitura de moeda", "tela": "Comparação USD x EUR", "narracao": "No Forex você nunca analisa uma moeda sozinha. Em EUR/USD, por exemplo, você compara a economia da zona do euro com a dos Estados Unidos. Se o lado americano estiver mais forte e com juros relativamente mais altos, isso tende a favorecer o dólar, tudo o mais constante."},
        {"bloco": "Exemplo", "tela": "AtlasQuant > ranking de moedas", "narracao": "Imagine USD com atividade forte, emprego resistente e Fed ainda restritivo, enquanto EUR desacelera e o BCE sinaliza cortes. A leitura relativa fica favorável ao dólar. Isso não é entrada automática; é direção macro para depois validar no gráfico."},
        {"bloco": "Fechamento", "tela": "Checklist da aula", "narracao": "Antes de olhar o gráfico, responda cinco perguntas: crescimento, inflação, emprego, banco central e juros relativos. Depois compare as duas moedas do par."},
    ],
    "macro_02": [
        {"bloco": "Abertura", "tela": "AtlasQuant > EUA", "narracao": "Agora vamos separar CPI, Core CPI, PCE, Core PCE e PPI. Todos falam de preços, mas não contam exatamente a mesma história."},
        {"bloco": "Conceito", "tela": "Cards CPI / Core / PCE / PPI", "narracao": "CPI mede inflação ao consumidor. Core CPI exclui itens mais voláteis e ajuda a enxergar persistência. PCE é outra medida de consumo e recebe muita atenção do Fed. PPI observa preços no produtor e pode sinalizar pressões que chegam depois ao consumidor."},
        {"bloco": "Surpresa", "tela": "Real x Consenso x Anterior", "narracao": "O mercado reage principalmente ao que saiu versus o que era esperado. Se o CPI vem acima do consenso, a surpresa pode elevar a expectativa de juros mais altos por mais tempo. Se vem abaixo, o efeito pode ser o oposto."},
        {"bloco": "Confirmação", "tela": "Treasury 2Y + USD", "narracao": "Depois do dado, confirme a narrativa no Treasury de 2 anos e no dólar. Se inflação surpreende para cima e o 2Y também sobe, a leitura hawkish ganha força."},
        {"bloco": "Fechamento", "tela": "Checklist Real / Consenso / Core / 2Y", "narracao": "Nunca opere só porque a inflação veio alta ou baixa. Compare real, consenso, anterior, núcleo e reação dos juros de mercado."},
    ],
    "macro_03": [
        {"bloco": "Abertura", "tela": "Calendário econômico > emprego", "narracao": "Payroll sozinho não explica todo o mercado de trabalho. Nesta aula, você vai ler NFP, desemprego, salários e revisões como um conjunto."},
        {"bloco": "Conceito", "tela": "NFP / Unemployment / AHE / ADP", "narracao": "NFP mostra criação líquida de vagas fora do setor agrícola. A taxa de desemprego mede a parcela da força de trabalho sem emprego. Average Hourly Earnings ajuda a medir pressão salarial. ADP é uma referência privada, mas não substitui o NFP oficial."},
        {"bloco": "Combinações", "tela": "Tabela de cenários", "narracao": "NFP forte com salários fortes costuma reforçar uma leitura de economia resistente. Mas NFP forte com desemprego subindo e revisões negativas pode deixar o quadro mais misto. Por isso, evite olhar só um número."},
        {"bloco": "Fed", "tela": "Fed narrativo", "narracao": "Mercado de trabalho muito apertado pode dificultar cortes de juros. Já uma desaceleração consistente pode aumentar a probabilidade de uma postura mais dovish."},
        {"bloco": "Fechamento", "tela": "Checklist emprego", "narracao": "Sua conclusão deve caber em uma frase usando pelo menos NFP, desemprego e salários. Depois, veja se as revisões confirmam ou contradizem a leitura."},
    ],
    "macro_04": [
        {"bloco": "Abertura", "tela": "AtlasQuant > Fed", "narracao": "O mercado não negocia apenas a taxa de hoje. Ele tenta antecipar o caminho futuro dos juros. É por isso que comunicado, coletiva e dot plot podem mover o dólar mesmo sem mudança na taxa."},
        {"bloco": "FOMC", "tela": "Taxa / comunicado / coletiva", "narracao": "O FOMC define a faixa-alvo dos Fed Funds. A decisão é só a primeira camada. Depois, o mercado lê o texto e a coletiva para entender se o Fed está mais preocupado com inflação ou com crescimento."},
        {"bloco": "Hawkish e dovish", "tela": "Semáforo Hawkish / Neutro / Dovish", "narracao": "Hawkish significa inclinação a juros mais altos ou cortes mais lentos. Dovish significa maior abertura para cortes ou estímulo. Neutro é quando a mensagem não muda de forma clara o caminho esperado."},
        {"bloco": "Dot plot", "tela": "Exemplo de pontos por ano", "narracao": "O dot plot mostra onde cada participante projeta a taxa futura. O importante não é um ponto isolado, mas a mediana e a mudança em relação à reunião anterior."},
        {"bloco": "Fechamento", "tela": "Comparação reunião atual x anterior", "narracao": "Sempre compare a reunião atual com a anterior. O que move o mercado muitas vezes é a mudança de narrativa, não o nível absoluto da taxa."},
    ],
    "macro_05": [
        {"bloco": "Abertura", "tela": "AtlasQuant > EUA > Treasury 2Y / 10Y", "narracao": "Os Treasuries ajudam a confirmar se o mercado está acreditando na narrativa macro. O 2Y responde mais de perto à expectativa de política monetária; o 10Y mistura crescimento, inflação e prêmio de prazo."},
        {"bloco": "2Y", "tela": "Treasury 2Y", "narracao": "Se o mercado espera Fed mais restritivo, o rendimento de 2 anos tende a subir. Se espera cortes mais rápidos, tende a cair. Por isso ele é uma ótima confirmação para CPI, Payroll e FOMC."},
        {"bloco": "10Y", "tela": "Treasury 10Y", "narracao": "O 10Y olha um horizonte maior e pode se mover por crescimento, inflação de longo prazo e oferta de títulos. Nem sempre ele anda igual ao 2Y."},
        {"bloco": "Juro real", "tela": "Nominal - inflação esperada", "narracao": "Uma forma simples de pensar juro real é rendimento nominal menos inflação esperada. Quando o retorno real relativo dos EUA sobe, o dólar pode ganhar suporte."},
        {"bloco": "Fechamento", "tela": "Exemplo CPI acima + 2Y sobe", "narracao": "Se CPI surpreende para cima e o 2Y também sobe, a confirmação é mais limpa. Depois compare a reação do USD com a moeda do outro lado do par."},
    ],
    "macro_06": [
        {"bloco": "Abertura", "tela": "PIB / ISM / PMI", "narracao": "PIB mostra o quadro amplo, mas chega mais devagar. ISM e PMI são mais rápidos e ajudam a perceber se a atividade está acelerando ou esfriando."},
        {"bloco": "PIB", "tela": "PIB real", "narracao": "PIB real mede a produção ajustada pela inflação. Crescimento mais forte que o esperado pode sustentar emprego e juros, mas também pode aumentar pressão inflacionária."},
        {"bloco": "ISM e PMI", "tela": "Índices de difusão", "narracao": "Nos índices de difusão, 50 costuma separar expansão de contração. Mas o nível sozinho não basta: compare também tendência e surpresa contra o consenso."},
        {"bloco": "Serviços", "tela": "ISM Serviços", "narracao": "Nos Estados Unidos, serviços têm grande peso. Um ISM Serviços muito forte pode alterar rapidamente a leitura de atividade, especialmente se preços e emprego dentro do relatório também vierem fortes."},
        {"bloco": "Fechamento", "tela": "Exemplo 56 vs 52", "narracao": "Se o ISM Serviços sai 56 contra consenso 52, a surpresa inicial é de atividade mais forte. Depois veja Treasuries, dólar e se isso muda a expectativa para o Fed."},
    ],
    "macro_07": [
        {"bloco": "Abertura", "tela": "AtlasQuant > Moedas", "narracao": "O objetivo aqui é parar de perguntar apenas se o dólar está forte. Você vai comparar oito moedas e procurar contraste: uma forte contra outra fraca."},
        {"bloco": "Score relativo", "tela": "Ranking 0–100", "narracao": "O score de 0 a 100 é um ranking relativo, não probabilidade de gain. Ele organiza juros, inflação, crescimento, emprego e narrativa dos bancos centrais."},
        {"bloco": "Base e cotada", "tela": "EUR/USD, GBP/USD, USD/JPY", "narracao": "Em EUR/USD, euro é base e dólar é cotada. Se EUR fortalece e USD enfraquece, o par tende a ter pressão de alta. Em USD/JPY, um USD mais forte contra JPY mais fraco favorece pressão de alta."},
        {"bloco": "Escolha de par", "tela": "Top 3 e Bottom 3", "narracao": "A melhor oportunidade costuma aparecer quando existe boa diferença de força e qualidade dos dados. Depois, Market Map e scanner técnico precisam confirmar estrutura e timing."},
        {"bloco": "Fechamento", "tela": "Checklist força / qualidade / direção", "narracao": "Primeiro escolha forte contra fraca. Depois confirme qualidade, direção macro, estrutura e gatilho. O ranking sozinho nunca executa uma operação."},
    ],
    "macro_08": [
        {"bloco": "Abertura", "tela": "Calendário Econômico Automático", "narracao": "Calendário não serve para prever o futuro pela cor do evento. Ele serve para organizar expectativa, risco e surpresa."},
        {"bloco": "Antes do release", "tela": "Anterior / Consenso", "narracao": "Antes do dado, compare anterior e consenso. O consenso representa a expectativa média do mercado. É essa expectativa que cria o ponto de referência para a surpresa."},
        {"bloco": "No release", "tela": "Real / Consenso / Revisão", "narracao": "Quando sai o real, compare imediatamente com consenso. Depois confira revisão do dado anterior. Uma revisão grande pode reforçar ou anular a leitura do número principal."},
        {"bloco": "Depois do release", "tela": "Surprise Engine + Treasuries + USD", "narracao": "O Surprise Engine mede direção e intensidade da diferença. Mas a reação final depende do que já estava precificado. Confirme a leitura no Treasury 2Y, no dólar e na estrutura do par."},
        {"bloco": "Fechamento", "tela": "Checklist pré / durante / pós-release", "narracao": "Pré-release: expectativa e risco. Release: real, consenso e revisão. Pós-release: confirmação nos juros e no preço. Essa sequência reduz decisões impulsivas."},
    ],
}


ICT_VIDEO_SCRIPTS: dict[str, list[dict[str, str]]] = {
    "ict_01": [
        {"bloco": "Abertura", "tela": "AtlasQuant > Painel Mestre / Market Map", "narracao": "Nesta aula você vai aprender a dar uma função para cada timeframe. W1 e D1 servem para contexto; H4 e H1 para confirmar estrutura; M15 para timing. O erro mais comum é deixar o M15 escolher uma direção que deveria vir do macro e dos timeframes maiores."},
        {"bloco": "W1 e D1", "tela": "Market Map > W1 / D1", "narracao": "No semanal e diário, procure direção estrutural, localização no range e liquidez relevante. Esses timeframes dizem onde o mercado está dentro do contexto maior e ajudam a evitar operar contra uma estrutura dominante."},
        {"bloco": "H4 e H1", "tela": "Scanner técnico > H4 / H1", "narracao": "H4 confirma tendência e estrutura intermediária. H1 ajuda a avaliar se existe pullback, alinhamento ou preço esticado. Eles funcionam como filtro entre a ideia macro e o gatilho de execução."},
        {"bloco": "M15", "tela": "Scanner técnico > M15", "narracao": "M15 não escolhe a direção. Ele procura confirmação curta, como momentum e quebra estrutural, depois que contexto e direção já estão definidos."},
        {"bloco": "Fechamento", "tela": "Checklist W1 → D1 → H4 → H1 → M15", "narracao": "A sequência é simples: contexto maior, confirmação intermediária e gatilho curto. Se um timeframe importante entrar em conflito, a resposta mais profissional pode ser esperar."},
    ],
    "ict_02": [
        {"bloco": "Abertura", "tela": "Market Map > níveis de liquidez", "narracao": "Liquidez é uma forma de organizar onde ordens e stops tendem a se concentrar. Nesta aula vamos trabalhar com BSL acima de máximas, SSL abaixo de mínimas e o conceito de sweep."},
        {"bloco": "BSL e SSL", "tela": "PWH / PWL / PDH / PDL / Asia High-Low", "narracao": "Buy-side liquidity costuma ficar acima de máximas relevantes; sell-side liquidity abaixo de mínimas. Máximas e mínimas anteriores, extremos da Ásia e níveis iguais podem funcionar como referências de liquidez."},
        {"bloco": "Sweep", "tela": "Exemplo de varredura + retorno", "narracao": "Sweep acontece quando o preço busca um nível e depois rejeita ou retorna para dentro da estrutura. Isso é diferente de assumir que toda perfuração é reversão; o contexto e o fechamento importam."},
        {"bloco": "Contexto", "tela": "Macro + liquidez alvo", "narracao": "Com viés comprador, uma varredura de SSL seguida de recuperação pode ser mais interessante do que perseguir preço no topo. Com viés vendedor, o raciocínio se inverte."},
        {"bloco": "Fechamento", "tela": "Checklist BSL / SSL / sweep / rejeição", "narracao": "Marque primeiro onde está a liquidez. Depois espere o mercado mostrar como reage ao nível. Liquidez indica área de interesse, não entrada automática."},
    ],
    "ict_03": [
        {"bloco": "Abertura", "tela": "AtlasQuant > estrutura M15", "narracao": "BOS, CHoCH e MSS são formas de descrever mudança ou continuidade da estrutura. O mais importante é usar fechamento e swings confirmados, não qualquer pavio."},
        {"bloco": "Swings", "tela": "Swing High / Swing Low", "narracao": "Um swing high é uma máxima estrutural; um swing low é uma mínima estrutural. Esses pontos formam a referência para saber se o mercado continua a estrutura ou quebra um lado importante."},
        {"bloco": "BOS", "tela": "Exemplo de continuação", "narracao": "Break of Structure é mais útil quando confirma a direção que já vinha sendo construída. Em uma estrutura altista, romper uma máxima relevante por fechamento pode reforçar continuidade."},
        {"bloco": "CHoCH / MSS", "tela": "Exemplo de quebra contrária", "narracao": "CHoCH ou MSS aparece quando o preço rompe contra a estrutura anterior. Isso pode sinalizar mudança de comportamento, mas não deve ser usado isoladamente para inverter a direção macro."},
        {"bloco": "Fechamento", "tela": "Estrutura + contexto", "narracao": "Sempre pergunte: qual swing foi rompido, houve fechamento, qual era a estrutura anterior e isso está alinhado ao contexto? Sem essas respostas, a quebra pode ser apenas ruído."},
    ],
    "ict_04": [
        {"bloco": "Abertura", "tela": "AtlasQuant > Order Block", "narracao": "Order Block deve ser tratado como zona contextual, não como ordem institucional comprovada e nem como entrada automática. O AtlasQuant usa uma regra determinística baseada em estrutura e deslocamento."},
        {"bloco": "Origem", "tela": "Candle oposto antes do deslocamento", "narracao": "Uma zona candidata nasce a partir do último candle oposto dentro da perna estrutural que antecede uma quebra com deslocamento suficiente. Isso evita buscar candles antigos sem relação com a estrutura atual."},
        {"bloco": "Mitigação", "tela": "Zona ativa / em mitigação", "narracao": "Quando o preço retorna à zona, dizemos que houve mitigação. O retorno pode ser parcial ou profundo. O importante é observar se a zona continua válida e se a estrutura permanece alinhada."},
        {"bloco": "Invalidação", "tela": "Fechamento além da borda oposta", "narracao": "Uma zona perde validade quando o preço fecha além da borda de invalidação definida pela regra. Nesse caso, o sistema não reaproveita o Order Block antigo."},
        {"bloco": "Fechamento", "tela": "OB + premium/discount + macro", "narracao": "Use Order Block junto de localização, liquidez, FVG e direção macro. Uma zona sozinha não é motivo suficiente para executar."},
    ],
    "ict_05": [
        {"bloco": "Abertura", "tela": "AtlasQuant > FVG", "narracao": "Fair Value Gap é um desequilíbrio entre candles criado por deslocamento. Ele pode servir como área de retorno, mas não existe garantia de preenchimento ou reação."},
        {"bloco": "Formação", "tela": "Padrão de três candles", "narracao": "Em um FVG altista, existe um espaço entre a máxima do primeiro candle e a mínima do terceiro. No FVG baixista, o raciocínio é invertido. O AtlasQuant procura esse desequilíbrio em dados recentes."},
        {"bloco": "Deslocamento", "tela": "Movimento impulsivo", "narracao": "Quanto mais claro o deslocamento que criou a ineficiência, mais útil o FVG pode ser como referência contextual. Mesmo assim, ele precisa estar alinhado à estrutura."},
        {"bloco": "Validação", "tela": "FVG presente / em teste / invalidado", "narracao": "O sistema diferencia FVG ainda válido, FVG sendo testado e zona invalidada. Uma zona totalmente atravessada não deve ser tratada como se continuasse ativa."},
        {"bloco": "Fechamento", "tela": "FVG + estrutura + gatilho", "narracao": "Use FVG para melhorar localização do pullback. A entrada só ganha qualidade quando estrutura, macro e gatilho também concordam."},
    ],
    "ict_06": [
        {"bloco": "Abertura", "tela": "Market Map > sessões / Killzones", "narracao": "Killzones e divisões temporais organizam quando observar o mercado. Elas não escolhem a direção e não garantem movimento."},
        {"bloco": "Sessões", "tela": "Ásia / Londres / Nova York", "narracao": "A sessão asiática costuma construir referências importantes. Londres e Nova York frequentemente concentram mais liquidez e expansão. Por isso Asia High e Asia Low entram no mapa."},
        {"bloco": "Killzones", "tela": "Janela ativa", "narracao": "Killzone é uma janela de horário em que você presta mais atenção a liquidez, sweep e deslocamento. Fora dela, o setup pode continuar válido, mas o timing pode ser menos interessante."},
        {"bloco": "Quarterly", "tela": "Divisão temporal em quartis", "narracao": "Quarterly Theory pode ser usada como heurística temporal para dividir períodos e observar acumulação, manipulação e expansão. Ela organiza observação; não deve ser apresentada como lei de mercado."},
        {"bloco": "Fechamento", "tela": "Perfil semanal + horário + contexto", "narracao": "Use tempo para decidir quando observar, não para inventar direção. A direção continua vindo de macro, estrutura e localização."},
    ],
    "ict_07": [
        {"bloco": "Abertura", "tela": "Painel Mestre > melhor contexto", "narracao": "Agora vamos juntar tudo em uma sequência operacional. A ideia é reduzir trades impulsivos e só avançar quando as camadas principais concordarem."},
        {"bloco": "1. Macro", "tela": "Moedas / Pares / evento do dia", "narracao": "Comece identificando moeda forte contra moeda fraca, qualidade dos dados e risco de evento. Isso define a hipótese, não a entrada."},
        {"bloco": "2. Contexto", "tela": "Market Map W1/D1 + liquidez + ADR", "narracao": "Depois confirme W1 e D1, posição no range, liquidez alvo e quanto do ADR já foi consumido. Um preço muito esticado pode reduzir a qualidade mesmo com macro alinhado."},
        {"bloco": "3. Confirmação", "tela": "Scanner H4/H1", "narracao": "H4 e H1 precisam apoiar a hipótese. Se algum deles estiver claramente contra, o sistema deve priorizar espera em vez de forçar entrada."},
        {"bloco": "4. Gatilho", "tela": "M15 + sweep + BOS/CHoCH + FVG/OB", "narracao": "No M15, procure o gatilho final dentro da localização planejada. Sweep, estrutura, FVG ou Order Block podem ajudar, mas sempre como confluência, não como certeza."},
        {"bloco": "Fechamento", "tela": "Checklist Macro → Contexto → Confirmação → Gatilho → Risco", "narracao": "Se uma etapa importante falhar, pare. O objetivo do setup integrado é selecionar menos operações, mas com contexto mais claro e auditável."},
    ],
}


ATLASQUANT_VIDEO_SCRIPTS: dict[str, list[dict[str, str]]] = {
    "aq_01": [
        {"bloco": "Abertura", "tela": "AtlasQuant > Painel Mestre", "narracao": "Nesta aula você vai aprender a ler o Painel Mestre em cerca de um minuto. O objetivo é priorizar contexto, não transformar um número em sinal automático."},
        {"bloco": "Visão geral", "tela": "Cards Pares / Market Map / Scanner técnico atual / Modo", "narracao": "Comece pelos quatro cards do topo. Pares mostra o universo analisado. Market Map processado indica quantos pares têm contexto estrutural. Scanner técnico atual mostra quantos estão frescos. Modo seletivo lembra que o sistema deve filtrar, não forçar operação."},
        {"bloco": "Estado e Gate", "tela": "Tabela consolidada > Estado / Gate", "narracao": "Estado resume a condição atual: executável, quase pronto, conflito, esticado ou aguardar. Gate mede seletividade do contexto. Um score alto sem Gate adequado ou com conflito técnico não deve ser tratado como confirmação."},
        {"bloco": "Índice Integrado", "tela": "Índice Integrado / ADR usado / Liquidez", "narracao": "O Índice Integrado combina componentes para ranking operacional. Ele não é probabilidade de gain. ADR ajuda a evitar perseguir preço esticado e liquidez alvo mostra onde o mercado pode buscar interesse."},
        {"bloco": "Fechamento", "tela": "Melhor contexto consolidado + diagnóstico", "narracao": "Antes de qualquer decisão, abra o diagnóstico do melhor contexto e confirme pelo menos Estado, Gate, ADR e H4/H1/M15. Se uma camada importante falhar, mantenha WAIT."},
    ],
    "aq_02": [
        {"bloco": "Abertura", "tela": "AtlasQuant > Market Map", "narracao": "O Market Map organiza o cenário antes do gatilho. Ele responde quatro perguntas: qual é a estrutura maior, onde o preço está, qual liquidez é relevante e existe risco de evento ou exaustão de range?"},
        {"bloco": "W1 e D1", "tela": "W1 / D1", "narracao": "Leia semanal e diário primeiro. Quando os dois concordam, o contexto tende a ficar mais limpo. Quando divergem, reduza a confiança e exija mais confirmação nos timeframes menores."},
        {"bloco": "Localização e liquidez", "tela": "Premium/Discount / PWH-PWL / PDH-PDL / Asia High-Low", "narracao": "Localização importa. O mesmo gatilho pode ter qualidade diferente dependendo de onde ocorre no range. Marque a liquidez acima e abaixo antes de procurar entrada."},
        {"bloco": "Sweep, evento e ADR", "tela": "Sweep recente / Event Risk / ADR14", "narracao": "Sweep recente pode reforçar uma hipótese se estiver alinhado ao contexto. Evento de alto impacto pode bloquear execução. ADR mostra se o movimento diário já está consumido demais."},
        {"bloco": "Fechamento", "tela": "Exemplo de WAIT", "narracao": "Um Market Map correto também sabe dizer para não operar. Se estrutura, localização ou risco de evento estiverem ruins, WAIT é uma saída válida mesmo que parte da técnica esteja verde."},
    ],
    "aq_03": [
        {"bloco": "Abertura", "tela": "Painel Mestre > Scanner técnico automático", "narracao": "O scanner técnico acompanha H4, H1 e M15 e agora pode se atualizar automaticamente enquanto o AtlasQuant está aberto."},
        {"bloco": "Função dos timeframes", "tela": "H4 / H1 / M15", "narracao": "H4 mede tendência e estrutura intermediária. H1 procura alinhamento, pullback ou preço esticado. M15 procura o gatilho curto. O scanner não deve inverter sozinho uma direção macro já definida."},
        {"bloco": "Frescura", "tela": "Scanner técnico atual X/7 / Técnica atualizada", "narracao": "O indicador X de 7 mostra quantos pares têm técnica recente. Dado vencido não deve participar como se fosse atual; por isso o sistema rastreia idade e marca técnica desatualizada."},
        {"bloco": "Automação e cota", "tela": "Toggle automático / cooldown Twelve Data", "narracao": "No modo automático, o sistema verifica periodicamente quais pares estão ausentes ou vencidos e atualiza no máximo dois por ciclo. Isso protege a cota da Twelve Data e evita consultas desnecessárias."},
        {"bloco": "Fechamento", "tela": "Botão manual como reserva", "narracao": "Deixe o automático ligado para manutenção normal. Use o botão manual apenas como reserva. E lembre: H4 verde, H1 amarelo e M15 vermelho ainda é contexto incompleto, não execução."},
    ],
    "aq_04": [
        {"bloco": "Abertura", "tela": "AtlasQuant > EUA", "narracao": "A aba EUA é onde você valida a base macro do dólar. O primeiro passo não é olhar o score; é conferir a qualidade dos dados."},
        {"bloco": "Qualidade", "tela": "Qualidade dos dados / Auditoria", "narracao": "Cheque a porcentagem de qualidade e abra a Auditoria dos dados. Confirme fonte, última observação, idade e status. Dado oficial e fresco vale mais que um número bonito sem procedência."},
        {"bloco": "Indicadores", "tela": "Fed Funds / CPI / PCE / Payroll / Desemprego / PIB / Treasuries", "narracao": "Leia os indicadores em bloco. Inflação conversa com juros; emprego conversa com crescimento e Fed; Treasury 2Y ajuda a confirmar expectativa de política monetária."},
        {"bloco": "Fed", "tela": "AtlasQuant > Fed", "narracao": "Depois compare o score macro com a narrativa do Fed. Se dados sugerem pressão inflacionária e o Fed está restritivo, existe coerência. Se os dois divergem, trate a leitura com mais cautela."},
        {"bloco": "Fechamento", "tela": "Conclusão macro USD", "narracao": "Faça uma conclusão em uma frase usando pelo menos três indicadores e o tom do Fed. O objetivo é explicar o porquê da leitura, não apenas repetir o score."},
    ],
    "aq_05": [
        {"bloco": "Abertura", "tela": "AtlasQuant > Moedas", "narracao": "A aba Moedas serve para encontrar contraste relativo. Você procura uma moeda mais forte contra outra mais fraca, sempre conferindo qualidade dos dados."},
        {"bloco": "Ranking", "tela": "Ranking das moedas", "narracao": "Leia força relativa e qualidade lado a lado. Score alto com baixa qualidade deve perder prioridade para um contexto um pouco menor, mas melhor documentado."},
        {"bloco": "Formação do par", "tela": "AtlasQuant > Pares", "narracao": "Depois forme pares coerentes. Forte na base contra fraca na cotada tende a favorecer alta; fraca na base contra forte na cotada tende a favorecer baixa. Isso é hipótese macro, não ordem."},
        {"bloco": "Validação", "tela": "Matriz de Pares + Market Map + Scanner", "narracao": "A aba Pares testa a diferença macro. Em seguida, Market Map valida estrutura e localização, e o scanner verifica H4, H1 e M15."},
        {"bloco": "Fechamento", "tela": "Dois candidatos → eliminar um", "narracao": "Monte dois candidatos e elimine o pior por baixa qualidade, evento, conflito técnico ou preço esticado. O AtlasQuant deve ajudar você a excluir cenário ruim, não apenas procurar cenário bom."},
    ],
    "aq_06": [
        {"bloco": "Abertura", "tela": "AtlasQuant > Backtest / Histórico", "narracao": "Backtest e diário existem para responder uma pergunta simples: o operacional tem evidência ou só parece funcionar na memória?"},
        {"bloco": "Métricas", "tela": "Gain / Loss / Breakeven / Payoff / Drawdown", "narracao": "Taxa de acerto sozinha não basta. Um sistema pode acertar muito e ainda perder dinheiro se o loss médio for grande. Payoff, drawdown e tamanho da amostra precisam entrar na análise."},
        {"bloco": "Registro", "tela": "Diário de trade", "narracao": "Registre setup, par, direção, contexto macro, horário, risco, entrada, saída e resultado. Se possível, inclua screenshot e motivo de entrada e saída."},
        {"bloco": "Revisão", "tela": "Filtro por setup / sessão / estado", "narracao": "Revise por grupo. Compare, por exemplo, setups com Gate A contra Gate B, sessão de Londres contra Nova York ou scanner completo contra incompleto. Isso mostra onde realmente está a vantagem ou o problema."},
        {"bloco": "Fechamento", "tela": "Amostra antes de mudar regra", "narracao": "Não altere o operacional por causa de dois ou três resultados. Junte uma amostra suficiente e mude uma variável por vez. O objetivo é aprendizado mensurável."},
    ],
    "aq_07": [
        {"bloco": "Abertura", "tela": "AtlasQuant > fluxo completo", "narracao": "Nesta última aula você vai montar uma rotina diária fixa. A vantagem da rotina é reduzir improviso e impedir que o gráfico escolha a narrativa depois que o preço já andou."},
        {"bloco": "Pré-mercado", "tela": "Calendário / EUA / Fed / Moedas", "narracao": "Comece pelo calendário. Depois leia macro, Fed e força relativa. Marque eventos de alto impacto antes de escolher qualquer par."},
        {"bloco": "Seleção", "tela": "Pares / Market Map", "narracao": "Escolha poucos pares com contraste de força e boa qualidade. Confirme W1, D1, localização, liquidez, ADR e risco de evento."},
        {"bloco": "Execução", "tela": "Scanner H4/H1/M15", "narracao": "Só depois vá para H4 e H1. M15 entra por último como gatilho. Se o scanner estiver vencido, espere a atualização automática ou atualize manualmente."},
        {"bloco": "Pós-mercado", "tela": "Diário / Backtest / Histórico", "narracao": "Depois da sessão, registre o resultado e o contexto. Não avalie só se ganhou ou perdeu; avalie se seguiu o processo."},
        {"bloco": "Fechamento", "tela": "Checklist diário completo", "narracao": "A rotina final é: Calendário → Macro → Moedas → Pares → Market Map → Scanner → Decisão → Diário. Repetir a mesma sequência torna o processo auditável."},
    ],
}

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



ACADEMY_VISUALS: dict[str, dict[str, Any]] = {
    "macro_01": {
        "titulo": "Ciclo macroeconômico",
        "subtitulo": "Como crescimento, inflação, juros e moeda se conectam",
        "tipo": "flow",
        "itens": [
            ("1", "Crescimento", "Atividade acelera"),
            ("2", "Emprego", "Demanda e salários"),
            ("3", "Inflação", "Pressão de preços"),
            ("4", "Juros", "Banco central reage"),
            ("5", "Moeda", "Força relativa muda"),
        ],
        "nota": "O ciclo não é mecânico; compare sempre as duas economias do par.",
    },
    "macro_02": {
        "titulo": "Mapa da inflação",
        "subtitulo": "CPI, Core CPI, PCE e PPI em uma única leitura",
        "tipo": "grid",
        "itens": [
            ("CPI", "Consumidor", "Preço da cesta ao consumidor"),
            ("Core CPI", "Persistência", "Exclui componentes mais voláteis"),
            ("PCE", "Fed", "Medida ampla de consumo observada pelo Fed"),
            ("Core PCE", "Núcleo", "Persistência na medida PCE"),
            ("PPI", "Produtor", "Pressão de preços na origem"),
            ("Surpresa", "Mercado", "Real versus consenso"),
        ],
        "nota": "Depois do release, confirme a narrativa no Treasury 2Y e no USD.",
    },
    "macro_04": {
        "titulo": "Como ler o Fed",
        "subtitulo": "Da decisão de juros à mudança de narrativa",
        "tipo": "flow",
        "itens": [
            ("1", "Taxa", "Faixa-alvo dos Fed Funds"),
            ("2", "Comunicado", "Mudanças no texto"),
            ("3", "Dot plot", "Caminho esperado dos juros"),
            ("4", "Coletiva", "Tom hawkish, neutro ou dovish"),
            ("5", "Mercado", "Treasuries e USD reprecificam"),
        ],
        "nota": "Compare sempre a reunião atual com a anterior; a mudança costuma importar mais que o nível isolado.",
    },
    "macro_07": {
        "titulo": "Força relativa das moedas",
        "subtitulo": "Encontrar contraste antes de escolher o par",
        "tipo": "strength",
        "itens": [
            ("USD", "82", "Forte"),
            ("EUR", "67", "Moderada"),
            ("GBP", "61", "Moderada"),
            ("JPY", "38", "Fraca"),
            ("AUD", "34", "Fraca"),
            ("NZD", "31", "Fraca"),
        ],
        "nota": "Exemplo didático: score organiza comparação; não representa probabilidade de gain.",
    },
    "ict_02": {
        "titulo": "Liquidez: BSL e SSL",
        "subtitulo": "Onde estão as referências acima e abaixo do preço",
        "tipo": "liquidity",
        "itens": [
            ("BSL", "Acima das máximas", "Buy-side liquidity"),
            ("Preço", "Range atual", "Estrutura em observação"),
            ("SSL", "Abaixo das mínimas", "Sell-side liquidity"),
        ],
        "nota": "Sweep é busca de liquidez seguida de reação; perfurar um nível não garante reversão.",
    },
    "ict_03": {
        "titulo": "BOS, CHoCH e MSS",
        "subtitulo": "Continuidade versus mudança de estrutura",
        "tipo": "structure",
        "itens": [
            ("Swing", "Referência", "Máxima/mínima estrutural"),
            ("BOS", "Continuidade", "Rompe a favor da estrutura anterior"),
            ("CHoCH", "Mudança", "Rompe contra uma estrutura direcional"),
            ("MSS", "Mista", "Quebra quando a estrutura anterior não é limpa"),
        ],
        "nota": "O AtlasQuant exige fechamento além do swing confirmado e usa contexto para evitar ruído.",
    },
    "ict_05": {
        "titulo": "FVG e imbalance",
        "subtitulo": "Desequilíbrio de três candles e retorno de preço",
        "tipo": "fvg",
        "itens": [
            ("Candle 1", "Origem", "Define uma borda"),
            ("Candle 2", "Deslocamento", "Movimento impulsivo"),
            ("FVG", "Ineficiência", "Área entre Candle 1 e Candle 3"),
            ("Candle 3", "Confirmação", "Mantém o espaço do desequilíbrio"),
        ],
        "nota": "FVG é zona contextual: presente, em teste ou invalidado; não é entrada automática.",
    },
    "ict_04": {
        "titulo": "Order Block",
        "subtitulo": "Zona de origem validada por estrutura e deslocamento",
        "tipo": "ob",
        "itens": [
            ("1", "Candle oposto", "Origem dentro da perna atual"),
            ("2", "Displacement", "Movimento com força suficiente"),
            ("3", "Quebra", "BOS/CHoCH alinhado"),
            ("4", "Mitigação", "Retorno à zona"),
            ("5", "Invalidação", "Fechamento além da borda oposta"),
        ],
        "nota": "É uma heurística auditável do AtlasQuant; não prova existência de ordens institucionais reais.",
    },
    "macro_03": {
        "titulo": "Bloco do emprego",
        "subtitulo": "NFP, desemprego, salários e revisões precisam ser lidos juntos",
        "tipo": "grid",
        "itens": [
            ("NFP", "Vagas", "Criação líquida de empregos"),
            ("UR", "Desemprego", "Folga no mercado de trabalho"),
            ("AHE", "Salários", "Pressão salarial e inflação"),
            ("ADP", "Prévia privada", "Referência complementar"),
            ("Rev.", "Revisões", "Podem mudar a leitura do mês"),
        ],
        "nota": "Evite concluir pelo Payroll isolado; combine quantidade de vagas, desemprego, salários e revisões.",
    },
    "macro_05": {
        "titulo": "Treasury 2Y, 10Y e juro real",
        "subtitulo": "Como os juros de mercado confirmam ou contradizem a narrativa macro",
        "tipo": "flow",
        "itens": [
            ("2Y", "Política monetária", "Mais sensível ao caminho do Fed"),
            ("10Y", "Longo prazo", "Crescimento, inflação e prêmio de prazo"),
            ("Real", "Juro real", "Nominal menos inflação esperada"),
            ("FX", "Dólar", "Compara retorno relativo entre economias"),
        ],
        "nota": "Movimentos do 2Y após CPI, Payroll ou FOMC ajudam a confirmar a reprecificação do mercado.",
    },
    "macro_06": {
        "titulo": "Atividade econômica",
        "subtitulo": "PIB mostra o quadro amplo; ISM e PMI ajudam a enxergar a direção mais cedo",
        "tipo": "grid",
        "itens": [
            ("PIB", "Trimestral", "Crescimento amplo da economia"),
            ("ISM Mfg", "Indústria", "Difusão da atividade industrial"),
            ("ISM Serv", "Serviços", "Leitura importante para os EUA"),
            ("PMI", "Tendência", "Expansão ou contração"),
            ("50", "Linha de corte", "Acima tende a indicar expansão"),
        ],
        "nota": "Olhe nível, tendência e surpresa contra consenso; um número isolado raramente conta toda a história.",
    },
    "macro_08": {
        "titulo": "Calendário e Surprise Engine",
        "subtitulo": "Antes, durante e depois de cada release",
        "tipo": "flow",
        "itens": [
            ("1", "Anterior", "Base histórica"),
            ("2", "Consenso", "Expectativa do mercado"),
            ("3", "Real", "Dado divulgado"),
            ("4", "Revisão", "Corrige o dado anterior"),
            ("5", "Surpresa", "Real versus consenso"),
            ("6", "Confirmação", "Treasury, USD e preço"),
        ],
        "nota": "A surpresa só ganha contexto completo quando comparada ao que já estava precificado.",
    },
    "ict_01": {
        "titulo": "Top-down operacional",
        "subtitulo": "Cada timeframe tem uma função específica",
        "tipo": "flow",
        "itens": [
            ("W1", "Contexto", "Estrutura maior"),
            ("D1", "Direção", "Viés diário"),
            ("H4", "Confirmação", "Tendência intermediária"),
            ("H1", "Pullback", "Alinhamento e extensão"),
            ("M15", "Gatilho", "Timing de execução"),
        ],
        "nota": "O M15 não deve escolher a direção; ele entra por último na sequência.",
    },
    "ict_06": {
        "titulo": "Killzones e Quarterly",
        "subtitulo": "Tempo organiza observação, mas não escolhe direção",
        "tipo": "grid",
        "itens": [
            ("Ásia", "Referência", "Constrói range e extremos"),
            ("Londres", "Liquidez", "Janela ativa europeia"),
            ("NY", "Liquidez", "Janela ativa americana"),
            ("Q1–Q4", "Quarterly", "Divisão temporal heurística"),
            ("Perfil", "Semana", "Contexto temporal complementar"),
        ],
        "nota": "Use horário para saber quando observar; macro, estrutura e localização continuam definindo o contexto.",
    },
    "ict_07": {
        "titulo": "Setup integrado",
        "subtitulo": "Da hipótese macro ao gatilho, sem pular etapas",
        "tipo": "flow",
        "itens": [
            ("1", "Macro", "Forte contra fraca"),
            ("2", "W1/D1", "Contexto estrutural"),
            ("3", "Liquidez", "Alvos e localização"),
            ("4", "ADR", "Evitar preço esticado"),
            ("5", "H4/H1", "Confirmação"),
            ("6", "M15", "Gatilho"),
            ("7", "Risco", "Gestão e invalidação"),
        ],
        "nota": "Se uma camada importante falhar, o processo deve parar em WAIT.",
    },
    "aq_01": {
        "titulo": "Painel Mestre em 60 segundos",
        "subtitulo": "Priorizar contexto sem confundir ranking com probabilidade",
        "tipo": "grid",
        "itens": [
            ("Estado", "Situação", "Executável, quase pronto, conflito ou wait"),
            ("Gate", "Seletividade", "Filtro operacional"),
            ("Índice", "Ranking", "Índice integrado, não probabilidade"),
            ("ADR", "Volatilidade", "Quanto do range já foi usado"),
            ("Técnica", "H4/H1/M15", "Confirmação top-down"),
        ],
        "nota": "Abra o diagnóstico consolidado antes de qualquer decisão.",
    },
    "aq_02": {
        "titulo": "Market Map",
        "subtitulo": "Estrutura, localização, liquidez, evento e volatilidade no mesmo mapa",
        "tipo": "grid",
        "itens": [
            ("W1", "Macroestrutura", "Contexto semanal"),
            ("D1", "Estrutura diária", "Direção e range"),
            ("Loc.", "Localização", "Premium, discount e range"),
            ("Sweep", "Liquidez", "Varredura recente"),
            ("Evento", "Risco", "Calendário macro"),
            ("ADR", "Extensão", "Consumo do range diário"),
        ],
        "nota": "Market Map pode concluir WAIT mesmo quando parte da técnica está alinhada.",
    },
    "aq_03": {
        "titulo": "Scanner técnico automático",
        "subtitulo": "H4, H1 e M15 atualizados com controle de frescura e cota",
        "tipo": "flow",
        "itens": [
            ("1", "H4", "Estrutura e tendência"),
            ("2", "H1", "Pullback e extensão"),
            ("3", "M15", "Gatilho curto"),
            ("4", "Frescura", "Idade da leitura"),
            ("5", "Automático", "Fila de pares vencidos"),
            ("6", "Cooldown", "Proteção da Twelve Data"),
        ],
        "nota": "Atualiza no máximo dois pares por ciclo e mantém o botão manual como reserva.",
    },
    "aq_04": {
        "titulo": "Aba EUA + Fed",
        "subtitulo": "Da qualidade dos dados à conclusão macro do USD",
        "tipo": "flow",
        "itens": [
            ("1", "Qualidade", "Validar fonte e frescura"),
            ("2", "Inflação", "CPI e PCE"),
            ("3", "Emprego", "Payroll e desemprego"),
            ("4", "Atividade", "PIB e ISM"),
            ("5", "Treasuries", "2Y e 10Y"),
            ("6", "Fed", "Narrativa hawkish/dovish"),
        ],
        "nota": "O score deve ser explicado pelos dados; não substitua a auditoria por um número único.",
    },
    "aq_05": {
        "titulo": "Moedas e Pares",
        "subtitulo": "Do ranking relativo à seleção de um par coerente",
        "tipo": "flow",
        "itens": [
            ("1", "Ranking", "Moedas fortes e fracas"),
            ("2", "Qualidade", "Confiabilidade de cada moeda"),
            ("3", "Par", "Base contra cotada"),
            ("4", "Market Map", "Estrutura e localização"),
            ("5", "Scanner", "H4/H1/M15"),
        ],
        "nota": "O AtlasQuant também deve ajudar a eliminar candidatos ruins, não apenas encontrar candidatos bons.",
    },
    "aq_06": {
        "titulo": "Backtest, performance e diário",
        "subtitulo": "Trocar memória por evidência mensurável",
        "tipo": "grid",
        "itens": [
            ("Win rate", "Acerto", "Percentual de gains"),
            ("Payoff", "R:R", "Ganho médio versus perda média"),
            ("DD", "Drawdown", "Queda máxima"),
            ("PF", "Profit Factor", "Ganhos brutos versus perdas"),
            ("Amostra", "Tamanho", "Quantidade de trades"),
            ("Diário", "Contexto", "Setup, horário, motivo e resultado"),
        ],
        "nota": "Mude uma regra por vez e só depois de uma amostra suficiente.",
    },
    "aq_07": {
        "titulo": "Rotina diária AtlasQuant",
        "subtitulo": "Uma sequência fixa antes, durante e depois da sessão",
        "tipo": "flow",
        "itens": [
            ("1", "Calendário", "Eventos e horários"),
            ("2", "Macro", "EUA, Fed e moedas"),
            ("3", "Pares", "Contraste de força"),
            ("4", "Market Map", "Contexto e liquidez"),
            ("5", "Scanner", "H4/H1/M15"),
            ("6", "Decisão", "Gate, risco e timing"),
            ("7", "Diário", "Registrar e revisar"),
        ],
        "nota": "Repetir a mesma sequência torna o processo mais disciplinado e auditável.",
    },
}


def _academy_visual_html(lesson_id: str) -> str:
    visual = ACADEMY_VISUALS.get(lesson_id)
    if not visual:
        return ""

    items = list(visual.get("itens", []))
    kind = str(visual.get("tipo", "grid"))
    cards = []
    for tag, title, desc in items:
        tag_e = html.escape(str(tag))
        title_e = html.escape(str(title))
        desc_e = html.escape(str(desc))
        if kind == "strength":
            try:
                width = max(8, min(100, int(float(str(desc).replace("%", ""))))) if False else max(8, min(100, int(float(str(title)))))
            except Exception:
                width = 50
            cards.append(
                f'<div class="aqv-strength-row"><b>{tag_e}</b>'
                f'<div class="aqv-bar"><span style="width:{width}%"></span></div>'
                f'<em>{title_e}</em><small>{desc_e}</small></div>'
            )
        else:
            cards.append(
                f'<div class="aqv-card"><span class="aqv-tag">{tag_e}</span>'
                f'<b>{title_e}</b><small>{desc_e}</small></div>'
            )

    body_class = "aqv-strength" if kind == "strength" else f"aqv-{html.escape(kind)}"
    title = html.escape(str(visual.get("titulo", "")))
    subtitle = html.escape(str(visual.get("subtitulo", "")))
    note = html.escape(str(visual.get("nota", "")))
    return f"""
    <div class="aqv-shell" translate="no">
      <style>
        .aqv-shell{{border:1px solid rgba(70,150,220,.35);border-radius:16px;padding:18px;background:linear-gradient(145deg,#07111f,#0d2032);color:#eef7ff;margin:8px 0 14px 0}}
        .aqv-head b{{font-size:1.08rem}} .aqv-head p{{margin:.25rem 0 .9rem 0;color:#a8bfd2;font-size:.9rem}}
        .aqv-grid,.aqv-flow,.aqv-liquidity,.aqv-structure,.aqv-fvg,.aqv-ob{{display:grid;grid-template-columns:repeat(auto-fit,minmax(125px,1fr));gap:9px}}
        .aqv-card{{min-height:88px;padding:12px;border-radius:12px;background:#10283c;border:1px solid rgba(91,183,255,.24);display:flex;flex-direction:column;gap:4px}}
        .aqv-card b{{font-size:.95rem}} .aqv-card small{{color:#b7cad9;line-height:1.25}}
        .aqv-tag{{display:inline-flex;width:max-content;min-width:28px;justify-content:center;padding:2px 7px;border-radius:999px;background:#1178b8;color:white;font-size:.73rem;font-weight:700}}
        .aqv-strength{{display:flex;flex-direction:column;gap:8px}} .aqv-strength-row{{display:grid;grid-template-columns:42px 1fr 42px 70px;gap:8px;align-items:center;font-size:.84rem}}
        .aqv-strength-row em{{font-style:normal;text-align:right}} .aqv-strength-row small{{color:#a8bfd2}}
        .aqv-bar{{height:11px;border-radius:10px;background:#173247;overflow:hidden}} .aqv-bar span{{display:block;height:100%;background:linear-gradient(90deg,#1586c7,#6ec8ff);border-radius:10px}}
        .aqv-note{{margin-top:12px;padding-top:10px;border-top:1px solid rgba(255,255,255,.09);color:#b8cede;font-size:.82rem}}
      </style>
      <div class="aqv-head"><b>🖼️ {title}</b><p>{subtitle}</p></div>
      <div class="{body_class}">{''.join(cards)}</div>
      <div class="aqv-note">💡 {note}</div>
    </div>
    """



def _video_script_for_lesson(lesson_id: str) -> list[dict[str, str]]:
    return (
        MACRO_VIDEO_SCRIPTS.get(lesson_id, [])
        or ICT_VIDEO_SCRIPTS.get(lesson_id, [])
        or ATLASQUANT_VIDEO_SCRIPTS.get(lesson_id, [])
    )


def _visual_direction_for_segment(segment: dict[str, str], index: int) -> str:
    bloco = str(segment.get("bloco", "")).lower()
    tela = str(segment.get("tela", "")).strip()
    if "abertura" in bloco:
        return f"Cartela curta com o título da aula; entrar em {tela} e destacar o objetivo."
    if "fechamento" in bloco:
        return f"Voltar para {tela}; mostrar checklist final e deixar os pontos principais visíveis."
    if any(word in bloco for word in ("exemplo", "combina", "surpresa", "validação", "validacao")):
        return f"Usar {tela} em tela cheia; destacar o exemplo passo a passo com zoom apenas no campo relevante."
    if any(word in bloco for word in ("conceito", "formação", "formacao", "swings", "fomc", "2y", "10y", "pib")):
        return f"Mostrar {tela}; manter poucos elementos na tela e realçar somente o conceito explicado."
    return f"Mostrar {tela}; acompanhar a narração com destaque visual simples e sem trocar de tela desnecessariamente."


def build_storyboard(lesson_id: str) -> list[dict[str, str | int]]:
    """Transforma o roteiro completo em cenas reutilizáveis para gravação."""
    script = _video_script_for_lesson(lesson_id)
    storyboard: list[dict[str, str | int]] = []
    for idx, segment in enumerate(script, 1):
        storyboard.append({
            "cena": idx,
            "bloco": str(segment.get("bloco", f"Cena {idx}")),
            "tela": str(segment.get("tela", "")),
            "narracao": str(segment.get("narracao", "")),
            "direcao_visual": _visual_direction_for_segment(segment, idx),
        })
    return storyboard


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

        _visual_html = _academy_visual_html(lesson["id"])
        if _visual_html:
            st.markdown("##### 🖼️ Visual didático")
            st.markdown(_visual_html, unsafe_allow_html=True)

        st.markdown("##### 🎬 Roteiro do vídeo")
        for idx, item in enumerate(lesson["roteiro"], 1):
            st.markdown(f"{idx}. {item}")

        _video_script = _video_script_for_lesson(lesson["id"])
        if _video_script:
            with st.expander("🎥 Roteiro completo de gravação", expanded=False):
                for _segment in _video_script:
                    st.markdown(f"**{_segment['bloco']}**")
                    st.caption(f"🖥️ Tela sugerida: {_segment['tela']}")
                    st.write(_segment["narracao"])

        if _video_script:
            _storyboard = build_storyboard(lesson["id"])
            with st.expander("🎞️ Storyboard visual da aula", expanded=False):
                st.caption(
                    "Sequência pronta para gravação: cada cena mostra o que aparece na tela, "
                    "o texto da narração e a direção visual."
                )
                for _scene in _storyboard:
                    with st.container(border=True):
                        st.markdown(f"**Cena {_scene['cena']} — {_scene['bloco']}**")
                        st.markdown(f"**🖥️ Tela:** {_scene['tela']}")
                        st.markdown(f"**🎨 Direção visual:** {_scene['direcao_visual']}")
                        st.markdown(f"**🎙️ Narração:** {_scene['narracao']}")

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
