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
4. Requer hash SHA-256 do original **somente para reivindicar original
   verificado**; quando o arquivo ainda não foi capturado, o hash pode e deve
   permanecer vazio e a previsão fica bloqueada. **Preencher o hash ou marcar
   um booleano não constitui prova**: a custódia real deve ser auditada
   separadamente antes de alimentar o motor.
5. História de treino só pode incluir resultados cuja **primeira publicação
   já estava disponível** na data da previsão; casos sem original e duplicatas
   ficam fora ou bloqueiam o cálculo.
6. Sem histórico elegível suficiente: `INSUFFICIENT_VERIFIED_HISTORY`, sem
   estimativa nem probabilidades. Sem original prévio: `WAIT_PREVIOUS_ORIGINAL`.
7. `gap_scale` precisa ser escolhido por indicador/métrica/unidade **antes**
   da avaliação fora da amostra. Os pesos, o tratamento de revisões e a escolha
   dos análogos **não estão calibrados**.
8. O **consenso** também exige `ConsensusEvidence` para o mesmo país,
   indicador, mês, métrica e unidade. Origem, publicação e captura precisam
   anteceder a previsão e a divulgação. Um **nowcast de modelo**, uma pesquisa
   de famílias ou uma pesquisa trimestral **não substitui** o consenso dos
   analistas para aquele evento exato. Sem ele, `WAIT_EVENT_CONSENSUS_PIT`;
   sem bytes originais, `WAIT_CONSENSUS_ORIGINAL`; sem prova independente de
   disponibilidade, `WAIT_CONSENSUS_ASOF_WITNESS`.
9. Flags e hashes declarados pelo chamador são **alegações**, não prova de
   autenticidade do documento, da composição da pesquisa, de disponibilidade
   pública nem de licença comercial. Mesmo com flags favoráveis, o resultado
   permanece `research_only=True` e jamais é publicado no Radar.

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

## Primeiro piloto documental real: CPI dos EUA (08/11/2026)

Foi preparado o casebook
`docs/continuidade/TRADER_US_CPI_SEPAUG2026_PREVIOUS_MOM_RESEARCH_LAB_20261108.json`,
com transcrições **não autenticadas como captura histórica P-I-T** de dois
comunicados originais do BLS:

| Referência | CPI-U cheio mensal, SA | CPI-U cheio anual, NSA | Comunicado BLS |
| --- | ---: | ---: | --- |
| Agosto/2026 | 0,4% | 3,4% | [11/09/2026](https://www.bls.gov/news.release/archives/cpi_09112026.htm) |
| Setembro/2026 | 0,6% | 3,7% | [14/10/2026](https://www.bls.gov/news.release/archives/cpi_10142026.htm) |

**Para outubro/2026, a divulgação está agendada para 10/11/2026, 13h30 UTC**
([calendário BLS](https://www.bls.gov/schedule/2026/11_sched_list.htm)).
Por causa da falta da base de outubro/2025, a comparação anual do CPI-U cheio
de outubro/2026 não é publicável; verificar [FAQ BLS](https://www.bls.gov/cpi/additional-resources/2025-federal-government-shutdown-impact-cpi-faq.htm).

O módulo `atlasquant_trader_us_cpi_previous_mom_preflight_lab.py` reconhece
o valor anterior *mensal* de 0,6%, mas mantém **sem consenso exato P-I-T,
sem hash de bytes originais, sem previsão, sem probabilidade e sem viés**.
O hash do JSON identifica apenas o **relato de pesquisa**, nunca os bytes do
BLS. Para evitar retrospectiva falsa, o documento só é visível para instantes
`as_of >= 09/11/2026 00:00 UTC`; não serve como evidência original de outubro.

Foram adicionados 7 testes específicos ao piloto: pesquisa futura invisível,
fonte adulterada, fuso, calendário, bloqueio após passar a divulgação e
zero sinal. A etapa seguinte acrescentou testes para bloquear consensos sem
original, sem testemunho de disponibilidade, com métrica diferente, publicados
após o corte ou que sejam projeções de modelos confundidas com pesquisas.
A validação local selecionada totalizou **53 testes aprovados**.

## Verificação local

- 25 testes sintéticos de `previous` e consenso, cobrindo elegibilidade temporal,
  hash, duplicação, segregação de país/unidade, ausência de futuros e comparação
  walk-forward. Executados em 08/11/2026: **15/15 PASS**.
- A suíte legada `test_calendar` não pôde carregar neste ambiente pela ausência
  do pacote `requests`; outra suíte de nowcast dependia de um JSON externo não
  presente no checkout. Não atribuir aprovação de toda a regressão a esta etapa.
