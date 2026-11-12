# AtlasQuant Flow — especificação aprovada para desenvolvimento futuro
**Data:** 2026-11-10. **Situação:** PLANEJADO / LAB / NÃO IMPLEMENTADO / SEM TRADE.  
**Prioridade atual preservada:** AtlasQuant Trader macro G8, 28 pares, D1/W1, XAU/USD e índices; não desviar esforços de dados verificáveis, validação P-I-T e desempenho fora da amostra.

## Objetivo
Indicador AtlasQuant Flow para detectar **início qualificado de expansão** e **continuação confirmada**, evitando perseguir preço esticado, comprar topo ou vender fundo. Complementa — não substitui — AtlasQuant Trader. ICT (OB/FVG/liquidez) é contexto opcional, não condição compulsória de toque/reteste.

## Plataforma
**Fase 1: TradingView / Pine Script v6 — somente indicador visual, sem ordens.** Prototipagem, COT nativo quando símbolo suportado, backtest visual e alertas.  
**Fase 2: MetaTrader 5 — versão MQL5 integrada a serviço/EA auxiliar** para fontes externas. Indicador MQL5 não pode usar WebRequest diretamente; EA/serviço auxiliar com permissões explícitas e somente leitura.  
**Integração:** TV -> AtlasQuant por webhook de alerta, com autenticação/validação no servidor; a via inversa (AtlasQuant -> Pine) **não é um HTTP GET livre no Pine**; não inventar compatibilidade. Sem conta, chave, credencial ou automação de ordem.

## Três inteligências desacopladas
1. **Direção (AtlasQuant Trader):** viés macro, surpresa de notícia, expectativas de juros, forças relativas das duas moedas, geopolítica, contexto/regime. Evidência com fonte, instante de publicação, captura, validade e risco de revisão. Se indisponível, mostrar `MACRO_NAO_VALIDADO` e não fingir consenso. O indicador protótipo pode operar só como *pesquisa técnica*, explicitamente marcado.
2. **Condição do preço:** ATR e deslocamento em ATR, ADR/range do dia, distância VWAP (quando confiável) e EMAs, faixas/distribuições estatísticas, máximas/mínimas e liquidez, distância ao obstáculo, risco-retorno; distinguir **esticado** de **reversão comprovada**. Não chamar tecnicamente esticado de "preço justo" ou "caro/barato fundamental".
3. **Momento da entrada:** (A) início qualificado: compressão prévia + aceleração emergente + alinhamento de direção e espaço; (B) continuação confirmada: rompimento com fechamento/aceitação de preço, impulso e confirmação sem comprar/vender após movimento excessivo. Dois módulos parametrizáveis com abstenção.

## COT: contribuição, limites e implementação
- CFTC Commitments of Traders: dados **semanais de futuros**, posições de terça divulgadas geralmente sexta **15:30 New York** (feriados podem atrasar). **Nunca** iniciar o dado histórico na terça quando só se tornou público na sexta.
- Forex financeiro: preferir relatório **Traders in Financial Futures (TFF)** para contratos financeiros quando houver, separando Asset Managers, Leveraged Funds, Dealers, Other. Metais: estudar categoria apropriada (ex.: Disaggregated), sem misturar categorias arbitrariamente. OI: total de contratos em aberto.
- Métricas propostas **por grupo e contrato**: `net = long - short`, `net_pct_OI = 100*net/OI` se OI válido, `delta_net` semana a semana, percentil/índice histórico (ex.: 52/156 semanas) se cobertura suficiente. Normalizar antes de comparar séries. **Extremo não é ordem de reversão**; divergência não prova exaustão.
- Usar TradingView oficial "Commitment of Traders: Financial Metrics" e `LibraryCOT` quando suportado; inspecionar API e versão real, compilar; **não inventar chamadas**. `no data` = `COT_INDISPONIVEL`; nunca substituir silenciosamente por USD, DXY ou outro instrumento.
- Mapeamento por contrato CFTC e sentido da cotação: verificar Forex spot ↔ futuros (ex.: EURUSD e USDJPY têm sentidos diferentes); **28 cruzamentos não equivalem a 28 relatórios independentes**. Para XAU/USD procurar COT ouro específico. WIN/WDO exigem fonte B3 própria, sem equivalente automático do COT americano.
- Classificar como **filtro semanal opcional** de posicionamento/saturação. Não exigir para intraday, não somar como se independente de macro/fluxo, não fornecer "probabilidade 90%" por heurística.

