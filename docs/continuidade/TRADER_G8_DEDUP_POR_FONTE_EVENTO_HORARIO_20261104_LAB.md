# AtlasQuant Trader — deduplicação de evento por fonte e horário (LAB)

Checkpoint 04/11/2026 · PR #1815 · ambiente offline · HARD NO-GO.

## Por que corrigir

O controle anterior recusava apenas o mesmo par `(source_id,event_id)`.
Um chamador poderia alterar `event_id` (campo não autenticado), manter
a mesma fonte e o mesmo instante econômico e contar duas divulgações
como se fossem eventos distintos.

## Regra adicionada

O auditor documental G8 agora exige unicidade do triplo
`(source_id,kind,event_at_utc)` **normalizado em UTC**, além da regra
já existente para `(source_id,event_id)`.

- Dois identificadores diferentes da mesma fonte/mesmo evento/instante:
  `LAB_BLOCKED`, motivo `DUPLICATE_SOURCE_EVENT_TIME_WITH_DIFFERENT_ID`.
- Diferentes notações UTC, como `Z` e `+00:00`, são consideradas
  o mesmo instante.
- Duas divulgações de uma mesma fonte em horários distintos são
  permitidas como **alegações documentais**, sem prova de origem.
- Instantes coincidentes de fontes diferentes podem permanecer no
  dossiê; não se tornam evidências independentes só por isso.
- A saída informa `same_source_event_instant_dedup_checked=true` e
  `declared_event_ids_are_not_independent_evidence=true`.

A regra conservadora não resolve o problema de duas alegações falsas
com horários declarados diferentes. Tampouco autentica horário,
conteúdo, direitos de uso, fundamento ou impacto de mercado.

## Verificação

Cinco casos adicionais no arquivo existente
`test_atlasquant_trader_g8_official_source_receipt_lab.py`.
No AM12 isolado, 41/41 testes desse arquivo aprovados; compilação e
`git diff --check` aprovados. A validação de CI da PR #1815 para
o novo commit ainda deve ser confirmada.

Módulo sem acesso HTTP, Worker, agendamento, renderização da interface,
ordens, custos ou integração ao viés real. D1/W1/MN1 continuam
`AGUARDAR`. PR #1816 (integração macro e UI) e a branch `main`
não são alteradas por esta mudança isolada.
