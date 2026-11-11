# AtlasQuant Trader — panorama competitivo e padrão de precisão seletiva — 11/11/2026

**Pesquisa documental de páginas oficiais de fornecedores. NÃO é auditoria independente de resultados, certificação de assertividade, autorização de uso de API, nem aprovação de operação real. LAB / PR em rascunho.**

## Conclusão estratégica

Não seria correto anunciar que não existe concorrente parecido. **Já existem ofertas fortes para macro + Forex + eventos + IA + notícias + sinais + análise de volatilidade**. A vantagem que devemos desenvolver e medir não é a quantidade de sinais: é a **seleção rigorosa e reproduzível de raras decisões**, com abstenção explícita e demonstração prospectiva de que a seleção acrescenta valor após custos. Nenhuma taxa de acerto foi demonstrada pelo AtlasQuant neste momento.

## Concorrentes e referência pública consultada

| Fornecedor | O que declara oferecer | Implicação para o AtlasQuant |
|---|---|---|
| **Trading Central** | Economic Insight para Forex, evento contextualizado em relação às DUAS moedas do par e impactos após 15 min, 1 h e 4 h; notícias/sentimento/sinais e integração MT4/5. | Não alegar exclusividade por comparar duas moedas ou medir reação à notícia. Diferenciar por política seletiva de abstenção demonstrada e trilha de evidência auditável. |
| **Acuity Trading** | Market/Trade/Event Intelligence, NLP de notícias, sentimento, calendário, ideias acompanhadas por analistas, histórico temporal de ideias e probabilidades direcionais de modelos. | Ser apenas um feed de IA/sentimento/probabilidade não é vantagem. Medir calibração e proporção de ideias rejeitadas; comparar qualidade de previsão. |
| **Autochartist** | Our Favourites seleciona setups ditos de alta probabilidade com dados históricos; estatísticas de desempenho, cenários para eventos econômicos, risco, volatilidade e MT5. | Filtro de alta probabilidade já existe no mercado. O AtlasQuant precisará distinguir viés macro **pré-movimento** de padrões técnicos e comprovar resultados fora da amostra. |
| **Trading Economics** | Calendário com Actual, Previous, Revised, consenso de economistas, TE Forecast próprio e API histórica point-in-time; preços e indicadores. | Serve como benchmark de qualidade de dados. Separar consenso de projeção da plataforma; verificar custo/licença antes de redistribuição comercial. |
| **QuantConnect** | LEAN, pipeline de pesquisa/backtest/paper/live, dados point-in-time, fees/spread/slippage, walk-forward e controles contra look-ahead. | Rigor estatístico e resultados prospectivos já são práticas de mercado. Usar como referência de metodologia e auditabilidade. |
| **TrendSpider** | ML Strategy Lab, IA, scanners, backtests, automações, integração técnica e fundamental. | IA e backtesting também não são exclusivos. Não virar scanner de padrões excessivos: foco em poucos vieses macro claros. |
| **Bloomberg Terminal** | Dados e notícias multiativos, macro e geopolítica, previsões e consenso econômico, análise de surpresas e reação, modelos de probabilidade de juros. | Não competir por volume de cobertura/dados institucionais. Focar numa experiência simples, transparente e econômica, com cobertura menor porém profunda. |
| **FXSSI** | Sentimento de varejo, razões comprador/vendedor, posicionamento agregado, order book e indicadores para MT4/5. | Sentimento é um possível filtro complementar; suas amostras não representam o mercado Forex inteiro e não substituem macro bilateral. |

### Fontes oficiais

- Trading Central Economic Insight (ambas as moedas, janelas): https://employee.tradingcentral.com/resources/economic-insight
- Trading Central MT4/5 e notícias: https://www.tradingcentral.com/solutions/metatrader-research-solutions
- Acuity: https://acuitytrading.com/
- Acuity AI Signals: https://knowledgebase.acuitytrading.com/en/acuity-client-knowledge-base/ai-signals
- Acuity probabilidade de sentimento: https://api.acuitytrading.com/
- Autochartist: https://www.autochartist.com/products/
- Autochartist desempenho: https://tradersupport.autochartist.com/en/knowledgebase/article/performance-statistics
- Trading Economics: https://docs.tradingeconomics.com/economic_calendar/point-in-time/
- QuantConnect: https://www.quantconnect.com/ ; https://www.quantconnect.com/docs/v2/writing-algorithms/key-concepts/research-guide
- TrendSpider: https://trendspider.com/
- Bloomberg: https://professional.bloomberg.com/products/bloomberg-terminal/research/economics/
- FXSSI: https://fxssi.com/tools/
- Verificação probabilística: https://scikit-learn.org/stable/modules/calibration.html