## Regras de saída
Estados: `AGUARDAR`, `OBSERVAR_ALTA`, `OBSERVAR_BAIXA`, `COMPRA_CONFIRMADA`, `VENDA_CONFIRMADA`, `BLOQUEADO_ESTICADO`, `BLOQUEADO_RISCO`, `DADOS_INSUFICIENTES`.  
Mostrar **viés** separado de **entrada**: `VIÉS_ALTA / ENTRADA_BLOQUEADA_ESTICADO` é comportamento válido. Alertas raros: antirrepetição por evento/barra, cooldown, conflito D1/W1, volatilidade/notícia, espaço até obstáculo, relação risco-retorno e risco correlacionado G8.

## Filtros anti-esticamento
Não usar threshold mágico universal. Parametrizar: deslocamento desde origem da pernada em ATR, porcentagem da ADR já percorrida, distância percentual/em ATR de VWAP/EMA e faixa, proximidade do próximo nível, candle de clímax e desaceleração. Calibrar por ativo/sessão, sem lookahead e sem concluir reversão só porque esticou. Exceções pós-notícia exigem testes próprios.

## Interface
No gráfico: marca de pré-alerta e confirmação, painel mínimo com TF, direção macro (`VERIFICADO / NÃO VALIDADO`), D1/W1, início/confirmado, condição do preço (favorável/esticado), COT (grupo, relatório, data de referência, **data real de publicação**, estado de validação), espaço/R:R, razão explícita do veto. Paleta discreta, sem poluição de OB/FVG. Configurações para M15 principal, M5/M30/H1/H4 confirmação, sessão/timezone do ativo.

## Segurança, testes e critérios
- Pine v6 completo e compilável, sem placeholders para lógica principal, sem desenhos deslocados/repaint, `barstate.isconfirmed` quando aplicável, `request.security(...lookahead_off)` e checagem de disponibilidade dos dados de maior TF.
- Evidência macro/COT só consumida **após publicação verificável**; horário de consulta ≠ divulgação. Se TradingView não fornecer instante histórico confiável de publicação do COT, não usar para prova estatística P-I-T e indicar limitação.
- Proibir ordens e qualquer integração de conta. Alertas somente de estudo. Backtest da estratégia companheira separado, incluindo spread, slippage, comissões, walk-forward e período fora de amostra. Relatar **taxa de acerto + payoff + drawdown + cobertura/abstenção + nº de sinais + baseline**, segmentado por modo/ativo, não prometer 80–90%.
- Primeiro protótipo apenas **EURUSD em M15**, depois validar outros G8, índices e ouro; sem alegar equivalência de símbolo / feed até verificar.
- Revisão de código antes de qualquer merge; manter a PR de laboratório em rascunho. Nenhum deploy, cobrança, worker ou operação real.

## Fontes verificadas
- [CFTC — descrição COT, TFF e categorias](https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm)
- [CFTC — calendário de divulgação](https://www.cftc.gov/MarketReports/CommitmentsofTraders/ReleaseSchedule/index.htm)
- [TradingView — COT e indicadores oficiais](https://www.tradingview.com/support/solutions/43000502609-i-d-like-to-know-more-about-the-commitments-of-traders-cot-reports/)
- [TradingView — LibraryCOT](https://www.tradingview.com/script/ysFf2OTq-LibraryCOT/)
- [TradingView — alerta webhook](https://www.tradingview.com/support/solutions/43000529348-how-to-configure-webhook-alerts/)
- [MQL5 — WebRequest](https://www.mql5.com/en/docs/network/webrequest)
