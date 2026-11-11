# AtlasQuant Trader — Precision Gate coordenador (seis bloqueios integrados) — 11/11/2026

**GO-LAB somente. Não há dados oficiais/macroeconômicos autenticados conectados a este coordenador, não há sinais no Radar, trade, broker, worker, merge nem deploy. Testes exclusivamente sintéticos. PR draft #1851.**

## Problema resolvido

Até agora existiam vários filtros úteis porém isolados: simetria dos 28 pares e alinhamento D1/W1; evidências que podem vir do mesmo choque; regime de preço; extensão de mercado e spread bid/ask; e política seletiva com blackout/OOS. Isso permite testar cada uma das peças, mas não auditar facilmente a **mesma decisão** de um par percorrendo todas elas com relógios compatíveis.

**Nova implementação** (offline, recomputa verificações; não aceita uma lista de "passes" inventados):
- `atlasquant_trader_precision_gate_orchestrator_lab.py`
- `test_atlasquant_trader_precision_gate_orchestrator_lab.py`

### Estágios obrigatórios

| Etapa | Implementação realmente reexecutada | Condição para estágio passar *em pesquisa* |
|---|---|---|
| BILATERAL_D1W1 | `inspect_fx28_d1w1_agreement_lab` | Confere 8 moedas/28 pares completos, duas matrizes coerentes, D1 e W1 concordantes para o par e orientação idêntica à hipótese. |
| EVIDENCE_D1 | `inspect_fx_evidence_dependency_lab` | Raízes/famílias declaradas suficientes na janela diária; nenhum fator contradiz a direção da hipótese. |
| EVIDENCE_W1 | `inspect_fx_evidence_dependency_lab` | Mesma prova separada no corte semanal; não transformar duplicação D1/W1 do mesmo evento em novas amostras independentes. |
| MARKET_REGIME | `inspect_market_regime_veto_lab` | Duas janelas OHLC fechadas, tendência documentariamente alinhada à hipótese; faixa, transição e choque vetam. |
| M15_PRICE_COST | `inspect_fx_m15_price_cost_veto_lab` | Vinte e uma barras M15 fechadas + quote bid/ask separada, spread, extensão e choque dentro dos limites *de pesquisa* não calibrados. |
| SELECTIVE_NEWS_OOS | `assess_selective_bias_lab` | Teste de data/fonte e seleção de sinais, notícias de alto impacto, cooldown, duplicações e relatório OOS alegado — **não comprova estatística real**. |

**Pré-checagens:** ativo dentro dos 28 pares canônicos; direção ALT/BAIXA coincidente nos horizontes; hora do corte semanal <= corte diário <= revisão do calendário <= instante de decisão <= hora da auditoria; revisão documental de calendário com idade <=12h; dados de evento não verificados bloqueiam; snapshot de fator posterior ao corte bloqueia. Essas regras são de estrutura e disciplina temporal, não autenticam fontes ou consenso; limiares também não foram ajustados empiricamente.

**Saída:** sempre `operational_bias=AGUARDAR`, `calibrated_direction_probability=null`, `validated_accuracy=null`, `trade_authorized=false`, `publishable=false`; motivos detalhados em `stage_reports`, `blocking_stages`, `blocking_reasons`. Se seis etapas passam, o rótulo é somente `LAB_PRECISION_RESEARCH_CANDIDATE_UNATTESTED`: **jamais** sinal ou 80/90% comprovado.

### Atenção a dependências de dados e seleção

- Todas as pontuações de moeda e raízes econômicas ainda são **declarações do chamador/testes sintéticos**. Os SHA hexadecimais de teste não são prova de arquivo original. Nem a auditoria nem o GitHub certificam fontes macro, broker ou preços point-in-time históricos.
- Um evento CPI que explica índice do dólar, yields e sentimento deve entrar como **uma causa declarada**, não 3 indicadores independentes; e o mesmo evento avaliado em D1/W1 não vira duas previsões independentes.
- As 21 velas M15 e bid/ask são apenas contexto de possível extensão/custo. **Cotação indicativa não prova execução, profundidade de livro, comissão ou slippage**.
- A política seletiva reusa intervalos de Wilson em amostras fornecidas pelo chamador; dependência entre eventos pode invalidar uma interpretação binomial. Não basta score 8/10 ou 100 registros inventados.
- Calendário e auditoria são fornecidos pela chamada e **não autenticados independentemente**. Em produção, é indispensável ligar evidência real com hashes, horários de publicação e captura, licença, feed e históricos.
- Índices EUA, WIN/WDO, XAU/USD e mensal requerem filtros/validação próprios; **não estender automaticamente** esse pipeline Forex D1/W1.
- O coordenador não cria scheduler, compra dados ou mexe em MT5, como solicitado para o usuário no celular.

## Validação técnica

- Um conjunto novo de **18 testes unitários sintéticos integrados** cobre: cenário em que os seis filtros passam mas não há autorização; quote bid/ask ausente; spread e extensão excessivos; conflito de matriz; direção incompatível; eventos-raiz duplicados; evidência direcional contraditória; regime lateral; notícia no blackout; resultado de notícia não verificado; ausência de holdout; alegação incompleta de auditoria; calendário antigo; datas inválidas; candle ausente; pacote malformado.
- Compilação Python local passou. O workflow da PR `.github/workflows/atlasquant-trader-d1w1-offline-lab.yml` foi ampliado para rodar a nova suíte em Python 3.11 e 3.12, junto com os testes já existentes. **CI valida código, não performance financeira**.
- Mesmo quando todos os seis estágios aceitam sinteticamente, a saída permanece `AGUARDAR`, sem predição operacional.

## Próximas tarefas com maior retorno

1. **Bind de dados reais:** conectar o coordenador aos arquivos oficiais macro das oito moedas, *sem* atribuir status independente a hashes auto-declarados. A primeira sessão prospectiva já documentada é o PPI de 13/11.
2. **Preflight do preço legítimo:** captar bid/ask e M15 realmente observados no horário da decisão; documentar sessão, spread, origem do broker e custo efetivo; evitar simulação retroativa de execução.
3. **A/B prospectivo sem seleção retrospectiva:** comparar base macro vs macro+filtro de dependência vs todos os filtros, inclusive AGUARDAR, custos, cobertura e regime. A vantagem líquida precisa superar a incerteza estatística.
4. **Calibração só depois de provas suficientes** e *walk-forward*; uma pontuação não se converte em percentagem por conveniência.

**Checkpoint operacional:** GO-LAB; NO-GO integração em Radar/live; HARD NO-GO negociação real. Custo extra R$0. PR #1851 permanece draft e não mesclada.
