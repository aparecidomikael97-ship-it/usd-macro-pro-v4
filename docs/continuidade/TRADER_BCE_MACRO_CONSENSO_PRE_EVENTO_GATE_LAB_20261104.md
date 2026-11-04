# AtlasQuant Trader — proteção de consenso pré-evento na ponte BCE × macro (LAB)

Data: 04/11/2026. PR #1811, separada da PR macro #1803.

## Problema identificado

A ponte de horários entre a referência histórica BCE e o dossiê de
surpresas macro aceitava a data de divulgação declarada e o delta
`actual_minus_consensus`, mas não conferia se o consenso declarado
foi capturado **antes** dessa divulgação. Isso poderia criar uma
aparência falsa de previsão feita com informações pré-evento.

## Bloqueios implementados

- Exige `consensus_captured_at_utc` com fuso e instante **anterior**
  a `released_at_utc`. Consenso ausente, inválido, igual ou posterior
  torna o dossiê recusado.
- Exige `actual_synthetic`, `consensus_synthetic` e diferença numérica
  finita coerente com `actual_minus_consensus`.
- Rotulação `ABOVE_CONSENSUS` só aceita delta positivo e
  `BELOW_CONSENSUS` só aceita delta negativo.
- `IN_LINE_WITH_CONSENSUS` admite diferença pequena diferente de zero,
  pois o deadband pré-declarado não é transmitido pelo contrato de
  dossiê. Esse rótulo **não é independentemente recalibrado** aqui.
- Registra o horário declarado do consenso e
  `consensus_snapshot_origin_authenticated=false`.

O motor apenas classifica cronologia documental nos 28 pares e
D1/W1/MN1; notícias publicadas no dia da referência BCE continuam
com ordem intradiária não comprovada. Consenso sintético e declaração
de timestamps **não são autenticação independente** e não provam
causalidade, reação de mercado ou previsões. O horário de recebimento
real da divulgação não é conhecido por esse contrato.

Sem fonte histórica licenciada, preços FX independentes, consenso
pré-evento autenticado e avaliação OOS real: todos os vieses continuam
`AGUARDAR`, sem conexão com Radar ao vivo, operações, Worker,
agendamento, gastos, merge ou deploy. Quatro testes de proteção
adicionados à suíte já incluída em Quality.
