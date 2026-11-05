# AtlasQuant Trader — NY Fed SME setembro e ponte EUR/USD (LAB, 05/11/2026)

**Objetivo:** completar o lado USD das expectativas monetárias documentadas
sem confundir data de envio de questionário, data de disponibilização do
resultado ou horizonte de reunião. Nenhum par recebeu direção, surpresa de
juros ou permissão de operar.

## Fontes primárias e disponibilização

1. [NY Fed Survey of Market Expectations (SME)](https://www.newyorkfed.org/markets/market-intelligence/survey-of-market-expectations):
   pesquisa enviada antes do FOMC; resultados agregados são publicados após
   cada reunião e respectivas atas. O SME fundiu, desde 2025, o SPD e SMP.
2. [Fed de Nova York — calendário de publicação](https://www.newyorkfed.org/markets/data-hub/):
   indica resultados **um dia útil após** as atas do FOMC.
3. [Fed — ata da reunião de 15–16/09/2026](https://www.federalreserve.gov/newsevents/pressreleases/monetary20261007a.htm):
   divulgada em **07/10/2026**. A data **08/10/2026** para os resultados SME
   de setembro é **inferida** da regra pública, não atestada por comprovante
   independente de primeiro acesso, cabeçalho HTTP histórico ou hora UTC.
4. Documento [SME setembro 2026, resultados PDF](https://www.newyorkfed.org/medialibrary/media/markets/survey/2026/sep-2026-sme-results.pdf)
   e [dados XLSX](https://www.newyorkfed.org/medialibrary/media/markets/survey/2026/sep-2026-data.xlsx).
   A primeira página do PDF informa distribuição do questionário em 02/09 e
   prazo de resposta em 08/09, não datas de disponibilização dos resultados.
   A questão 2a estima o *ponto médio* da faixa de fed funds para cada reunião.

## Captura real isolada no AM12

Uma requisição manual de cada recurso oficial, em 05/11/2026 UTC, sem plano
pago. Brutos somente em
`C:\Users\apare\AtlasQuant_Trader_G8_LAB_20261104\evidence`:

| Fonte | Arquivo privado | Bytes | SHA-256 |
| --- | --- | ---: | --- |
| XLSX setembro SME | `nyfed_sep_2026_sme_data_private_lab.xlsx` | 251.519 | `eec6790e64761b925b3d9306f198b26e94eff60c0d3fb514ded4f640b0e979df` |
| PDF resultados | `nyfed_sep_2026_sme_results_private_lab.pdf` | 386.947 | `7f532bbf3fed67acc21daa4d5a69e2150e8a67948905a81eac61b4b16a0477a0` |

Planilha inspecionada via Excel Windows em **somente leitura**, com `Sheet1`,
2.749 linhas e 21 colunas. O nome `survey_release_date` (coluna A) parece
enganoso: no arquivo de setembro repete **02/09**, que corresponde à data em
que o questionário foi distribuído, e **não** à data de publicação dos
resultados. `survey_due_date` (coluna B) é **08/09** e também não é publicação.

### Extração da questão 2a, painel Combined, reunião 27–28/10/2026

Filtro exato: `question_tag=fftr_pathofmodes`,
`value_tag=fftr_pathofmodes_20261028`, `panel_type=Combined`,
`horizon_date=2026-10-28`, e `aggregation` separada.

| Medida | Valor recuperado | Significado |
| --- | ---: | --- |
| `count` | 62 | Número de respondentes da questão no painel combinado |
| `pctl25` | 3,63% | Percentil 25 dos pontos médios modais previstos |
| `pctl50` | **3,63%** | Mediana dos pontos médios modais previstos |
| `pctl75` | 3,88% | Percentil 75 dos pontos médios modais previstos |

Os valores brutos da coluna `aggregation_value` são frações: por exemplo,
`0.0363` equivale a **3,63%**, não a 0,0363%. O arquivo tem a mesma questão
duplicada em painéis `Dealer` e `Participant` (26 e 36 respostas); o leitor
seleciona somente `Combined` para evitar tripla contagem. Os valores não
representam taxa efetiva EFFR, decisão anunciada, probabilidade de um corte
ou alta, nem o consenso disponível antes da reunião por prova independente.

## Proteções implantadas

- `atlasquant_trader_nyfed_sme_sep2026_lab.py`: parser **offline** da tabela
  OOXML, com cabeçalho/21 campos exatos, horizonte e `value_tag` fixos,
  restrições de ZIP/XML/tamanho, ausência de fórmulas, validação de frações,
  quatro agregações únicas e percentis ordenados.
- 14 testes sintéticos PASS localmente e **14 PASS no AM12 Windows**, além de
  replay bem-sucedido sobre a planilha real. O `state` é de pesquisa, com
  `results_publication_date_independently_verified=false`,
  `historical_point_in_time_eligible=false`.
- `atlasquant_trader_eurusd_survey_context_compare_lab.py`:
  **ponte bilateral somente classificatória**. Rejeita propagação de
  registros malformados e não calcula spread entre DFR EUR trimestral e
  ponto médio do alvo FOMC por reunião. `interest_rate_spread_bps=null`,
  `fx_bias=null`, `operational_bias=AGUARDAR`.
- 6 testes da ponte PASS localmente e **6 PASS no AM12**. Bateria completa da
  etapa: **197 testes focados PASS** em 12 módulos. Quality CI inclui os
  dois novos testes.

## Próxima validação necessária

1. Prova independente de **quando** o XLSX/PDF de setembro ficou acessível,
   sua versão histórica e as condições de reutilização comercial.
2. Para EUR/USD, alinhar janelas e medidas: SPF/BCE Q3 antecipa DFR de Q4;
   NY Fed SME setembro estima ponto médio da faixa dos juros para FOMC em
   outubro. São metodologias, populações e horizontes diferentes.
3. Consenso genuíno *pré-evento* com vintage atestada, divulgação da decisão
   com instante verificado e preços FX independentes no mesmo corte para
   começar testes históricos sem look-ahead.

**HARD NO-GO:** dados brutos e licença não transferidos ao repositório, sem
merge, deploy, Worker, compra, custos, cron, publicação, Radar ativo ou trade.
PR #1815 DRAFT; PR #1816 preservada.
