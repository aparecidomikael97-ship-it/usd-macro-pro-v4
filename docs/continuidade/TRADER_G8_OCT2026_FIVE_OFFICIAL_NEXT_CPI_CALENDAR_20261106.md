# AtlasQuant Trader LAB — calendário CPI outubro/2026 (cinco moedas)

**Corte da pesquisa:** 06/11/2026. **Admissibilidade conservadora:** 07/11/2026 00:00 UTC.
**Situação:** laboratório offline, sem trabalho em segundo plano, sem publicação no app e sem direção operacional.

## O que os documentos oficiais permitem dizer

| Moeda | Publicação de referência outubro/2026 | Data do calendário | Fonte primária |
|---|---|---|---|
| USD | CPI-U americano, primeira publicação | 10/11/2026 | [BLS — calendário novembro](https://www.bls.gov/schedule/2026/11_sched_list.htm) |
| CAD | CPI canadense, primeira publicação | 16/11/2026 | [Statistics Canada — release anterior com próxima data](https://www150.statcan.gc.ca/n1/daily-quotidien/261019/dq261019a-eng.htm) |
| EUR | HICP **completo** EA21, posterior ao flash | 18/11/2026 | [Eurostat — flash com data da publicação completa](https://ec.europa.eu/eurostat/en/web/products-euro-indicators/w/2-04112026-ap) |
| GBP | CPI britânico, não CPIH | 18/11/2026 | [ONS — publicação agendada](https://www.ons.gov.uk/releases/consumerpriceinflationukoctober2026) |
| AUD | CPI australiano | 25/11/2026 | [ABS — calendário futuro](https://www.abs.gov.au/release-calendar/future-releases/202611/rcc_economy) |

Estas datas foram consultadas no texto de fontes públicas, mas o HTML original e o instante exato de captura **não foram arquivados**. Os calendários podem mudar. Trata-se de registro manual fixado por hash SHA-256 de **metadados**, não de uma prova independente dos dados estatísticos. Nenhuma dessas datas significa que o número oficial da inflação já foi publicado.

CHF, JPY e NZD **não têm data registrada neste recorte**. Isso não significa que os órgãos dessas moedas não tenham outros calendários ou eventos previstos.

## Regras executáveis

Entrada: `docs/continuidade/TRADER_G8_OCT2026_FIVE_OFFICIAL_NEXT_CPI_CALENDAR_LAB_20261106.json`, com bytes exatos pinados por SHA-256, e um `as_of_utc` com fuso.

1. Uma consulta anterior a 07/11/2026 00:00 UTC não recebe eventos do recorte, prevenindo vazamento retrospectivo.
2. Depois desse limite, os 28 pares recebem apenas as datas de sua moeda base ou cotada. Contagem: **25 pares** com pelo menos um evento, incluindo **10 com dois** e **15 com um**; **3** pares sem evento registrado neste recorte.
3. Se dois eventos do mesmo par tiverem a mesma data (ex.: EUR/GBP em 18/11), **ambos** são mostrados como o próximo evento.
4. Uma data ultrapassada muda apenas para `SCHEDULE_DATE_PASSED_ACTUAL_UNVERIFIED`; não se torna inflação realizada. O próximo evento só considera as datas ainda não ultrapassadas. A verificação é por **dia UTC**, não pelo instante intradiário de publicação do país.
5. Sem consenso de mercado coletado antes da divulgação, sem inflação oficial autenticada, sem surpresa macro, sem força relativa, sem ranking, sem confiança percentual, sem viés D1/W1, sem negociação.
6. O resultado não se conecta à aba inicial, ao Radar ou ao Painel Mestre em produção. É um contrato de dados/prova local para o cartão futuro “Próximo evento”.

## Limites importantes

- `CPI-U`, `HICP`, `CPI` britânico e `CPI` canadense/australiano não devem ser diretamente tratados como a mesma métrica macro bilateral.
- Eurostat já apresentou **flash de outubro** em 04/11; 18/11 corresponde à etapa **completa**. Não marcar a etapa completa como já divulgada.
- O registro de um evento econômico não é sinal de compra/venda nem prova de direção futura. Acerto de 80–90% continua sem comprovação prospectiva.
- Frequência de atualização de dados e momento real de publicação de um indicador são coisas diferentes.

## Verificação local

```bash
python -m unittest -v test_atlasquant_trader_g8_oct2026_five_cpi_calendar_lab.py
```

Continuidade de laboratório empilhada sobre o estudo EUR HICP/USD CPI model em **PR #1838**. Sem custo adicional, cron, acesso às corretoras, merge nem deploy.
