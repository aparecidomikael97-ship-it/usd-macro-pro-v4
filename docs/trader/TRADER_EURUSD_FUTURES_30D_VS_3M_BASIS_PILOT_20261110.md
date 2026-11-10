# AtlasQuant Trader — piloto de futuros de juros USD/EUR (LAB)

**Pesquisa de 10/11/2026; sem contratação.** A meta é testar duas leituras temporais *da mesma referência* para cada moeda, antes de considerar qualquer expansão aos 28 pares. Nenhuma cotação real foi capturada ou autenticada e o Radar permanece `AGUARDAR`.

## O que foi confirmado na documentação oficial

| | USD | EUR |
| --- | --- | --- |
| Fonte/exchange | [CME Group, 30-Day Federal Funds futures](https://www.cmegroup.com/markets/interest-rates/stirs/30-day-federal-fund) | [Eurex, Three-Month Euro STR futures](https://www.eurex.com/ex-en/markets/int/mon/3m-euro-str-futures) |
| Código do produto | `ZQ` | `FST3` |
| Taxa subjacente | Média **aritmética mensal** da Effective Federal Funds Rate | **€STR composto** durante três meses |
| Cotação | Índice de `100 − taxa subjacente (%)` | Índice de `100 − taxa subjacente (%)` |
| Consulta pública | FedWatch visualiza probabilidades correntes/históricas; o manual cita downloads históricos em Excel | Página oficial oferece cotações com atraso e método de ajuste diário do contrato |
| Limitador | FedWatch probabilidade de reunião não é a mesma coisa que preço ZQ bruto | Preços podem refletir pouca negociação, spreads e cálculo por ordens de compra/venda; não presumir liquidez a partir do último valor |

**Ponto decisivo:** não é legítimo comparar diretamente o número `100 − preço` de um futuro USD mensal com um futuro EUR trimestral e chamá-lo de *mudança relativa da taxa básica de juros*. Os períodos, convenções e exposições são diferentes. Tampouco se deve equiparar a expectativa de futuros com a pesquisa de economistas dos bancos centrais.

## Custo, disponibilidade e direitos

- A [CME FedWatch API](https://www.cmegroup.com/market-data/market-data-api/fedwatch-api.html) anuncia o produto **End-of-Day por US$ 25/mês** e oferece histórico a partir de 2015; a versão intradiária tem estrutura distinta. **Nenhuma compra, cadastro ou contrato foi feito.** Preço e termos podem mudar.
- O [manual público do FedWatch](https://www.cmegroup.com/tools-information/quikstrike/cme-fedwatch-tool-user-guide.html) informa comparações de um dia, uma semana, um mês e exportação histórica em Excel. Isso não comprova autorização para coleta automática ou republicação comercial; será necessária revisão dos termos antes de integrar.
- A [FAQ de ajustes da CME](https://www.cmegroup.com/articles/faqs/access-to-cme-group-settlement-data-faq.html) informa que valores de ajustes exibidos no site são disponibilizados livremente após a meia-noite CT; acesso antes disso tem outros canais e condições. Mesmo após a divulgação, verificar permissões de reutilização e o instante exato do arquivo.
- Para a Eurex, a [documentação do FST3](https://www.eurex.com/ex-en/markets/int/mon/3m-euro-str-futures) explica formação de preços de ajuste; a página [ECB Dated STR futures](https://www.eurex.com/ex-en/markets/int/mon/3m-euro-str-futures/estr/ECB-Dated-Euro-STR-Futures-4853042) sinaliza atraso de 15 minutos nas cotações exibidas. Não inferir que uma licença API histórica está incluída sem verificação específica.
- A taxa [€STR do BCE](https://www.ecb.europa.eu/stats/financial_markets_and_interest_rates/euro_short-term_rate/html/index.pt.html), embora oficial e gratuita, reflete **operações do dia útil anterior**. Não é um preço futuro, nem substitui o FST3. Seus índices de €STR composto são medidas históricas, não previsões.

## Guardião implementado

Arquivo `atlasquant_trader_eurusd_futures_basis_guard_lab.py` com testes sintéticos em `test_atlasquant_trader_eurusd_futures_basis_guard_lab.py`:

1. Aceita somente as combinações `currency=USD, product_code=ZQ` e `currency=EUR, product_code=FST3`, com preços de índice finitos e dois snapshots da **mesma entrega** e fontes declaradas por hashes distintos.
2. Rejeita snapshots com captura depois do corte, relógios impossíveis, sequência não independente, preço inválido, contrato rolado, entrega claramente vencida pelo mês, fonte velha e **volume de sessão zero ou não verificável**. O teste de mês não substitui o calendário exato de vencimento. Um preço de ajuste com livro de ofertas e volume zero não é necessariamente inválido; apenas não comprova uma *negociação* sem evidência extra.
3. Pode calcular **a variação reivindicada** do índice de taxa de cada produto separadamente, para testar a aritmética. Não calcula diferencial normalizado USD/EUR nem probabilidade de alta/baixa do EUR/USD.
4. Sem arquivo original, timestamp comprovado, permissão de redistribuição, calibração e metodologia de equivalência entre períodos, continua `market_data_authenticated=false`, `cross_currency_rate_basis_normalized=false`, `trade_authorized=false`, `publishable=false`, `operational_bias=AGUARDAR`.
5. A pesquisa só tem visibilidade laboratorial conservadora a partir de **11/11/2026 00:00 UTC**. Não altera decisões passadas.

**Próxima prova de valor:** obter, com autorização e sem extrapolar direitos, uma amostra autenticada de ZQ e FST3 com mesmo dia de referência e metadados de contrato, maturidade, publicação, liquidez e licença; depois definir/evidenciar normalização. Sem isso, não expandir o detector aos outros 26 cruzamentos nem alegar ganho de assertividade.
