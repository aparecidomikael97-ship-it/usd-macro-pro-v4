# AtlasQuant Trader — FX28 + proximidade FVG/Order Block (LAB 27/10/2026)

**Pesquisa isolada. Sem produção, ordens, Worker, SEND, dados de cliente ou custo adicional.** Este bloco não altera o núcleo AION nem as seis P0; HARD NO-GO da operação continua.

## Por que esta etapa existe

Decisões do proprietário: avaliar a força das oito moedas principais sobre **todos os 28 cruzamentos Forex**; quando FVG e Order Block (OB) estiverem quase na mesma região, evitar dois alertas redundantes e apresentar a candidata com evidência superior. Preferência leve pelo FVG **somente em empate**, não por suposta taxa de acerto universal.

## Força cambial 8 × 28

- Moedas: AUD, CAD, CHF, EUR, GBP, JPY, NZD, USD, importadas do cadastro canônico `atlasquant_instrument_registry.FX_CURRENCIES`.
- Pares: os 28 símbolos oficiais de `atlasquant_instrument_registry.FX_28`, sem segunda lista de pares independente.
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

## Ponte de cache M15 existente — laboratório somente leitura

`atlasquant_trader_precision_cache_bridge_lab.py` consome **um dicionário de cache que o chamador já possui** no formato de `dados/twelve_series_v1108.json`. Não abre arquivo, não chama `cached_series`/`_load`, não busca preços, não carrega secrets, não aciona o Trader e não decide operação.

Para cada um dos 28 pares, aceita `EUR/USD|15min` (ou exclusivamente `EURUSD|15min`) com `fetched_at` e candles OHLC. Exige timestamp com fuso, OHLC finito e coerente, dois candles fechados consecutivos de 15 minutos, coleta posterior ao fechamento, ausência de timestamps duplicados, dados atuais e mesma janela de comparação em todos os pares. Uma barra ainda em formação é ignorada; nunca entra no cálculo.

Um único par ausente, antigo, inconsistente ou duplicado -> `WAIT_NO_CONTEXT`, com `missing_pairs`/`invalid_pairs` para auditoria. Os log-retornos extraídos alimentam o cálculo G8/FX28 já isolado. A saída `COMPLETE_RESEARCH_ONLY` **não** é signal, alert, probabilidade, autorização ou prova de cobertura real do cache.

**Limitação honesta:** os testes usam snapshots sintéticos no formato do cache, não são prova de que o cache operacional contenha os 28 pares, nem autenticam independentemente o provedor. A matriz macro atual de sete pares USD e o Radar não foram alterados.

## Critérios para o próximo bloco

- Conectar snapshot de dados históricos *somente leitura* com 28 séries sincronizadas, fixando timezone, ajuste de calendário, fonte, spread e timestamp de disponibilidade — sem vazar velas futuras.
- Provar que os scores dos detectores foram gerados exclusivamente com candles conhecidos no momento da decisão; preservar FVG/OB rejeitados no relatório de auditoria.
- Backtest/forward Paper separados por par, sessão e M15/M30/H1/H4/D1/W1, com fricção, embargo temporal, caminhada fora da amostra e comparação contra base sem deduplicação.
- Reportar precisão, cobertura, falso positivo, drawdown, expectativa, amostra, intervalo de confiança e conflitos de força/estrutura. Não otimizar em dados de teste.
- Só considerar integração aos radares após revisão dos critérios e dos resultados. Nenhum sinal real ou operação automática decorre de CI verde.

## Evidência desta PR

`test_atlasquant_trader_precision_lab.py` cobre **38 testes determinísticos** (23 do motor + 15 da ponte): 28 combinações, recuperação de forças sintéticas, soma zero, inconsistência triangular exposta, falhas fechadas de dados, sobreposição FVG/OB, preferência condicionada, isolamento por mercado/TF/direção, zonas invalidadas, duplicação e invariância da ordem.

**Resultado local após a ponte:** 38/38. GitHub Actions deverá confirmar Ubuntu + Windows. Testes sintéticos não são ganho financeiro nem acurácia de sinal.
