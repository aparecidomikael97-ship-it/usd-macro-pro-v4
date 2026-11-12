# AtlasQuant Trader — treino/validação/teste cronológico (LAB)

## Por que essa etapa existe

Uma taxa de acerto de viés medida sobre períodos usados para construir ou
ajustar o mesmo modelo não é prova de precisão futura. Para perseguir
**poucos vieses com alta qualidade**, precisamos de uma avaliação realmente
fora da amostra, com o modelo fixado antes do período final.

## Módulo

`atlasquant_trader_fx_walkforward_split_lab.py` recebe um plano de três
etapas **ordenadas temporalmente** e casos de previsão do mesmo par/horizonte:

1. Treinamento: período com resultados anteriores para aprendizagem;
2. Validação: período seguinte para escolhas de modelo/limiares;
3. Teste: período futuro, após congelamento do modelo, reservado para
   verificar desempenho sem reajustar parâmetros por causa do resultado.

Cada etapa precisa conter pelo menos um caso sintético bem-formado. As
janelas de desfecho precisam terminar e ter preço final observado dentro
de sua própria etapa. Casos no intervalo de segurança ou que atravessam
uma fronteira são recusados. Cada etapa passa também pelo auditor já
existente de viés que bloqueia duplicidade temporal e lookahead evidente.

## Embargo e modelo congelado

| Horizonte | Intervalo mínimo entre etapas (regra inicial de LAB) | Duração aceita para rótulo futuro |
| --- | ---: | ---: |
| D1 | 1 dia | 1–4 dias |
| W1 | 7 dias | 7–10 dias |
| M1 | 31 dias | 28–35 dias |

As faixas são **política estrutural inicial**, não garantia matemática de
independência nem equivalência rigorosa ao calendário do broker; podem
precisar de revisão após estudar sessões/feriados, timezone e preço real.

O plano contém dois instantes/identificadores SHA-256 **alegados**:

- modelo candidato fixado depois do fim de treino e antes da validação;
- modelo final fixado depois da validação e antes do teste.

Hash de modelo fornecido pelo chamador **não prova** histórico de código,
tempo confiável ou que a previsão foi realmente emitida antes do resultado.
Não há treinamento de modelo dentro do módulo.

## Testes

- **222/222 testes locais aprovados** (`python -m unittest discover -q -p
  'test_atlasquant*.py'`).
- 12 cenários sintéticos novos: três etapas válidas; desfecho atravessando
  fronteira; registro dentro do embargo; congelamento atrasado; embargo
  insuficiente; semana e mês com rótulo/horizonte próprios; janelas
  sobrepostas; ausência de validação; hash/relógio/ativo inválidos; captura
  das variáveis depois da emissão.

## O que NÃO está aprovado

**Ainda não foram executados backtests reais ou treinado qualquer modelo.**
`validated_accuracy=None`, `calibrated_probability=None`,
`out_of_sample_accuracy_validated=false`,
`price_outcomes_independently_verified=false` e
`cross_pair_correlation_audited=false` permanecem no retorno.

Para validação posterior, ainda será necessário obter previsões e dados
originalmente capturados nos instantes relevantes, preços M15/D1/W1
consistentes, custos/spreads, agrupamento de pares correlacionados e prova
de que o modelo permaneceu fixo durante o teste.

Nenhum app publicado, worker, conta Pepperstone, operação, cobrança ou
merge foi alterado. `AGUARDAR` obrigatório.
