# AtlasQuant Trader — NFP outubro/2026: contexto anterior, pesquisa Reuters e resultado BLS

Estudo em laboratório de 06/11/2026; **nenhum dado com recibo histórico independente**. Nenhum sinal de USD, previsão registrada ou resultado OOS.

## Origem documental, período e relógio

| Fonte | Divulgado / horário indicado | Período | Dado | Como usar |
|---|---|---|---|---|
| [BLS JOLTS](https://www.bls.gov/news.release/archives/jolts_11032026.htm) | 03/11 10h ET, 15h UTC | Setembro | Vagas abertas **7,5 milhões** (arredondado) | Contexto de vagas; não é previsão do NFP outubro |
| [ADP, comunicado emitido pela empresa](https://www.prnewswire.com/news-releases/adp-national-employment-report-private-sector-employment-increased-by-86-000-jobs-in-october-302929216.html) | 04/11 8h15 ET, 13h15 UTC | Outubro | **+86 mil** empregos no setor privado | Pesquisa independente; não é o NFP nem o seu consenso |
| [Reuters, pesquisa própria de economistas em artigo anterior ao NFP](https://www.reuters.com/business/us-private-payrolls-rise-october-adp-says-2026-11-04/) | 04/11 às 13h27 UTC, artigo datado no próprio site; corte conservador LAB **14h UTC** | Outubro | Previsão de **+65 mil NFP** e **4,2%** desemprego | Referência de expectativa **documental**, não feed contratado |
| [BLS Emprego, edição arquivada](https://www.bls.gov/news.release/archives/empsit_11062026.htm) | 06/11 8h30 ET, **13h30 UTC** | Outubro | **+165 mil NFP** e **4,1%** desemprego | Resultado publicado somente após o embargo |

Todos os números foram transcritos manualmente e versionados no arquivo `TRADER_US_NFP_OCT2026_PREPOST_DOCUMENTARY_CASE_LAB.json`. Não guardamos os HTML originais ou uma testemunha independente de captura na data de 04/11. O artigo Reuters possui data editorial **anterior ao evento**, evidência documental relevante, mas **não comprova sozinho** disponibilidade histórica sem alteração de conteúdo. Direitos de redistribuição comercial de Reuters e outros fornecedores não foram homologados; não incorporar feed nem texto de terceiros ao produto.

## Aritmética controlada, não sinal

Após a divulgação do BLS, o piloto calcula somente:

- Empregos: `165000 - 65000 = +100000` pessoas, diferença entre realizado e previsão **indicada pela Reuters**.
- Desemprego: `4.1 - 4.2 = -0.1` ponto percentual.

Essas grandezas não devem ser chamadas de **surpresa de mercado independentemente verificada** nem traduzidas automaticamente em dólar forte: falta prova robusta de vintage de consenso, direitos de uso, posicionamento anterior, reprecificação Fed, reação de preço bid/ask e avaliação prospectiva OOS. NFP e ADP são **populações distintas**; a referência de JOLTS é **outro mês e outro conceito econômico**.

O módulo `atlasquant_trader_us_nfp_prepost_pit_lab.py` recebe o snapshot completo e um relógio UTC *simulado*. Até 03/11 14h59:59 UTC não inclui JOLTS; até 04/11 13h14:59 não inclui ADP; até 04/11 13h59:59 não inclui a pesquisa Reuters; até **06/11 13h29:59** não inclui NFP realizado, nem qualquer diferença realizado–previsto. Os cortes representam divulgação nominal ou margem conservadora; **não são capturas históricas autenticadas**.

O relatório preserva `market_surprise_independently_verified=null`, `policy_repricing_impulse=null`, `usd_strength=null`, `fx_bias=null`, `validated_accuracy=null`, `trade_authorized=false`. O universo oficial contém sete cruzamentos USD entre 28, mas um estudo de NFP não prova a direção de nenhum deles.

## Próxima etapa importante

Para usar a pesquisa no cálculo de viés, primeiro obter **fonte de consenso com licença e histórico por período/indicador**, registrar um recibo externo antes da divulgação e confrontar a surpresa com o comportamento de juros relativos e câmbio, sem escolher somente movimentos vencedores. Mesmo uma surpresa de +100 mil vagas não demonstra que poderíamos ter previsto o NFP ou antecipado a direção do EUR/USD/GBP/USD antes dele.

**HARD NO-GO:** sem merge, deploy, Worker, cron, cobrança, ordens, alteração da UI, avaliação de 80–90% ou publicação operacional.
