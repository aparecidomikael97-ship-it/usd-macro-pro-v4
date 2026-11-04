# AtlasQuant Trader — calendário de pesquisa V2 para viés G8 (04/11/2026)

**Prioridade de Mikael:** força macro/fundamental comparada das 8 moedas,
28 pares Forex e viés diário/semanal/mensal, sustentados por macro, micro,
geopolítica, notícias e agenda. Sem FVG/OB neste caminho crítico.

## Revisão sem sobrescrever a história

O calendário V1, revisado em 03/11, fica preservado. A V2 é outra versão
documental, disponível **somente a partir de 04/11/2026**. Isso impede
contaminar um estudo histórico de 03/11 com informação revisada em 04/11.

- V1: 3 eventos / USD e GBP, com BoE sem horário atestado no momento do estudo.
- V2: 10 eventos / USD, GBP, CAD, NZD e AUD, com horários locais convertidos
  em UTC **somente quando apresentados pela fonte**. CAD continua `DATE_ONLY`.
- EUR, JPY e CHF não têm eventos no piloto V2 — **isso não significa baixa
  importância ou ausência de risco**. A agenda permanece incompleta.
- A notícia oficial mais recente do RBNZ **substituiu** a data anterior do
  Financial Stability Report: de 11/11 para **17/11**, às 9h NZDT. Este é
  um relatório de *estabilidade financeira*, **não** uma reunião decisória
  da taxa de juros. O relatório não entra como voto direcional para NZD.

## Dez eventos documentais V2

| Moeda | Evento | Data e hora na fonte | UTC calculado | Fonte oficial |
|---|---|---|---|---|
| GBP | BoE MPC | 05/11 12:00 GMT | 05/11 12:00 | [BoE](https://www.bankofengland.co.uk/events/upcoming-events) |
| USD | Produtividade e custos | 05/11 08:30 EST | 05/11 13:30 | [BLS](https://www.bls.gov/schedule/2026/11_sched_list.htm) |
| CAD | Emprego outubro | 06/11 (hora não aferida) | `DATE_ONLY` | [Statistics Canada](https://www150.statcan.gc.ca/n1/daily-quotidien/261009/dq261009a-eng.htm) |
| USD | Employment Situation / NFP | 06/11 08:30 EST | 06/11 13:30 | [BLS](https://www.bls.gov/schedule/2026/11_sched_list.htm) |
| USD | IPC/CPI | 10/11 08:30 EST | 10/11 13:30 | [BLS](https://www.bls.gov/schedule/news_release/cpi.htm) |
| GBP | PIB mensal | 12/11 07:00 GMT | 12/11 07:00 | [ONS](https://www.ons.gov.uk/releases/gdpmonthlyestimateukseptember2026) |
| USD | PPI | 13/11 08:30 EST | 13/11 13:30 | [BLS](https://www.bls.gov/schedule/news_release/ppi.htm) |
| NZD | Financial Stability Report | 17/11 09:00 NZDT | 16/11 20:00 | [RBNZ atualização](https://www.rbnz.govt.nz/news-and-events/news/2026/10/updates-to-the-october-mpr-and-november-fsr) |
| GBP | Labour Market | 17/11 07:00 GMT | 17/11 07:00 | [ONS](https://www.ons.gov.uk/releasecalendar?keywords=labour+market&release-type=type-upcoming) |
| AUD | Labour Force outubro | 19/11 11:30 AEDT | 19/11 00:30 | [ABS](https://www.abs.gov.au/statistics/labour/employment-and-unemployment/labour-force-australia) |

As observações acima foram feitas por leitura de páginas públicas oficiais,
**não** por guarda certificada dos bytes originais. As fontes podem alterar
novamente o calendário. Nenhum refresh automático, API contratada ou licença
para preços de mercado foi habilitado.

## Contratos e testes

- `atlasquant_trader_macro_event_exposure_v2_lab.py`: 84 exposições FX e 15
  exposições de índices, cobrindo três janelas móveis de 24h/7d/30d.
- `atlasquant_trader_bias_calendar_exposure_link_lab.py`: reconhece V1 e V2,
  exige que cada relatório corresponda exatamente ao seu calendário canônico
  da época e sempre deixa D1/W1/MN1 operacionais em `AGUARDAR`.
- Rejeita data retroativa da V2, hora/fonte adulterada, evento inventado,
  evento omitido, falsa completude, preço live, probabilidade e direção.
- Dados de força e hipóteses macro dos testes são **sintéticos**, sem validação
  de expectativa, surpresa, notícia, geopolítica nem backtest OOS real.

Comando de validação local:

```sh
python -m unittest -q \
  test_atlasquant_trader_macro_event_exposure_lab.py \
  test_atlasquant_trader_macro_event_exposure_v2_lab.py \
  test_atlasquant_trader_bias_calendar_exposure_link_lab.py \
  test_atlasquant_trader_bias_priority_bridge_lab.py \
  test_atlasquant_trader_macro_pit_documentation_link_lab.py \
  test_atlasquant_trader_g8_country_macro_catalog_lab.py
```

**Resultado local em 04/11: 106 testes OK.** Ainda exige teste automático
remoto e documentação das fontes originais com custódia antes de qualquer
alimentação do Radar. PR #1803 continua DRAFT; AION, Worker, operações reais
e Render continuam HARD NO-GO; custo incremental = R$ 0.
