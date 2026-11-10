# AtlasQuant Trader — BLS setembro/2026: confronto de cálculo com comunicado oficial

## Documento localizado

Comunicado de CPI do U.S. Bureau of Labor Statistics para setembro de 2026,
arquivado sob `https://www.bls.gov/news.release/archives/cpi_10142026.htm`.
Na Tabela 1 do documento, linha **All items**, **CPI-U, U.S. city average,
unadjusted indexes** (base 1982–84=100):

| Campo da Tabela 1 | Valor escrito no comunicado |
| --- | ---: |
| Índice setembro/2025 | 324.800 |
| Índice setembro/2026 | 336.940 |
| Variação de 12 meses publicada | 3.7% |

Fórmula verificada:
`(336.940 / 324.800 - 1) × 100 = 3.737684...%`.
Com três casas, **3.738%**; à precisão de uma casa divulgada pelo BLS,
**3.7%**. Assim, o método de cálculo do parser coincide com os valores
apresentados nesse comunicado.

## Modificação implementada

Em `atlasquant_trader_us_bls_cpi_yoy_snapshot_lab.py`, a função
`reconcile_bls_september_2026_release_lab` confronta um cálculo derivado
com a taxa anual alegada de uma publicação BLS com URL específica. Exige
mesmo mês de referência, índice de 12 meses anterior, documento do emissor
esperado, e calcula novamente o arredondamento para uma casa diretamente
dos dois índices. Em caso de diferença, bloqueia e **não exibe a taxa**.

É somente um controle aritmético. Os números da Tabela 1 foram
**transcritos do texto oficial recuperado na consulta web** para uma
fixture que simula o formato JSON da API. **Não são bytes de uma resposta
real da API**, não há SHA de HTML BLS capturado, nem atestação da hora da
primeira publicação ou de vintage histórico. `AGUARDAR` continua obrigatório.

## Testes

- **187/187 testes locais aprovados** (`python -m unittest discover -q -p
  'test_atlasquant*.py'`).
- 4 testes adicionais: números impressos no BLS 2026-09 batem com a taxa
  anual, valor comunicado divergente bloqueia, origem exata diferente é
  rejeitada, e adulterar período ou flags de autenticação rejeita.
- Zero requisições HTTP pelo código, alterações na conta, trades,
  publicações, workers ou cobranças.

## Próxima etapa

Capturar o JSON oficial do BLS por uma via autorizada e com hash preservado.
Somente depois ligar o módulo de índice YoY e o gate temporal a uma
observação USD de verdade. A cobertura bilateral dos 28 pares continua
considerando o USD **não documentado por API validada**.

Fontes BLS:
https://www.bls.gov/news.release/archives/cpi_10142026.htm
https://www.bls.gov/cpi/factsheets/calculating-percent-changes.htm
