# AtlasQuant Trader — horários de divulgação das decisões de juros G8 (LAB)

Data da pesquisa: **08/11/2026**. Disponibilidade conservadora deste
levantamento retrospectivo: **somente após 09/11/2026 00:00 UTC**.
Não é prova de arquivo original capturado no instante da divulgação.

## Achado: data da decisão não equivale ao primeiro instante de acesso

| Moeda | Decisão | Horário local alegado pela fonte | Equivalente UTC | Classe documental |
| --- | --- | --- | --- | --- |
| USD | 28/10/2026 | 14:00 EDT | 28/10 18:00Z | `ISSUER_EXPLICIT_RELEASE_TIME` |
| EUR | 29/10/2026 | 14:15 CET | 29/10 13:15Z | `ISSUER_SCHEDULED_TIME` |
| GBP | 05/11/2026 | 12:00 GMT | 05/11 12:00Z | `ISSUER_SCHEDULED_TIME` |
| CAD | 28/10/2026 | 09:45 EDT | 28/10 13:45Z | `ISSUER_SCHEDULED_TIME` |
| AUD | 03/11/2026 | 14:30 AEDT | 03/11 03:30Z | `ISSUER_SCHEDULED_TIME` |
| JPY | 30/10/2026 | 12:02 JST | 30/10 03:02Z | `ISSUER_EXPLICIT_RELEASE_TIME` |
| CHF | 24/09/2026 | 09:30 CEST **padrão de outros eventos, não comprovado para 24/09** | 24/09 07:30Z **apenas hipotético** | `ISSUER_PATTERN_ONLY` |
| NZD | 28/10/2026 | 14:00 NZDT, **horário de atualização exibido em página mutável** | 28/10 01:00Z | `ISSUER_RECORDED_UPDATE_TIME` |

**Distinção crucial**: USD e JPY são os **únicos dois casos** onde o próprio
documento oficial da decisão contém uma expressão de horário de liberação.
Isso é uma declaração do emissor, **não** uma captura independente dos bytes
disponíveis ao público naquele instante. Quatro outros horários são de
agendas/regras de publicação; NZD mostra hora da atualização; CHF mantém
somente padrão posterior. Nenhuma classe automaticamente autoriza replay.

## Fontes primárias específicas

- **Federal Reserve:** comunicado da decisão de 28/10, com `For release at
  2:00 p.m. EDT`:
  <https://www.federalreserve.gov/newsevents/pressreleases/monetary20261028a.htm>.
- **BCE:** decisão oficial de 29/10 e regra de publicação às 14:15 CET:
  <https://www.ecb.europa.eu/press/pr/date/2026/html/ecb.mp261029~9a493adf17.en.html>
  e <https://www.ecb.europa.eu/press/govcdec/mopo/html/index.en.html>.
- **Bank of England:** comunicado da decisão de 05/11 e explicação institucional
  de divulgação do MPC ao meio-dia:
  <https://www.bankofengland.co.uk/monetary-policy-summary-and-minutes/2026/november-2026>
  e <https://www.bankofengland.co.uk/monetary-policy>.
- **Bank of Canada:** aviso oficial de 28/10 especificando 09:45 ET; a hora
  anunciada não é carimbo independente de liberação real:
  <https://www.bankofcanada.ca/2026/10/fad-announcement-release-mpr-2026-10-28/>.
- **Reserve Bank of Australia:** calendário oficial indica 03/11 às 14:30 AEDT:
  <https://www.rba.gov.au/schedules-events/calendar/>.
- **Bank of Japan:** PDF original de 30/10, **página 3**, campo
  `Release dates and times`: decisão às **12:02**:
  <https://www.boj.or.jp/en/mopo/mpmdeci/mpr_2026/k261030a.pdf>.
- **Swiss National Bank:** comunicado de 24/09 informa a **data**, não a hora
  exata; calendário atual mostra 09:30 em **outras** decisões. Não retroceder
  o padrão como prova do evento de setembro:
  <https://www.snb.ch/en/publications/communication/press-releases-restricted/pre_20260924>
  e <https://www.snb.ch/en/services-events/digital-services/event-schedule>.
- **Reserve Bank of New Zealand:** página da taxa oficial exibe
  `Updated: 2:00pm, 28 Oct 2026`:
  <https://www.rbnz.govt.nz/monetary-policy/about-monetary-policy/the-official-cash-rate>.

## Porta de segurança implementada

- Casebook fixado por SHA-256:
  `1a1a7680bca46ab42780e104fc9ac17c9a1c726541f57e0867484b0d2cfdee2f`.
- `atlasquant_trader_g8_policy_release_time_audit_lab.py` valida
  oito moedas, origem oficial dos links, data, classe, zona IANA e horário;
  converte para UTC com horário de verão real.
- Se casebook, horário ou `as_of` falhar, **`LAB_BLOCKED`**;
  antes de 09/11 00:00Z, **`LAB_RESEARCH_NOT_VISIBLE_ASOF`**.
- Em todo cenário, **28 pares D1/W1 = `AGUARDAR`**,
  `historical_backtest_allowed=false`, nenhuma probabilidade estimada,
  ordem, worker, agenda ou publicação real.
- O laboratório **não** leu valores originais de juros nem obteve
  um arquivo imutável de primeira publicação de nenhum emissor;
  a classificação é pesquisa de procedência, não sinal de trading.

## Próxima prova P0

Obter, por emissor, captura preservada do **texto/valor original e timestamp
de disponibilização**, documentando timezone, versão, hash e fonte. Para
calendários sem horário efetivo, a saída precisa permanecer bloqueada.
Só depois comparar as moedas por indicadores economicamente compatíveis,
sem vazamento de dados futuros; em paralelo, preservar o bloqueio do
histórico GBPNZD D1 30/09/2025 e a ausência de calendário de corretora.

**Sem custo, operação, merge, deploy ou worker.** PR #1851 continua draft.
