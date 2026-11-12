# AtlasQuant Trader — placar histórico de previsões (LAB)

**Data:** 08/11/2026. **Estado:** pesquisa offline, sem série histórica de
resultados reais comprovada nesta etapa.

## Propósito

Medir **o erro da previsão de um indicador econômico** em comparação com o
consenso de analistas e o valor anterior. O objetivo é construir uma futura
avaliação de eventos como CPI/PCE/NFP, antes de sequer estudar se isso melhora
o viés dos 28 pares Forex ou dos índices.

### Arquivos

- `atlasquant_trader_event_forecast_benchmark_lab.py`
- `test_atlasquant_trader_event_forecast_benchmark_lab.py`

## Regras incorporadas

1. Cada caso exige uma previsão previamente congelada. O histórico recusa
   valores capturados depois do instante de avaliação.
2. A mesma divulgação não pode ser contada duas vezes: identificador do evento
   e combinação moeda/indicador/período/unidade são únicos.
3. Só compara erros de **um mesmo indicador com a mesma unidade** por rodada.
   Não calcula média entre, por exemplo, CPI percentual e NFP em pessoas.
4. Se a notícia ainda não aconteceu, conta como **aguardando**. Se o evento já
   passou sem valor real informado, conta como **resultado ausente**. Um valor
   futuro ou com cronologia incoerente **bloqueia** a avaliação.
5. O módulo diferencia previsões com modelo e sem modelo. Se faltar modelo,
   algum resultado ou a amostra mínima, **oculta o placar agregado**.
6. Por padrão, exige pelo menos **30 divulgações pareadas, todas completas**.
   Trata-se de limite inicial de exibição documental, não certificação
   estatística ou garantia de qualidade.
7. Referências externas apresentadas como comentários GitHub são checadas pela
   porta de cronologia existente, mas **continuam alegações não autenticadas**.
8. Nenhuma pontuação gera compra/venda, probabilidade de alta/baixa, backtest
   aprovado ou dado publicável.

## Métricas documentais, somente após cumprir requisitos de cobertura

| Métrica | Significado |
| --- | --- |
| MAE do modelo | Média do erro absoluto das previsões do modelo |
| MAE do consenso | Média do erro absoluto do consenso nos **mesmos eventos** |
| MAE do valor anterior | Média do erro absoluto da previsão ingênua "igual ao anterior" nos mesmos eventos |
| Skill pareada | `1 - (soma_erros_modelo / soma_erros_consenso)`; indefinida quando a soma do consenso é zero |
| Modelo mais perto / igual / pior | Contagem de eventos em cada situação, com empate separado |
| Fração de eventos mais perto | Modelo mais próximo dividido pelo número de eventos pareados; **não** é probabilidade de mercado ou acerto direcional |

**Exemplo inteiramente inventado:** 30 divulgações com resultado 0,4%, consenso
0,3% e previsão 0,35%. Nesse cenário sintético, o erro absoluto do modelo é
0,05 p.p., contra 0,1 p.p. do consenso. Isso **não significa** que o AtlasQuant
já tenha superado o consenso em notícias verdadeiras.

## Limitações ainda obrigatórias

- Previsões, fontes, datas e resultados usados nos testes são **sintéticos**.
- O conjunto de eventos ainda depende da seleção pelo chamador. É possível
  omitir eventos ruins antes de montar o conjunto; nenhuma proteção local pode
  afirmar que não houve viés de seleção.
- Falta autenticar publicações originais, consensos com seus *vintages*,
  carimbos de tempo externos e previsões produzidas antes de cada evento.
- Falta testar previsões sem ajuste retrospectivo, em vários períodos,
  inclusive mudanças de política monetária e notícias surpreendentes.
- Uma métrica econômica acertada não implica ganhar no par cambial: preço já
  incorpora expectativas, e a reação depende de juros, riscos e posicionamento.
- O universo de **índices** segue como requisito do AtlasQuant Trader, mas este
  placar mede apenas erros de indicadores econômicos; não mede previsão do
  S&P 500, Nasdaq, Dow, WIN ou WDO.
- Nem 80% nem 90% de assertividade foram comprovados.

**Estado permanente:** `AGUARDAR`, `publishable=False`, sem sinais, sem
negociação, workers, agendadores, HTTP ou novos custos. PR permanece DRAFT.

## Continuação recomendada

Conectar uma coleção completa e datada de eventos oficiais, registrar de forma
verificável uma previsão **antes** de cada divulgação, preservar valores reais
revisados separadamente dos publicados originalmente e executar este placar
em amostras históricas *walk-forward* não escolhidas pelo resultado.
