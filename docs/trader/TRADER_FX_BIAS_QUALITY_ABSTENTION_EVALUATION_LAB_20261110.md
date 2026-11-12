# AtlasQuant Trader — avaliar poucos vieses sem inflar assertividade (LAB)

## Motivação

Para uma estratégia com **poucos vieses de alta qualidade**, uma taxa de
acerto isolada é insuficiente. Precisamos registrar simultaneamente:

1. **Oportunidades de decisão**: quantas vezes o sistema poderia avaliar;
2. **Vieses emitidos**: quantos foram realmente apresentados;
3. **Abstenções**: quantas vezes a resposta foi `AGUARDAR`;
4. **Acertos e erros** dos vieses emitidos, incluindo movimentos neutros
   como erros de previsão direcional;
5. Quantidade e independência das observações, em vez de contar repetidas
   atualizações do mesmo horizonte como vitórias separadas.

## Módulo entregue

`atlasquant_trader_fx_bias_quality_lab.py` (somente G8 Forex por enquanto)
aceita amostras declaradas externamente para `D1`, `W1` e `M1` e produz
**apenas contabilidade de pesquisa**. Cada caso exige horários de captura
dos dados usados na previsão, horário de emissão, começo/fim do intervalo
avaliado, captura posterior do preço final, dois preços positivos, par e
horizonte corretos. Se a previsão tem dados capturados depois da emissão,
ou o desfecho ainda não estava disponível, bloqueia.

Para evitar inflar a taxa de acerto, **duas previsões no mesmo par e
horizonte com janelas futuras sobrepostas são rejeitadas**. Assim, três
atualizações do mesmo viés diário não valem três operações independentes.
Os movimentos dentro da faixa neutra configurada são computados como
erro de uma previsão explícita `UP` ou `DOWN`, nunca excluídos do denominador.

## Métricas, com limites obrigatórios

- `research_claim_only_hit_rate_pct`: acertos / vieses emitidos.
- `research_claim_only_coverage_pct`: vieses emitidos / oportunidades.
- `research_claim_only_wilson_lower_95_pct`: limite inferior descritivo
  calculado **somente a partir de pelo menos 100 sinais** (regra LAB inicial).
- `research_claim_only_lower_bound_at_least_80pct`: critério ilustrativo,
  **não** autorização operacional.

O intervalo de Wilson pressupõe amostras binomiais comparáveis e
independentes; impedir sobreposição temporal não elimina correlação de
regimes, moedas e notícias. Nenhum limite calculado aqui certifica essa
hipótese ou desempenho futuro.

## Testes locais

**210/210 testes aprovados** (`python -m unittest discover -q -p
'test_atlasquant*.py'`). Os **12 cenários novos são inteiramente
sintéticos** e exercitam abstenções, cobertura, movimentos neutros, amostras
pequenas, janela repetida, relógio futuro, preços inválidos e grupo correto.

Exemplo **fictício**: 90 acertos em 100 casos pode produzir limite inferior
de Wilson acima de 80%; 80 acertos em 100 não. Ambos permanecem
`validated_accuracy=None`, `calibrated_probability=None`,
`independent_out_of_sample_validation_completed=false`,
`transaction_costs_accounted_for=false`, `AGUARDAR` e sem negociação.

## Próximo gate

Somente após históricos de preços e notícias com integridade temporal
independente e previsões feitas *antes* dos intervalos avaliados, dividir
amostras por tempo em treino/validação/teste fora da amostra. Considerar
spread, slippage, regimes, clusters de pares correlacionados e custos.

**Não afirmar 80%, 90% ou qualquer assertividade real a partir deste LAB.**
Nenhuma conta MT5, trade, publicação, worker, custo ou deploy foi tocado.
