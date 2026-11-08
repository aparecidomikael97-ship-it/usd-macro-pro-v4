# AtlasQuant Trader — valor anterior na previsão pré-notícia (LAB)

**Estado em 08/11/2026:** estudo isolado, sem integração ao Radar, Painel Mestre,
matriz dos 28 pares, MT5, alertas, operações ou agendamento. Nenhum dado real
de CPI/NFP foi usado para alegar precisão. Os testes são **sintéticos**.

## O que mudou

O nowcast inicial comparava a surpresa histórica `actual - consensus` e o score
de indicadores antecedentes. O experimento
`atlasquant_news_previous_context_lab.py` acrescenta, na **seleção de análogos**,
o contexto `consensus - previous`: o mercado espera aceleração, estabilidade
ou desaceleração em relação ao último número conhecido?

Ele não presume que essa diferença preveja a surpresa. O efeito é apenas uma
hipótese testável. Dois conjuntos com o mesmo score de antecedentes, mas
contextos de valor anterior diferentes, podem selecionar análogos distintos.

## Portas contra falsas previsões históricas

1. Só admite eventos **mensais**, com a mesma moeda/país, indicador, métrica e
   unidade (`CPI YoY` não é `CPI MoM`, `NFP` não é `CPI`, etc.).
2. Exige valor anterior e consenso do **snapshot pré-notícia**, nunca o
   campo `previous` sobrescrito posteriormente por uma API.
3. Exige horários com fuso e a ordem
   `anterior_publicado <= anterior_capturado <= previsão_capturada < divulgação`.
4. Requer hash SHA-256 do original e indicação de verificação independente;
   **preencher o hash ou marcar um booleano não constitui prova**: a custódia
   real deve ser auditada separadamente antes de alimentar o motor.
5. História de treino só pode incluir resultados cuja **primeira publicação
   já estava disponível** na data da previsão; casos sem original e duplicatas
   ficam fora ou bloqueiam o cálculo.
6. Sem histórico elegível suficiente: `INSUFFICIENT_VERIFIED_HISTORY`, sem
   estimativa nem probabilidades. Sem original prévio: `WAIT_PREVIOUS_ORIGINAL`.
7. `gap_scale` precisa ser escolhido por indicador/métrica/unidade **antes**
   da avaliação fora da amostra. Os pesos, o tratamento de revisões e a escolha
   dos análogos **não estão calibrados**.

## Como medir se vale a pena

`walk_forward_previous_context` compara, para cada previsão que poderia ter sido
feita naquela época, três erros absolutos:

| Referência | Erro avaliado |
| --- | --- |
| AtlasQuant experimental | `abs(estimate - actual)` |
| Consenso publicado antes do evento | `abs(consensus - actual)` |
| Valor anterior conhecido antes do evento | `abs(previous - actual)` |

O teste deve ser feito separadamente por indicador e país, por janelas
cronológicas com amostra suficiente e com revisões/surpresas reconstruídas de
fontes primárias arquivadas. Uma melhora em um exemplo fictício não demonstra
vantagem real. O mínimo de 40 casos históricos e 20 análogos é **provisório**.

## Limites deliberados

- `research_only=True`, `calibrated=False`, `confidence_0_to_10=None`,
  `pair_bias=None`, `automatic_execution=False`.
- Probabilidades `BELOW/INLINE/ABOVE` são **frequências empíricas suavizadas da
  classe do indicador**; não são probabilidade de acertar o EUR/USD, WIN ou
  qualquer operação, e não justificam notas operacionais 6–10.
- O estudo não modifica o `atlasquant_news_nowcast.py` de produção nem habilita
  coleta automática ou cobrança.
- Resultados novos precisam de testes reais point-in-time, avaliação
  walk-forward/out-of-sample e revisão humana antes de qualquer integração.

## Verificação local

- 15 testes sintéticos novos, cobrindo elegibilidade temporal, `previous`,
  hash, duplicação, segregação de país/unidade, ausência de futuros e comparação
  walk-forward. Executados em 08/11/2026: **15/15 PASS**.
- A suíte legada `test_calendar` não pôde carregar neste ambiente pela ausência
  do pacote `requests`; outra suíte de nowcast dependia de um JSON externo não
  presente no checkout. Não atribuir aprovação de toda a regressão a esta etapa.
