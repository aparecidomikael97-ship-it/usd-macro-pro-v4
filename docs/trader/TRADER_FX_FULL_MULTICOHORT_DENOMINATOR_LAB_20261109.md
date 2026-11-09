# AtlasQuant Trader — histórico de rodadas D1/W1 sem escolha retrospectiva (LAB)

**09/11/2026.** Este é apenas um módulo de contabilidade de pesquisa. O AM12 estava **offline** quando o trabalho começou; não foram abertos candles reais, não foram fixadas previsões reais, não houve postagem de precommit, cálculo de retorno, ordem ou alteração na interface. O código não faz rede, não usa MetaTrader5 e não escreve arquivos. A PR #1851 deve continuar **draft**.

## Por que agora?

O módulo `atlasquant_trader_fx_census_bridge_guard_lab.py` garante que uma rodada de **28 pares × D1/W1 = 56 posições** não perdeu `ALTA`, `BAIXA` elegível, `AGUARDAR` ou veto. Mas a avaliação de assertividade exige **muitas rodadas**, nunca uma única rodada artificialmente expandida em 56 sinais independentes.

O módulo `atlasquant_trader_fx_multicohort_ledger_lab.py` recebe uma lista de `FrozenFxCohort(roster, census, hypotheses)` e uma sequência de IDs de rodadas **declarada pelo chamador**. Para **cada** rodada:

1. Recria e valida a assinatura local e as 56 posições do plano e do censo.
2. Exige 100% das oportunidades de baseline elegíveis, **inclusive as rejeitadas pelo filtro de regime**, com par, direção, alvo e horário imutáveis dentro do contrato.
3. Rejeita uma rodada omitida, duplicada, fora de ordem, versão da regra alterada no mesmo conjunto ou alvo repetido sob novo ID.
4. Acumula contagens de `AGUARDAR`, direções não elegíveis, elegíveis, vetadas e retidas, verificando o fechamento matemático de todos os **56 × N** registros.
5. Devolve **exatamente 56 grupos** — um por par/horizonte —, inclusive grupos vazios; ordena as hipóteses pelo horário-alvo para posterior uso na ponte MT5 sem misturar pares nem D1/W1.

Se uma só rodada for inválida, o retorno é `LAB_MULTI_COHORT_LEDGER_BLOCKED`, sem grupos e sem taxa de acerto. Uma rodada completamente `AGUARDAR` continua obrigatória no total, embora não gere hipótese direcional.

O limite de até **240 rodadas** permite acumular um número potencialmente suficiente de observações **por par e horizonte** para os limiares mínimos de pesquisa. Ele **não** comprova independência estatística, inexistência de correlação entre pares, período amostral suficiente, nem desempenho.

## Fonte de verdade e limites críticos

- A sequência de IDs é entregue pelo chamador: **não há âncora externa verificando que essa era a lista completa antes dos acontecimentos**. Portanto a seleção retrospectiva de rodadas **ainda pode ocorrer na origem**. É indispensável registrar prospectivamente essa sequência/agenda em fonte externa e observar quando cada plano e censo foram publicados.
- Hash SHA-256 de documento local não autentica automaticamente hora, corretora, fonte macroeconômica, histórico de vintages, regime ou custo operacional.
- O ledger **não consulta ou pontua candles**. Seus `groups` são apenas pacotes para uma etapa de avaliação futura, e a aplicação deve impedir que apenas os grupos com bom desempenho sejam divulgados.
- A comparação exige janelas OOS disjuntas declaradas antes do teste e limites estatísticos do `atlasquant_trader_regime_increment_benchmark_lab.py`. Os 56 grupos são subpopulações correlacionadas, não 56 observações independentes de acerto.
- Relógio semanal MT5, horários do servidor, mudança DST e lacunas seguem pendentes de verificação da corretora no AM12. Não deslocar timestamps ou preencher preços.
- A meta de 65–70% continua **hipótese não demonstrada**. Nenhuma probabilidade calibrada ou taxa de acerto real é produzida.

## Teste e integração

```bash
python -m unittest -q \
    test_atlasquant_trader_fx_multicohort_ledger_lab \
    test_atlasquant_trader_fx_census_bridge_guard_lab \
    test_atlasquant_trader_fx_trial_census_lab \
    test_atlasquant_trader_mt5_closedbar_outcome_lab \
    test_atlasquant_trader_regime_increment_benchmark_lab \
    test_atlasquant_trader_mt5_paired_outcome_bridge_lab \
    test_atlasquant_trader_fx_census_github_anchor_lab \
    test_atlasquant_trader_w1_ny17_dst_guard_lab
```

**176 testes sintéticos locais aprovados**, sendo **21 do novo acumulador**. O teste local usa um *stub* exclusivamente do universo FX para permitir teste isolado; **o stub não deve ser enviado ao repositório**. O GitHub tem o módulo canônico `atlasquant_fx_universe.py` e testará o código na integração real via workflow da PR.

## Próximo bloqueio real

O projeto precisa de um **manifesto de rodadas prospectivamente fixado**, das âncoras GitHub observadas antes das velas, de horário e preço MT5 confiáveis e de macro com originais ponto-no-tempo antes de publicar qualquer comparação real. O estado operacional permanece `AGUARDAR`, `publishable=False`, `trade_authorized=False`, custos novos R$ 0.
