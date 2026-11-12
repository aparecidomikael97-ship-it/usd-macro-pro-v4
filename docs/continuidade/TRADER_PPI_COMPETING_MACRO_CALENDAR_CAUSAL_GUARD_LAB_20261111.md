# AtlasQuant Trader — estudo PPI: não confundir simultaneidade com causalidade (LAB)

**Preparação:** 11/11/2026, antes da divulgação programada do PPI dos EUA referente a outubro de 2026, em 13/11/2026 às 13h30 UTC.

## Lacuna corrigida

O protocolo PPI #1851 já congelou uma postura `ABSTAIN`, os sete pares Forex USD e as janelas M15/H1/H4. A medição posterior consegue registrar a surpresa do PPI e as alterações de preço, mas **não demonstra que o PPI sozinho provocou o movimento**: pronunciamentos, política monetária, índices de risco e outros indicadores podem atingir os pares no mesmo período.

Foi criado `atlasquant_trader_ppi_competing_calendar_lab.py` e acoplado ao estudo `atlasquant_trader_ppi_one_event_study_join_lab.py`. Não houve consulta de feed nem contratação de serviço. Este é um verificador **de alegações de calendário**, não uma lista real ou confirmada de eventos de 13/11.

## Contrato de calendário

Um `PreEventCalendarClaim` inclui: horário da captura declarado, início/fim de cobertura, SHA-256 declarado da fonte, declaração de completude do período e registros com **raiz do evento**, horário UTC agendado, moeda ou `GLOBAL`, categoria e importância. O horário da captura deve anteceder estritamente o PPI, e a cobertura precisa incluir a vela de referência de **13h15 UTC** até o fim de H4 às **17h30 UTC**.

As outras divulgações com raiz diferente de `US_PPI_OCT2026` são agrupadas pela raiz; várias métricas do mesmo evento não contam como independentes. Identificações iguais com horários conflitantes bloqueiam a análise. Se um segundo evento tem o mesmo horário que o PPI, ele permanece como concorrente em **M15, H1 e H4**.

As janelas são delimitadas sem olhar candles não fechados:
- Contaminação possível da vela-base: de 13h15 inclusive até 13h30 exclusiva;
- M15: de 13h30 inclusive a 13h45 exclusiva;
- H1: de 13h30 inclusive a 14h30 exclusiva;
- H4: de 13h30 inclusive a 17h30 exclusiva.

Eventos exatamente no fim de uma janela ficam fora daquela janela, pois a vela já fechou. A relevância cambial, ocorrência efetiva e horários de primeira divulgação **não são verificados por este código**.

## Tratamento de incerteza

1. **Sem calendário:** `LAB_PPI_COMPETING_CALENDAR_UNKNOWN_REVIEW_REQUIRED`, nenhum número zero inventado para outros eventos.
2. **Calendário declarado completo e vazio:** `LAB_PPI_EMPTY_COMPETING_LIST_UNATTESTED_REVIEW_REQUIRED`. Zero eventos **listados** não equivale a nenhum outro acontecimento efetivo.
3. **Possíveis eventos concorrentes:** `LAB_PPI_COMPETING_ROOTS_DOCUMENTARY_REVIEW_REQUIRED`, identificadores separados por janela e vela-base.
4. **Calendário inválido ou capturado após a notícia:** bloqueia o relatório consolidado, sem disfarçar dados posteriores como disponíveis antes do PPI.

O relatório PPI consolidado só pode produzir estudo **descritivo** mesmo se a lista de outros eventos estiver vazia:
- `causal_effect_estimated=false`;
- `competing_macro_calendar_context_documentary.ppi_causal_isolation_verified=false`;
- `no_competing_events_proven=false`, `requires_human_calendar_review=true`;
- `pre_event_research_direction=ABSTAIN` e `validated_accuracy=null`.

O protocolo congelado do PPI **não foi modificado**, nem a estimativa de consenso. A entrada de calendário é opcional para permitir a medição puramente descritiva com estado **desconhecido**, mas dados fornecidos falsamente como pré-evento são rejeitados.

## Limites

O hash é apenas alegação de formato; o módulo não autentica o conteúdo original do calendário. Não há mecanismo de captura automática de revisões de última hora. O resultado é **um evento raiz econômico e sete séries de preços correlacionadas**, não sete experimentos independentes. Nenhuma reação observada deve ser comercializada como viés ou acerto validado.

Testes adversariais sintéticos: lista vazia, múltiplos eventos com o mesmo horário, coincidência em limites de janela, duplicatas e conflito de raiz, ausência de cobertura, timestamp tardio, moeda/categoria inválida, assim como integração com o PPI completo. **Nenhum dado real de preços ou do resultado futuro do PPI foi criado ou presumido.**

**Status:** LAB e PR rascunho, sem merge, deploy, operação, publicação ou custo adicional.
