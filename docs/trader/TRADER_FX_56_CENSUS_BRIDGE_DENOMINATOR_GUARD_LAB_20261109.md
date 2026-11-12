# AtlasQuant Trader — proteção contra omissão de vieses no comparador histórico

**09/11/2026 — LAB, somente leitura.** O computador AM12 estava offline. Não foram coletados candles reais, divulgadas previsões, alterado o aplicativo ou enviadas ordens. O desempenho de mercado permanece **não mensurado**.

## Falha metodológica identificada

O manifesto prospectivo registra **56 posições** por rodada: os 28 pares Forex × D1/W1. Ele inclui `ALTA`, `BAIXA` e `AGUARDAR`, com abstinências e vetos explícitos. O comparador histórico, por outro lado, recebe uma lista de `RecordedFxHypothesis` definida pelo chamador; anteriormente essa lista não era reconstituída e confrontada com **todas** as posições elegíveis do censo congelado.

Um avaliador descuidado poderia passar apenas oportunidades favoráveis, retirar aquelas marcadas `regime_veto=True` ou alterar o lado de um candidato. O comparador isolado não conseguiria provar que o denominador utilizado era completo. Isso não é um bug de preço, mas é uma lacuna relevante de **integridade estatística e risco de seleção retrospectiva**.

## Componente novo

`atlasquant_trader_fx_census_bridge_guard_lab.py` recebe o plano `FrozenBlob`, o censo `FrozenBlob`, a lista de hipóteses direcionais já congeladas e o horário da auditoria. Revalida os dois objetos usando as rotinas existentes do censo, deriva **sem aceitar IDs declarados pelo avaliador** todas as oportunidades cujo `baseline_eligible=True`, inclusive `regime_veto=True`, e exige correspondência exata de:

- ID, par, horizonte, lado, abertura da vela e status de veto;
- registro da decisão, congelamento da hipótese, e ordenação temporal em relação ao plano e ao alvo;
- tipos e formato dos hashes de fontes alegados.

Mantém contadores separados de `AGUARDAR`, direções não elegíveis, oportunidades baseline elegíveis, retidas e vetadas pelo regime, sempre com **56 posições no censo**. Se um único candidato elegível faltar ou uma decisão for alterada, bloqueia a reconciliação inteira. Inverte a ordem da entrada sem alterar o resultado.

**Importante:** `directional_noneligible` (ALTA/BAIXA com `baseline_eligible=False`) é diferente de `AGUARDAR`; ambos são excluídos da avaliação dos *vieses emitíveis*, mas ficam documentados. O veto de regime **não** exclui a oportunidade da comparação do baseline: ela precisa ser contabilizada entre as rejeitadas.

A rotina é uma **barreira de contabilidade**, não um avaliador de preço. Um censo contém apenas uma oportunidade por par/horizonte; a comparação estatística exige **várias rodadas prospectivas**, janelas cronológicas fixadas antecipadamente, vigência das regras, benchmark justo e amostras suficientes. Este componente retorna sempre `benchmark_sufficient_sample=False`, `validated_directional_accuracy=None`, `operational_bias=AGUARDAR`, `trade_authorized=False`, `publishable=False`.

## O que não foi comprovado

- A existência das previsões antes dos movimentos. Os hashes e horários ainda são **alegações do chamador**; não são autenticação da plataforma GitHub.
- A autenticidade das fontes macroeconômicas e do relógio/servidor MT5.
- Que cada histórico estava disponível, na versão correta, no momento da decisão.
- Rentabilidade após spread, slippage e custo, probabilidade calibrada, vantagem estatística ou precisão real.

Também não é correto usar uma amostra com 56 posições misturando 28 pares e D1/W1 para afirmar uma taxa única de acerto. As métricas devem permanecer **separadas por par e horizonte**, com análise posterior de dependência entre os cruzamentos e de acurácia condicionada à cobertura.

## Testes

```bash
PYTHONPATH=.:_testdeps python -m unittest -q \
  test_atlasquant_trader_fx_census_bridge_guard_lab \
  test_atlasquant_trader_fx_trial_census_lab \
  test_atlasquant_trader_mt5_paired_outcome_bridge_lab \
  test_atlasquant_trader_regime_increment_benchmark_lab \
  test_atlasquant_trader_fx_census_github_anchor_lab \
  test_atlasquant_trader_w1_ny17_dst_guard_lab \
  test_atlasquant_trader_mt5_closedbar_outcome_lab \
  test_atlasquant_mt5_d1w1_minimal_clock_probe_lab
```

**168 testes sintéticos locais aprovados** nessas oito suítes; 19 são novos. Foram cobertos 56 AGUARDAR, 56 elegíveis, mistura de rejeições, `baseline_eligible=False`, remoção do veto, duplicação, troca de ativos/horizontes, direção, horário de previsão, horário anterior ao plano, datas e hashes adulterados, reversão da ordem e modo permanente NO-GO. Nenhum teste usou cotações reais ou acesso de negociação.

A suíte de GitHub Actions `atlasquant-trader-d1w1-offline-lab.yml` deve compilar e testar esse módulo junto aos contratos D1/W1 já existentes, em Python 3.11 e 3.12. A execução remota tem de ser **verificada nos logs**, não presumida por existir um YAML na branch.

## Próxima ordem de trabalho

1. Recuperar o acesso ao AM12 sem coleta desnecessária; validar broker, padrões D1/W1, DST e gaps.
2. Registrar de verdade o primeiro plano prospectivo e, depois, o censo completo com **duas âncoras externas** anteriores às velas.
3. Acumular rodadas com os 56 slots contabilizados e fontes macro ponto-no-tempo verificáveis.
4. Só então avaliar os resultados do MT5, com cobertura e erros reportados separadamente; índices seguem contrato próprio.

**Sem nova cobrança, merge, deploy, ordem, sinal automático ou atualização do Radar de produção.**
