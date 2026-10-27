# AtlasQuant Trader — FX28 + proximidade FVG/Order Block (LAB 27/10/2026)

**Pesquisa isolada. Sem produção, ordens, Worker, SEND, dados de cliente ou custo adicional.** Este bloco não altera o núcleo AION nem as seis P0; HARD NO-GO da operação continua.

## Por que esta etapa existe

Decisões do proprietário: avaliar a força das oito moedas principais sobre **todos os 28 cruzamentos Forex**; quando FVG e Order Block (OB) estiverem quase na mesma região, evitar dois alertas redundantes e apresentar a candidata com evidência superior. Preferência leve pelo FVG **somente em empate**, não por suposta taxa de acerto universal.

## Força cambial 8 × 28

- Moedas: AUD, CAD, CHF, EUR, GBP, JPY, NZD, USD.
- Pares: 28 combinações não redundantes, em símbolos de negociação convencionais.
- Fonte exigida: log-retorno para o **mesmo intervalo sincronizado e mesma origem**, com horário UTC consciente, prazo máximo de atualização explícito e todos os 28 pares presentes.
- Estimador: solução de mínimos quadrados da rede completa de oito moedas. Para moeda c: **S(c) = soma dos log-retornos assinados dos sete pares envolvendo c / 8**. A força é relativa (soma das oito forças = zero).
- Direção contextual do par X/Y: **S(X) − S(Y)**. Não se trata de um gatilho de entrada; não confundir força de moeda com retorno esperado.
- Discrepâncias entre cotação cruzada e força estimada ficam em `residual_by_pair` e `max_abs_residual` para posterior auditoria, sem ocultar conflito.
- Falta de par, timestamps incompatíveis, feed divergente, preço futuro, retorno não finito ou dado expirado => **WAIT_NO_CONTEXT** sem preencher lacunas artificialmente.

## FVG versus Order Block próximos

1. O detector de origem precisa fornecer estrutura de zona válida: par, timeframe, direção, limites, identidade única, invalidação, idade e `detector_quality_score` em 0–1.
2. Regiões só competem se estiverem no mesmo par, timeframe e direção. Zonas anuladas não são selecionadas.
3. A distância entre intervalos de preços é comparada com ATR da mesma escala. Padrão de laboratório `max_gap_atr=0.15` é **hipótese ajustável**, não parâmetro otimizado nem comprovado.
4. O maior score do detector é a candidata principal. **Empate real: FVG vence OB**. Em seguida, mais recente e identificador determinístico desempatarão.
5. A regra só suprime regiões suficientemente próximas da candidata já selecionada; não elimina a terceira zona que é distante da vencedora só por formar uma cadeia de zonas.
6. Sem ATR confiável, score válido ou ID único, gera erro fechado. Nenhuma decisão pode ativar execução.

**Atenção:** `detector_quality_score` é apenas um campo de entrada. Esta etapa **não** define seus pesos, não prova que o FVG é mais assertivo que OB, não calcula probabilidade calibrada e não incorpora dados de mercado em tempo real. Isso requer prova empírica fora da amostra.

## Critérios para o próximo bloco

- Conectar snapshot de dados históricos *somente leitura* com 28 séries sincronizadas, fixando timezone, ajuste de calendário, fonte, spread e timestamp de disponibilidade — sem vazar velas futuras.
- Provar que os scores dos detectores foram gerados exclusivamente com candles conhecidos no momento da decisão; preservar FVG/OB rejeitados no relatório de auditoria.
- Backtest/forward Paper separados por par, sessão e M15/M30/H1/H4/D1/W1, com fricção, embargo temporal, caminhada fora da amostra e comparação contra base sem deduplicação.
- Reportar precisão, cobertura, falso positivo, drawdown, expectativa, amostra, intervalo de confiança e conflitos de força/estrutura. Não otimizar em dados de teste.
- Só considerar integração aos radares após revisão dos critérios e dos resultados. Nenhum sinal real ou operação automática decorre de CI verde.

## Evidência desta PR

`test_atlasquant_trader_precision_lab.py` cobre **23 testes determinísticos**: 28 combinações, recuperação de forças sintéticas, soma zero, inconsistência triangular exposta, falhas fechadas de dados, sobreposição FVG/OB, preferência condicionada, isolamento por mercado/TF/direção, zonas invalidadas, duplicação e invariância da ordem.

**Resultado local inicial:** 23/23. GitHub Actions independente deverá confirmar Ubuntu + Windows. Testes sintéticos não são ganho financeiro nem acurácia de sinal.
