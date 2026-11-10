# AtlasQuant Trader — prontidão de CPI EUR/US e 28 pares (LAB)

**10/11/2026 — Sem viés, pontuação, probabilidade ou operação.**

## Problema de qualidade

O Eurostat forneceu previamente um documento local de **estimativa preliminar
HICP de outubro/2026** para o euro. O parser BLS conhece a série mensal
**CPI-U não ajustado `CUUR0000SA0`** dos EUA e calcula variação de 12 meses
a partir de dois níveis, mas **ainda não há resposta BLS real preservada e
autenticada neste laboratório**. A inspeção oficial anterior da nota de
setembro/2026 não equivale à obtenção de bytes imutáveis da API.

Mesmo que ambas as observações fossem autenticadas, não é válido subtrair
diretamente um HICP de área do euro de um CPI-U dos EUA e inferir o sinal do
EUR/USD. Os índices têm conceitos e cestas de consumo diferentes; resultado,
consenso, revisões e reação de política monetária ainda precisariam de análise.

Fontes institucionais de contexto estatístico:

- Eurostat HICP: https://ec.europa.eu/eurostat/web/hicp/methodology
- BLS CPI-U: https://www.bls.gov/cpi/overview.htm

## Nova porta implementada

`atlasquant_trader_g8_cpi_dual_source_readiness_lab.py` recebe:

- O mapa de oito moedas que a porta de cobertura EUR já aceita (Eurostat
  documental ou ausente; outros emissores não são falsamente habilitados).
- **Bytes brutos** de uma resposta BLS e recibo de coleta, fornecidos pelo
  chamador; a porta BLS revalida schema, níveis, SHA-256, período homólogo e
  captura **alegadamente** anterior à decisão.
- Mês BLS, horizonte de consulta, horário de decisão e horário de avaliação.

Uma observação BLS de mês que ainda não terminou no momento da decisão é
rejeitada. Uma captura posterior à decisão também é rejeitada, em vez de ser
reinterpretada como informação histórica. Isso não comprova o calendário
oficial de lançamento, a primeira publicação, revisões ou a hora real do PC.

## Contagem de cobertura — somente exemplo sintético

Com documento EUR sintético e uma resposta BLS **fabricada no teste**:

| Situação | Pares |
|---|---:|
| Incluem EUR com documento local alegado | 7 |
| Incluem USD com parser/recibo candidato alegado | 7 |
| Interseção dos dois caminhos (EUR/USD) | 1 |
| **Ambos os lados oficialmente autenticados e comparáveis** | **0** |

É **incorreto** chamar esse cenário de 1 par liberado. `EUR/USD` recebe
`combined_eur_usd_candidate_only=true`, mas
`both_currency_issuers_authenticated=false` e
`two_sided_macro_comparison_allowed=false`.

No exemplo, EUR tem referência **2026-10** e USD **2026-09**. Logo, os
meses não coincidem. Um teste adicional inventa índices BLS de outubro/2026
para mostrar que **mesmo coincidindo o mês**, a diferença metodológica continua
sem harmonização e o viés permanece `AGUARDAR`.

A saída nunca coloca valores de inflação dentro das linhas dos 28 pares nem
calcula diferencial de inflação, direção, acurácia, score ou probabilidade.
Um valor YoY USD eventualmente exposto aparece apenas no resumo rotulado
`usd_derived_yoy_claim_research_only`, nunca como resultado oficial.

## Verificação e limites

- Novo `test_atlasquant_trader_g8_cpi_dual_source_readiness_lab.py`:
  **14 testes sintéticos** incluindo meses divergentes/iguais, bloqueio de
  captura pós-decisão, mês futuro, índice homólogo ausente, USD adulterado,
  documento de terceiro emissor, fonte EUR com falsa autenticação, duplicata
  mensal e resultado conservador em D1/W1/M1.
- Suíte local `python -m unittest discover -q -p 'test_atlasquant*.py'`:
  **298/298 PASS** nesta rodada.
- Nenhuma consulta nova à API do BLS, nenhum download de arquivo econômico
  real, nenhum acesso a AM12/MT5, cron, deploy, merge, Worker, compra ou ordem.
  O código será mantido apenas na PR draft de pesquisa.

## Próximo avanço real necessário

Capturar dados oficiais de cada moeda com origem, instante de publicação,
instante de captura, período, revisão, frequência, consenso pré-evento e
metodologia. Depois confrontar as duas moedas com fonte/tempo *point-in-time*
atestados e backtests independentes, não simples diferença de inflação bruta.
