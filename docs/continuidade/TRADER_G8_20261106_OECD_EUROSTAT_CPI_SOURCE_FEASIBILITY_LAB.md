# AtlasQuant Trader — estudo de fontes CPI G8 (OCDE, Eurostat)

**Pesquisa em 06/11/2026 | somente LAB | nenhum HTTP automatizado.**

A documentação de inflação e juros das oito moedas já está catalogada; o
problema seguinte é **uniformizar os tipos de série** e ter evidência sobre
**qual versão era conhecida no momento da análise**. O presente trabalho é
um inventário de fontes *candidatas*, não uma captura de dados econômicos,
comparação quantitativa, serviço de notícias ou algoritmo de viés.

## Constatações confirmadas em documentos oficiais

1. A [OCDE](https://www.oecd.org/en/data/insights/data-explainers/2024/07/consumer-price-indices-frequently-asked-questions-faqs.html)
   organiza CPI nacionais com objetivo de comparação entre países, mas
   índices nacionais podem manter metodologias próprias e sofrer revisões.
   A [API SDMX](https://www.oecd.org/en/data/insights/data-explainers/2024/09/api.html)
   tem rotas de consulta com frequência, período e formato configuráveis.
2. Existem famílias de séries da OCDE classificadas em COICOP **1999** e
   **2018**. Não foi provada neste laboratório a existência de uma série
   completa e consistente de **cada uma das oito moedas** em nenhuma delas.
   URLs candidatas: `DSD_PRICES@DF_PRICES_ALL` e
   `DSD_PRICES_COICOP2018@DF_PRICES_C2018_ALL`.
3. O [Eurostat](https://ec.europa.eu/eurostat/cache/metadata/EN/prc_hicp_esms.htm)
   documenta `prc_hicp_fpd` — HICP com valores **como publicados inicialmente**.
   Isso é promissor para estudar *vintages* do EUR, mas **não prova** por si
   só a hora em que a informação se tornou disponível em cada data nem
   substitui consenso pré-evento e arquivamento autenticado.
4. O [ABS](https://www.abs.gov.au/statistics/detailed-methodology-information/concepts-sources-methods/consumer-price-index-concepts-sources-and-methods/2025/historical-background-and-evolution-monthly-cpi)
   confirma CPI mensal australiano **completo** desde a referência **outubro
   de 2025**, divulgada em novembro de 2025. Portanto, a FAQ geral da OCDE
   que ainda diz "Austrália trimestral" não serve sozinha para determinar
   o calendário australiano de 2026. A frequência efetiva *dentro de cada
   dataset OCDE* continua por verificar com sua resposta real.
5. A [Stats NZ](https://www.stats.govt.nz/indicators/consumers-price-index-cpi/)
   mantém CPI trimestral em **2026** e planeja introduzir mensal a partir
   de **2027**. Trimestre 2026-Q3 não equivale ao mês isolado 2026-09.

## Rotas de pesquisa, sem alegação de cobertura efetiva no dataset

| Moedas | Candidato para investigar | Evidência ainda pendente |
|---|---|---|
| EUR | Eurostat `prc_hicp_fpd` | Schema, agregação da área do euro, períodos e timestamp independente |
| USD, GBP, JPY, CHF, CAD | OCDE CPI COICOP 2018 e retorno à 1999 quando necessário | Chaves de cada série, versão/classificação, período real e histórico PIT |
| AUD | ABS CPI mensal nacional; OCDE a reconciliar | Verificação do dataset OCDE correspondente e mudança de frequência |
| NZD | Stats NZ trimestral | Série trimestral consistente, sem inventar mês isolado |

Os indicadores nacionais continuam com calendários, cestas, convenções e
revisões potencialmente distintos. Também não é lícito trocar o HICP da **área
do euro** por um CPI nacional de um único país.

## Próxima experiência pequena e gratuita

**EUR — primeira publicação do HICP:** inspecionar manualmente o esquema
oficial `prc_hicp_fpd` e a identificação do agregado geográfico da área do
euro. **Correção descoberta em 06/11: a geografia corrente em 2026 é EA21,
não EA20 (Bulgária entrou em 01/01/2026).** Depois, em teste offline,
aceitar somente resposta original de fonte
verificada, com bytes, timestamp de consulta e registro do que ainda não se
consegue provar sobre a publicação histórica.

Critérios de liberação (todos **não satisfeitos** por este catálogo):

- cobertura de todas as moedas e períodos por séries efetivamente consultadas;
- harmonização demonstrável de frequências e métodos;
- armazenamento original e proveniência; versões históricas; consenso
  anterior ao evento;
- conformidade de licença para uso futuro no aplicativo;
- backtest prospectivo D1/W1 com janelas de mercado observadas.

**Estado:** nenhuma captura, nenhuma API acionada pelo módulo, nenhum valor
novo extraído, zero sinais, zero acurácia apurada, sem ranking ou "melhor par",
`AGUARDAR` para operar. Não mexe no aplicativo, Render, Worker, deploy,
calendário de três consultas diárias ou custos. O catálogo é fixado por SHA-256
da nossa transcrição de pesquisa, **não** por recibo oficial autenticado.
