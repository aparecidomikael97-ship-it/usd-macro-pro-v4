# Trader — reforço de autenticidade do lote de viés sintético (LAB 03/11/2026)

## Objetivo
Para antecipar o mercado de maneira honesta, o sistema deve diferenciar **lote sintético de pesquisa** de **previsão realmente sustentada por dados confiáveis**. A amostra matemática e um resultado OOS sintético não demonstram 90% de probabilidade de alta ou baixa.

## Falha no contrato anterior
`evaluate_synthetic_bias_batches_lab` verificava a identidade, quantidade, método e horários de alguns campos das 84 previsões sintéticas, mas **não exigia o esquema completo nem revalidava** os marcadores de procedência falsificáveis:
- era possível o chamador injetar `market_verified=true` em linhas ou `market_data_verified=true` no lote sem que o guardião barrasse;
- campos extras como `claimed_accuracy_probability` ou `probability_90_pct` podiam acompanhar o objeto sem uma recusa contratual;
- os totais `counts` podiam ser adulterados sem detecção;
- `evidence_kind` e o relógio de evidência não recebiam validação completa nesse ponto de entrada.

Embora as saídas globais continuassem rotuladas sintéticas, essas lacunas poderiam **contaminar consumidores de dados brutos** com afirmações de origem inexistente.

## Correção
O próprio `atlasquant_trader_bias_forecast_bridge_lab.py` agora exige:
1. chaves exatas de lote e linha;
2. flags de market/durable/Worker/scheduler/trade explicitamente **False** e `no_settlements_seen_by_issuer=True`;
3. quatro categorias de contagem por D1/W1/MN1 consistentes com as 84 linhas reais do lote;
4. `evidence_kind` limitado a `SYNTHETIC_INPUT` ou `ABSENT_POLICY`; evidência ausente sempre `AGUARDAR` com horário de emissão;
5. horário da evidência válido e anterior ou igual à emissão, sem extras de probabilidade;
6. motivo textual limitado e não vazio.

Foram adicionados **18 novos testes (17 de adulteração e 1 de regressão)** a `test_atlasquant_trader_bias_forecast_bridge_lab.py`. A suíte já existente permanece vinculada ao Quality do GitHub.

Isso protege **consistência interna**. Não substitui assinatura externa, dados de mercado reais, instantâneos de preços históricos, consenso macro pré-evento ou testes prospectivos fora da amostra. Lotes continuam explicitamente sintéticos, nunca ordens.

**HARD NO-GO:** sem merge, deploy, Worker, scheduler, custeio adicional, API, corretora, sinais operacionais ou mudança visual.
