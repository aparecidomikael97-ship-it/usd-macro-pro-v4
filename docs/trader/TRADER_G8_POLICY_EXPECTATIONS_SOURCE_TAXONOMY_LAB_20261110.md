# AtlasQuant Trader — fontes de expectativas de juros: pesquisa versus OIS

**Pesquisa de 10/11/2026; laboratório apenas.** Escopo: 8 moedas G8 / 28 cruzamentos, hipóteses D1 e W1. Não há snapshots reais de OIS/futuros auditados; o módulo `atlasquant_trader_policy_expectations_conflict_lab.py` continua com amostras sintéticas. Esta nova classificação **não autoriza** interpretar uma pesquisa de economistas como preço diário negociável nem emitir viés.

## Fontes primárias identificadas

| Moeda | Publicador e fonte | Natureza | Publicação temporal que conseguimos verificar | Uso responsável |
| --- | --- | --- | --- | --- |
| USD | New York Fed — [Survey of Market Expectations](https://www.newyorkfed.org/markets/market-intelligence/survey-of-market-expectations) | Expectativas de participantes; coleta antes das reuniões e divulgação de resultados em torno de três semanas após a reunião | Data exata de cada resultado exige inspeção específica da divulgação; não derivar de data do questionário | Contexto histórico após a publicação, nunca cotação OIS intradiária |
| EUR | BCE — [Survey of Monetary Analysts](https://www.ecb.europa.eu/stats/ecb_surveys/sma/html/all-releases.en.html) | Pesquisa periódica; agregados em PDF/CSV | Resultado da rodada de outubro listado para 30/10/2026; horários do calendário são indicativos e sujeitos a alterações | Contexto público com data-base; verificar arquivo e instante por vintage |
| GBP | Banco da Inglaterra — [Market Participants Survey, novembro de 2026](https://www.bankofengland.co.uk/markets/market-intelligence/survey-results/2026/market-participants-survey-results-november-2026) | Pesquisa com 80 respostas coletadas de 21 a 23/10 | A página de resultados existe, mas não se atestou o instante de primeira publicação | Nunca tratar 21–23/10 como disponibilidade pública dos resultados |
| CAD | Banco do Canadá — [Market Participants Survey, 3º trimestre de 2026](https://www.bankofcanada.ca/2026/11/market-participants-survey-third-quarter-of-2026/) | Pesquisa trimestral de participantes de mercado | Publicada em 09/11/2026; respostas coletadas 23/09–01/10/2026 | **Veto** de vazamento temporal: coleta em outubro não torna resultados públicos em outubro |
| AUD | RBA — [Financial Conditions, novembro de 2026](https://www.rba.gov.au/publications/smp/2026/nov/financial-conditions.html) | Comentário de mercado sobre preços de OIS, não base de cotações reproduzíveis | Página narrativa oficial identificada; sem timestamp de cada cotação nem snapshots | Contexto qualitativo apenas, não converter a porcentagem citada em série OIS diária |
| JPY | Banco do Japão | Nenhuma série pública de expectativas de política monetária adequada foi **validada nesta pesquisa** | Sem prova | `AGUARDAR` |
| CHF | Banco Nacional Suíço | Nenhuma série pública de expectativas de política monetária adequada foi **validada nesta pesquisa** | Sem prova | `AGUARDAR` |
| NZD | RBNZ — [Survey of Expectations (M14)](https://www.rbnz.govt.nz/hub/home/statistics/series/economic-indicators/survey-of-expectations) | Pesquisa trimestral com PDF/XLSX; inclusive expectativas de OCR nas publicações da série | Página indica divulgação de 13/08/2026; próxima rodada prevista para 17/11/2026 | Contexto periódico; não é caminho de OCR implícito por OIS intradiário |

## Três relógios que não devem ser confundidos

1. **Coleta/resposta:** quando os participantes preenchem a pesquisa. Não equivale a conhecimento público.
2. **Divulgação ao público:** primeira data/hora em que o resultado pode ter sido conhecido pelo operador. O teste não pode usar valores antes desse instante.
3. **Consulta/captura da nossa pesquisa:** quando o laboratório leu a página. Sem arquivo público com timestamp verificável, não se deve fingir que a versão consultada existia antes.

Para as **três datas públicas pesquisadas** (EUR 30/10, CAD 09/11, NZD 13/08), a implementação usa o **dia seguinte às 00:00 UTC** como piso conservador de calendário, sem declarar que esse foi o instante real da divulgação. Para GBP, USD e AUD, o instante exato permanece sem atestação. O próprio relatório de fontes do laboratório não retroage: sua `RESEARCH_VISIBLE_FROM_UTC` é **11/11/2026 00:00 UTC**; os períodos D1/W1 anteriores não podem consumir essa descoberta retrospectivamente.

## Decisão de produto

- **Contexto macro periódico (permitido apenas em pesquisa):** essas fontes podem ajudar a explicar *por que uma moeda parece forte ou fraca*, quando registro, período, unidade e momento público forem verificados.
- **Variação intradiária da expectativa futura de juros (ainda bloqueada):** requer pelo menos duas cotações verificáveis do **mesmo instrumento, tenor, data-alvo, unidade e convenção**, fonte licenciada, timestamps de observação/publicação e captura, e comparação econômica apropriada entre moedas.
- **Não confundir:** taxas oficiais atuais, pesquisas de expectativas, curvas OIS, futuros de juros, comentários de banco central e preços da Pepperstone são conjuntos diferentes. O horário de consulta não pode substituir o horário de divulgação.
- **Nenhuma promessa de assertividade:** somente validação prospectiva fora da amostra, incluindo cobertura/abstenção, pode mostrar ganho real. `operational_bias=AGUARDAR`, `trade_authorized=false`, `publishable=false`.

### Código e prova local

`atlasquant_trader_policy_survey_source_readiness_lab.py` e `test_atlasquant_trader_policy_survey_source_readiness_lab.py`: inventário 8/28, fonte/tipo, piso conservador de data, veto de coleta antes de divulgação, veto a preço OIS e a qualquer sinal, sem rede ou cobrança. A integração ativa com o Radar continua **NO-GO**.
