# AtlasQuant Trader — cobertura bilateral CPI em laboratório (10/11/2026)

## Problema evitado

O documento Eurostat EUR FLASH de outubro/2026 foi lido com sucesso no AM12,
mas a informação econômica de **uma moeda** não determina sozinha o viés de
um **par de duas moedas**. Além disso, inflação anual de países diferentes
não pode ser subtraída diretamente para criar uma probabilidade de compra.

## Entrega

- `atlasquant_trader_g8_cpi_bilateral_coverage_lab.py` enumera os 28 cruzamentos
  oficiais G8 e anota somente **cobertura documental** de cada lado.
- O único leitor real previamente verificado é EUR/Eurostat. Para USD, GBP,
  JPY, CHF, CAD, AUD e NZD ainda faltam adaptadores específicos com fontes e
  períodos próprios. Um documento de outro país injetado como se já estivesse
  validado é rejeitado.
- Para uma observação documental EUR isolada: **7 pares com um só lado
  documentado**, **21 pares sem documento dos dois lados**, **0 pares com as
  duas moedas documentadas**. Sem documento algum: 28/28 sem cobertura.
- Os horizontes `D1`, `W1` e `M1` são rótulos de consulta da cobertura; isso
  **não habilita** a matriz P-I-T mensal, publicação mensal nem viés mensal.
- Os resultados por par **não contêm o valor da inflação ou direção**, somente
  moedas documentadas/ausentes e estado `AGUARDAR`.
- Verificação de flags conservadoras: o leitor de EUR precisa declarar
  `historical_point_in_time_eligible=false`,
  `value_independently_verified=false`, `can_feed_macro_bias=false` e
  `trade_authorized=false`; qualquer alegação diferente bloqueia a consulta.

## Prova local

`python -m unittest discover -q -p 'test_atlasquant*.py'`:
**161 testes aprovados**, incluindo nove novos cenários sintéticos de
cobertura bilateral. Esses testes não consultaram provedores externos, não
abriram MT5, não alteraram configurações do usuário e não criaram custos.

**Importante:** o teste real de HTML EUR/Eurostat foi realizado e registrado
na etapa anterior; nesta etapa, a montagem dos 28 pares foi testada com
evidência EUR sintética no formato do leitor. Não afirmar que existem sete
pares operáveis nem qualquer acurácia medida a partir dessa cobertura.

## Próximo avanço P0

Criar adaptadores de indicadores econômicos oficiais de outras moedas,
preservando em cada registro emissor, unidade, conceito estatístico, período,
data de divulgação, data efetiva da captura, revisão e qualidade temporal.
Confrontar duas moedas **só com informações que já estivessem disponíveis no
instante de decisão**. Somente depois pensar em pontuação direcional e
validar calibragem por backtest fora da amostra.

Sem merge, deploy, sinais, trabalhador em segundo plano, mensalidade, ou
ordens na Pepperstone.