**Limitação da pesquisa:** capacidades e alegações de cada vendedor, não ranking de performance, preço comparável, auditabilidade contratual ou testes A/B com AtlasQuant. Não afirmar que um concorrente não possui um recurso apenas por não constar do material consultado.

## Padrão interno proposto: Precision Gate (NÃO IMPLEMENTADO NESTE CHECKPOINT)

1. **P0 — Proveniência point-in-time:** dado oficial, data observada, data publicada, hora capturada, revisão, valor ausente, fonte e licença; dado atrasado ou ambiguamente revisado => não promover.
2. **P0 — Análise bilateral de verdade:** avaliar USD vs EUR, AUD vs NZD etc. em unidades e períodos comparáveis. Checar simetria dos 28 pares e se D1 e W1 divergem; não contar 7 cruzamentos USD como 7 fontes de evidência.
3. **P0 — Separar previsão do evento, surpresa e direção do ativo:** previsão CPI/PPI não determina automaticamente USD, ouro ou índices. Estimar impacto apenas com histórico prospectivo por regime e contexto de política monetária/geopolítica.
4. **P0 — Motor de abstenção:** `SEM_VIES` / `AGUARDAR` deve ser opção normal e preferida diante de conflito, evento iminente, preço já estendido, baixa liquidez, spread alto, mudança de regime ou fonte vencida.
5. **P1 — Probability Engine apenas após ensaios:** previsão de chance de direção em horizonte claramente definido, com calibração em casos isolados no futuro, Brier/log loss + reliability diagram + intervalos de incerteza. `grade 0–10` de ranking **não** é porcentagem de acerto.
6. **P1 — Cobertura versus acerto:** reportar para cada ativo/horizonte o total de oportunidades elegíveis, número em AGUARDAR, vieses emitidos, acertos, erros, base rate, erro de calibração, regimes e distância até evento. **Nunca publicar só o percentual dos casos escolhidos retroativamente.**
7. **P1 — Comparar contra baseline:** tendência simples, direção nula, consenso público, versão sem notícias, versão sem filtro de regime, sem filtro de força. Exigir incremento estatístico fora da amostra, não apenas backtest atraente.
8. **P1 — Correlation/cost guard:** custo de spread, slippage, swap e risco; EURUSD, GBPUSD, AUDUSD em mesmo choque USD não representam apostas independentes. Limite de concentração temática, news blackout e reavaliação se preço já fez o movimento.
9. **P2 — UX clara:** Radar lista apenas raras hipóteses qualificadas; transparência no restante: 'AGUARDAR: motivo'; diferencia direção D1/W1, força relativa, probabilidade calibrada quando existir e hora/origem da última informação. Índices e XAU/USD requerem modelos/validação próprios.
10. **P2 — Contra fraude estatística:** parâmetros pré-registrados, conjuntos treino/validação/teste sem vazamento temporal, walk-forward, mudanças versionadas, arquivo da previsão anterior ao movimento, review de performance em paper antes de integração.

## Sequência de execução recomendada (sem custo adicional agora)

**Primeiro:** concluir o exercício PPI de 13/11 (duas fontes de consenso já congeladas no AM12), registrar realizado do BLS, coletar pós-evento M15 e medir reação dos sete pares, sem tratar um evento como sete ensaios independentes.

**Segundo:** confrontar a nova auditoria simétrica FX28 D1/W1 com macro oficial G8 point-in-time de verdade, sem transformar números sintéticos atuais em 'confiança'.

**Terceiro:** iniciar coorte prospectiva de decisões para 28 pares com default `AGUARDAR`, baseline e risco; desenvolver probabilidade somente se amostra por regime/horizonte sustentar calibração. O objetivo de 80%+ é meta de pesquisa, não promessa ou desempenho obtido.

**Quarto:** considerar fontes licenciadas/conectores mais caros somente quando uma comparação controlada mostrar melhora material de cobertura ou precisão líquida e quando o orçamento permitir.

## Política de comunicação

- Não prometer 90%, ausência de erros, lucro ou exclusividade absoluta sem testes independentes.
- Distinguir 'capacidade implementada e testada em LAB' de 'dados reais autenticados e disponibilizados ao usuário'.
- Relatórios comparativos devem citar fonte/versão/data; propaganda do fornecedor não prova taxa de acerto.
- **Mantém-se GO-LAB, NO-GO publicação/integração, HARD NO-GO operações**, sem assinatura, deploy ou merge automático; PR #1851 continua em rascunho. 
