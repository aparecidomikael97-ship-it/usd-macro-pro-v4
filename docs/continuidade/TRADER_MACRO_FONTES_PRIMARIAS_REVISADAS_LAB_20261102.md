# AtlasQuant Trader — Auditoria de fontes macro primárias (LAB)

Data da revisão: 2026-11-02 · PR #1803 DRAFT · HARD NO-GO

## Resultado auditado

Foram encontrados **8 pontos de acesso documental público oficial** para o piloto de pesquisa USD/EUR. **NENHUM dado histórico foi importado nem atestado**. O inventário estruturado fica em `docs/continuidade/TRADER_MACRO_SOURCE_AUDIT_LAB_20261102.json`. Ele não é fonte operacional e NÃO libera backtest de acurácia real.

| Fonte oficial | Utilidade documental | Limitação que impede uso direto no viés histórico |
|---|---|---|
| [BLS CPI releases originais](https://www.bls.gov/bls/news-release/cpi.htm) | Arquivo dos comunicados de inflação dos EUA, versões originais acessíveis | O comunicado contém dados de períodos que podem ter sido revisados, não oferece automaticamente o consenso do mercado nem recibo histórico da nossa captura |
| [Calendário BLS 2026](https://www.bls.gov/schedule/2026/) | Dia e hora programados em **Eastern Time** para CPI, emprego, PPI | Horário programado NÃO confirma que os bytes estavam disponíveis/capturados naquele segundo |
| [ALFRED](https://alfred.stlouisfed.org/help/downloaddata) | Vintages de séries como eram conhecidas em uma determinada **data** | Data da versão não prova disponibilidade intradiária às 07:00 de Cuiabá; API FRED exige chave registrada e termos específicos |
| [SPF Fed Filadélfia](https://www.philadelphiafed.org/surveys-and-data/real-time-data-research/survey-of-professional-forecasters) | Expectativas trimestrais historicamente publicadas de CPI, PCE, PIB, desemprego etc. | NÃO é consenso instantâneo divulgado antes de cada CPI/NFP, nem pode ser retroatribuído a uma data anterior à publicação |
| [BEA releases](https://www.bea.gov/news/archive) | Arquivo de comunicados de PIB dos EUA, histórico de estimativas | Verificar timestamp da publicação original, formato e revisões por release; ainda não foi ingerido |
| [Eurostat HICP](https://ec.europa.eu/eurostat/web/hicp/information-data) | Flash, final e histórico de revisões da inflação da zona do euro | **Flash e final são divulgações diferentes**. Base atual reprocessada não prova valores disponíveis antes das correções |
| [SPF do BCE](https://www.ecb.europa.eu/stats/ecb_surveys/survey_of_professional_forecasters/html/index.en.html) | Expectativas trimestrais de inflação, PIB e desemprego | NÃO equivale ao consenso imediatamente anterior a cada flash HICP; usar apenas depois da data de divulgação pública da pesquisa |
| [Survey NY Fed](https://www.newyorkfed.org/markets/market-intelligence/survey-of-market-expectations) | Expectativas monetárias pesquisadas entre participantes de mercado | **Os resultados consolidados são publicados cerca de três semanas após a reunião do FOMC**, logo não poderiam orientar retroativamente aquela reunião |

## Constatações concretas e prioridade

1. **Piloto USD/CPI é o mais simples para checagem de versão original.** Há arquivo de notícias do BLS e calendário de divulgação. Exemplo real de calendário: o CPI de outubro de 2026 estava programado para **10/11/2026 às 08:30 ET**, portanto uma fotografia de 02/11/2026 não pode conhecer o resultado e um viés das 07:00 de Mato Grosso em 10/11 não deve ser reescrito após a divulgação. Esta data/hora vem do calendário, não de um dado CPI baixado.
2. **ALFRED para reconciliação e vintages, não para provar o instante da notícia.** Um valor retornado para uma data precisa ser cotejado com o PDF/comunicado original. Não presumir que estava disponível no começo do dia nem converter `realtime_start` em horário de recebimento. Não chamamos a API nem solicitamos chave.
3. **Piloto EUR/HICP como segunda trilha.** A Eurostat publica uma estimativa flash e uma versão final; sua página de dados registra revisões específicas em 2026. É obrigatório preservar o estágio e os arquivos anteriores, em vez de baixar somente a série reprocessada e rotulá-la como valor original.
4. **Separar expectativa de longo prazo de consenso por evento.** As SPFs do BCE e da Filadélfia servem ao contexto, mas não comprovam `actual - consensus` para uma divulgação CPI intradiária. O Survey do NY Fed não pode ser retrodatado à reunião devido à divulgação posterior.
5. **Direitos de reutilização/comercialização e prova de captura estão pendentes** para cada fonte, assim como o FX spot de 28 pares com preços independentes. Uma página pública acessível sem cobrança não demonstra licença para produto B2B/Trader, e encontrar o link não equivale a ter recebido o dado no passado.

## Contrato de admissão futuro: falhar de modo seguro

Para admitir um único evento macro em um estudo de assertividade real, exigir **todos** os campos auditados: `source_id`, URL e cópia da publicação original, identificador de indicador e medida, referência do período, horário oficial de divulgação COM zona, horário de captura de bytes comprovado por custódia externa, hash da cópia, valor/vintage inicial, sequência de revisões e suas publicações, consenso de evento capturado antes da publicação **ou declaração explícita de que o consenso está ausente**, licença autorizada, e preço spot independentemente verificável para o par/horizonte. Se qualquer requisito crítico faltar: `QUARANTINED_NO_REAL_OOS`.

**Não fabricar consenso** a partir de previsões trimestrais. **Não inferir disponibilidade às 07:00** apenas por uma data ALFRED ou agendamento BLS. **Não usar resultado revisado** no horário da primeira publicação. **Não apresentar acurácia real** até existirem registros imutáveis e testes OOS/walk-forward sem vazamento.

## Próximo experimento de baixo custo, mas ainda não executado

Auditar manualmente **um único comunicado BLS CPI original** de 2026 e a versão da mesma série no ALFRED em datas posteriores. Registrar URL, estágio, valor histórico, carimbo de publicação oficial, data do arquivo, lacunas de consenso/captura e restrições de uso. O relatório pode ser documental, **sem requerer APIs pagas ou alimentar o Radar**. A seguir, replicar o método no flash/final do HICP da Eurostat.

### Fontes / limitações documentadas

- BLS archives: https://www.bls.gov/bls/news-release/cpi.htm
- BLS schedule: https://www.bls.gov/schedule/news_release/cpi.htm
- BLS dissemination: https://www.bls.gov/about-bls/dissemination.htm
- ALFRED download/vintage behavior: https://alfred.stlouisfed.org/help/downloaddata
- FRED/ALFRED real-time period: https://fred.stlouisfed.org/docs/api/fred/realtime_period.html
- FRED API terms/key: https://fred.stlouisfed.org/docs/api/terms_of_use.html
- Eurostat HICP release stages/revisions: https://ec.europa.eu/eurostat/web/hicp/information-data
- Philadelphia Fed SPF: https://www.philadelphiafed.org/surveys-and-data/real-time-data-research/survey-of-professional-forecasters
- ECB SPF: https://www.ecb.europa.eu/stats/ecb_surveys/survey_of_professional_forecasters/html/index.en.html
- NY Fed SME publication lag: https://www.newyorkfed.org/markets/market-intelligence/survey-of-market-expectations
- BEA archive: https://www.bea.gov/news/archive

**LAB / HARD NO-GO:** PR DRAFT. Nenhum download/ingestão automática de histórico, nenhum acesso a contas, FRED API, BCE, Worker/cron, compra, trade, merge ou deploy.
