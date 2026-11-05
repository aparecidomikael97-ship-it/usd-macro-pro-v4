# AtlasQuant Trader — cobertura numérica de inflação nas 8 moedas e 28 pares (LAB)

**Etapa:** 2026-11-05. **Estado:** leitor offline de cobertura, com fixtures totalmente sintéticas no teste. **Não é medição de assertividade de trading.**

## Contrato

O leitor `atlasquant_trader_g8_numeric_inflation_coverage_lab.py` aceita **bytes brutos**, opcionalmente ausentes, de apenas duas integrações que já têm parsers rigorosos:

1. EUR — Eurostat HICP/ECOICOP v2, observação anual de inflação (taxa), com marcador `e` de estimativa; documentação: https://ec.europa.eu/eurostat/web/hicp/information-data
2. USD — BLS CPI-U série `CUUR0000SA0`, índice mensal NSA; o percentual anual é **derivado de dois níveis de índice do mesmo mês em anos distintos**, quando ambos existem; documentação: https://www.bls.gov/cpi/

Outras seis moedas G8 (GBP, JPY, CHF, CAD, AUD e NZD) permanecem **sem captura numérica integrada** nesse contrato. Ele recusa bytes malformados, relógios sem timezone, registros de captura posteriores ao corte de avaliação e situações em que se declara captura sem entregar bytes.

O resultado cobre **exatamente os 28 pares canônicos**, em vez de extrapolar os valores de EUR/USD para outras moedas. Para cada par informa se há 0, 1 ou 2 observações estruturais das respectivas moedas, seus meses e os bloqueios de comparação. Guarda também o SHA-256 dos bytes de entrada e horário alegado da coleta. Hash e horário local **não são prova de publicação naquela data**, assinatura do produtor nem fonte de confiança independente.

## Exemplo unicamente sintético de cobertura

Com as respostas sintéticas válidas de EUR (2026-10, estimativa) e USD (2026-09, CPI-U derivado):

| Número de moedas com observação de inflação | Pares dos 28 |
| --- | ---: |
| 2 (somente EUR/USD) | 1 |
| 1 (EUR ou USD com outra moeda) | 12 |
| 0 (nenhuma das duas) | 15 |

Esses números são **contagem de cobertura dos dados fornecidos aos testes**, não porcentagem de acerto nem prova de que os mesmos dados estão agora disponíveis em fonte confiável. Para EUR/USD, os meses não coincidem. Mesmo se coincidissem, HICP e CPI-U NSA derivado têm metodologias distintas e não devem ser subtraídos como um diferencial de força cambial.

Toda observação é tratada como **captura atual, retrospectiva e não autenticada**. Os dados não contêm consenso pré-evento atestado, versão histórica certificada, hora independente de publicação ou preços spot executáveis para um backtest válido.

## Bloqueios permanentes

Para todas as 28 linhas: `D1=AGUARDAR`, `W1=AGUARDAR`, `MN1=AGUARDAR`, `fx_bias=null`, `trade_authorized=false`, `methods_comparable=false`, `inflation_difference_percentage_points=null` e `currency_strength_rank=null`. Não aciona Radar, Worker, cron ou deploy. **Sem preço Bid/Ask histórico atestado, não há taxa de acerto ou entrada operacional.**

**Verificação:** 16 testes novos sintéticos de cobertura, períodos, ausência de fontes, origem em bytes, limites de relógio e ausência de viés; incluir em Quality Tests e repetir regressão econômica. Não houve download de dados, compras, novas assinaturas, merge ou mudança de interface. Draft PR #1815; PR #1816 preservada.
