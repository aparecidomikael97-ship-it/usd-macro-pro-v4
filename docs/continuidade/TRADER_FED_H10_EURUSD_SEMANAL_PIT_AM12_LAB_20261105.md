# AtlasQuant Trader — Fed H.10 EUR/USD: observação diária ≠ disponibilidade diária

Data de coleta **05/11/2026 UTC**, modo exclusivamente LAB.

## Evidência oficial e recebimento no AM12

- Histórico primário (Board of Governors): `https://www.federalreserve.gov/releases/h10/hist/dat00_eu.htm`.
- Regra oficial de disponibilidade: `https://www.federalreserve.gov/releases/h10/` e `https://www.federalreserve.gov/releases/h10/hist/`. O Fed indica **publicação na segunda-feira às 16h15 de Nova York** das cotações observadas na semana útil anterior; feriado federal na segunda desloca a publicação para o próximo dia útil. A observação representa uma **taxa de compra ao meio-dia em Nova York**, não um preço executável M15.
- O cabeçalho do documento capturado declara **Release Date: Monday, November 02, 2026** e **Historical Rates for the EU Euro**, unidade USD por EUR.
- Captura manual de 1 requisição HTTPS no AM12 (sem agendamento, serviço pago ou broker), arquivo privado:
  `C:\Users\apare\AtlasQuant_Trader_G8_LAB_20261104\evidence\fed_h10_euro_hist_capture_20261105.html`.
- Criação do arquivo no AM12 (UTC): `2026-11-05T02:36:46.919269Z` — **não** é a hora de publicação histórica.
- Tamanho bruto: **1.133.042 bytes**. SHA-256: `0bdf76f96e381a735a3181877a6631b82648c3e54eb26f22a5bfc203a5071ef1`.
- Leitor offline `atlasquant_trader_fed_h10_euro_history_lab.py` processou o HTML bruto: **6.727 valores numéricos** e **273 `ND` (não disponíveis)**, abrangendo datas de observação de **03/01/2000 a 30/10/2026**.

### Exemplo de bloqueio histórico efetivo

| Dia observado | H.10 USD por EUR | BCE USD por EUR | Publicação do H.10 capturado |
| --- | ---: | ---: | --- |
| 28/10/2026 | 1,1140 | 1,1133 | 02/11/2026 |
| 29/10/2026 | 1,1165 | 1,1130 | 02/11/2026 |
| 30/10/2026 | 1,1163 | 1,1172 | 02/11/2026 |

As duas referências são observadas **em horários distintos**, portanto suas diferenças **não são erros de captura, arbitragem, spreads negociáveis nem surpresas de política**. A série BCE foi capturada em outro XML privado, documentado na etapa anterior.

Para um evento de **28/10/2026 18:00 UTC**, o documento H.10 que contém a observação de 28/10 informa publicação em **02/11/2026**. O leitor devolve `reason=H10_RELEASE_AFTER_EVENT_NO_PRE_EVENT_ACCESS`; é **proibido** alimentar uma decisão histórica de 28/10 com esses números provenientes do H.10.

## Contratos e limites de confiança

- Entrada: bytes HTML salvos e timestamps explícitos UTC para captura, `as_of` e evento. Sem rede, arquivo de credenciais, agendamento ou IA para inferir valores.
- Seleção exclusiva da tabela histórica com cabeçalho e unidade de EUR; valida release date textual, nome e dia da semana, dias de observação em ordem crescente sem duplicações, números finitos positivos ou `ND`, datas solicitadas existentes sem interpolação e limite de tamanho.
- `source_publication_after_event_date=true` quando a **data** informada no cabeçalho oficial é posterior à data do evento. Se publicação e evento caem no mesmo dia, isso **não comprova** qual ocorreu primeiro: permanece indeterminado. O horário padrão 16h15 é calendário, **não uma prova independente do instante exato de publicação ou de vintage imutável**.
- O HTML recuperado posteriormente não prova que seu conteúdo completo, com a mesma revisão, estava disponível em eventos anteriores. Só prova integridade dos bytes arquivados após a coleta local; não autentica por assinatura da fonte.
- Jamais habilitar retorno de acerto, viés FX, M15, live Radar, trade, Worker, scheduler ou publicação. Saída permanente: `operational_bias=AGUARDAR`, `fx_bias=null`, `historical_point_in_time_eligible=false`, `trade_authorized=false`, `new_cost_brl=0`.

**Gate futuro:** buscar fonte de preço independente com amostras intradiárias e horários comprováveis, licenciamento/uso permitido, e uma captura histórica de consensos antes dos eventos; só então desenhar testes de acerto/erro sem look-ahead.

PR #1815 Draft; PR #1816 não alterada. Sem merge, Render, Worker, cobrança ou negociação real.
