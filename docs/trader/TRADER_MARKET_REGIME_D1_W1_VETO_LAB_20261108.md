# AtlasQuant Trader — P0/P1: filtro de regime de mercado D1/W1 (LAB)

**Checkpoint 08/11/2026.** O módulo `atlasquant_trader_market_regime_veto_lab.py` é um filtro **experimental e sem consulta de rede**. Não prevê direção por si só, não negocia, não agenda rotinas, não altera o aplicativo e não atribui probabilidades de acerto. Integra-se apenas ao diagnóstico dos 28 pares G8; índices WIN/WDO/US500/NAS100/US30 exigem avaliação própria.

## Motivação

Mesmo quando juros e surpresas econômicas parecem favorecer um viés, o preço pode estar lateralizado, mudar de regime ou registrar uma explosão de volatilidade. Este filtro **pode vetar uma hipótese documental**, mas jamais liberá-la automaticamente.

## Entradas e regras

- Exige duas séries independentes de **velas fechadas**, uma D1 e outra W1, registradas sem informações futuras em relação a seus **respectivos cortes de decisão**.
- Cada vela exige hora de abertura, fechamento, captura declarada, OHLC coerente e SHA-256 alegado. Isso **não autentica** o horário nem a origem: é uma declaração fornecida pelo chamador. Histórico baixado *hoje* não pode ser fingido como captura disponível em um corte histórico anterior.
- Rejeita dados incompletos, candles ainda abertos, registros futuros, datas sem fuso, fontes sem hash válido, candles repetidos ou fora de ordem e gaps sem revisão. **Calendário da corretora não foi verificado.**
- Janela experimental: **20 alterações de fechamento**. O índice de eficiência (ER) é `|fechamento_atual − fechamento_20_barras_atrás| / soma(|variações_consecutivas|)`; não é probabilidade.
- `ER >= 0,55`: tendência documental; bloqueia se a direção contradiz o candidato. `ER <= 0,30`: lateralização, bloqueia. Entre esses valores: transição, bloqueia.
- Se a amplitude verdadeira (*True Range*) da última vela for >= **2,5x** a mediana das 20 anteriores: `VOLATILITY_SHOCK`, bloqueia, sem deduzir automaticamente aversão a risco.
- Requer **ambos os períodos** sem veto. Uma tendência alinhada em D1 e W1 devolve `LAB_REGIME_ALIGNMENT_DOCUMENTARY_NOT_LIVE`, jamais compra, venda, acurácia ou resultado comercial.
- Os cortes e limiares não foram otimizados. Antes de qualquer uso prospectivo, registrar as escolhas e medir **valor incremental** em *walk-forward* intocado, comparando o motor com e sem filtro, com cobertura de sinais, intervalos de confiança e possível dependência temporal.

## Testes e limitações

- `test_atlasquant_trader_market_regime_veto_lab.py`: **24 testes sintéticos locais aprovados**, incluindo os 28 crosses, tendência nos dois sentidos, lateralização, transição, volatilidade anormal, vazamento temporal, dados futuros, séries incompletas, extremos decimais e índice fora do escopo.
- Durante os testes locais foram usados substitutos mínimos dos dois imports do repositório (`atlasquant_fx_universe` e `BiasObservation`); **a suíte integral da PR e os snapshots reais MT5 não foram executados neste ambiente**.
- A lacuna histórica do GBPNZD D1 em **30/09/2025** e a identidade/calendário do broker permanecem não atestadas; nenhuma lacuna recebe vela sintética para backtest.
- Ainda não é possível classificar **risk-on/risk-off** apenas com o movimento de um par: para isso serão necessários sinais independentes de diversas classes de ativos com fontes e horários auditáveis.

## Segurança e governança

`operational_bias=AGUARDAR`, `publishable=False`, `trade_authorized=False`, `worker_enabled=False`, `scheduler_enabled=False`, `validated_directional_accuracy=None`, `new_cost_brl=0`. O filtro jamais aumenta a nota de 0–10 nem converte ER em probabilidade. Seus metadados devem ser usados **apenas como veto**, não como autorização.

**Próximo passo real:** executar a bateria integrada sobre dados arquivados com cortes históricos demonstráveis, comparar taxa de acerto *fora da amostra* e a proporção de dias em **AGUARDAR**. Se o filtro reduzir cobertura sem acrescentar precisão, ajustá-lo apenas no conjunto de treinamento ou descartá-lo.
