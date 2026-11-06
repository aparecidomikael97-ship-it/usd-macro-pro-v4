# AtlasQuant Trader — níveis de juros BCE/Fed, sem viés automático (LAB)

> **Retificação posterior da leitura BCE:** a captura real do AM12 revelou
> **674 observações DIÁRIAS**, não 674 decisões ou datas de mudança. O parser
> foi corrigido para `parse_ecb_dfr_daily_csv_lab`, versão semântica V2.
> Este documento preserva o planejamento inicial; resultados e hashes reais
> estão em `TRADER_EURUSD_JUROS_CAPTURAS_REAIS_AM12_LAB_20261105.md`.

Checkpoint de desenvolvimento em 05/11/2026; continuação da PR #1815, sem
alterar a PR #1816 nem a `main`. **HARD NO-GO** permanece.

## Fonte e variável econômica exata

| Moeda | Referência documental | Medida correta | O que NÃO comprova |
| --- | --- | --- | --- |
| EUR | [BCE, FM.D.U2.EUR.4F.KR.DFR.LEV](https://data.ecb.europa.eu/data/datasets/FM/FM.D.U2.EUR.4F.KR.DFR.LEV) | Taxa da facilidade permanente de depósito, `% ao ano`, em **observações diárias de nível**; repetição não significa nova decisão | Instante do anúncio, data exata da mudança inferida apenas de observações, expectativa pré-reunião ou revisão histórica |
| USD | [FRED, DFEDTARL](https://fred.stlouisfed.org/series/DFEDTARL) e [DFEDTARU](https://fred.stlouisfed.org/series/DFEDTARU), Federal Reserve Bank of St. Louis, origem Board of Governors | Limites inferior e superior da **faixa-alvo vigente** dos Fed Funds, `%`, em observações diárias | Texto ou instante de divulgação do FOMC, surpresa perante consenso ou probabilidade futura |

Pontos de coleta candidatos, **não capturados nesta etapa**:

- BCE: `https://data-api.ecb.europa.eu/service/data/FM/D.U2.EUR.4F.KR.DFR.LEV?format=csvdata&startPeriod=2025-01-01`
- Fed/FRED: `https://fred.stlouisfed.org/graph/fredgraph.csv?id=DFEDTARL%2CDFEDTARU`

A documentação do BCE descreve `csvdata` na sua API SDMX. FRED descreve
`DFEDTARL`/`DFEDTARU` como limites da faixa, efetivos na data da observação;
seu endpoint de API formal exige chave, portanto a URL acima é **candidata de
exportação gráfica**, ainda não homologada como fonte operacional. O formato
precisa ser confrontado com bytes reais antes de chamar a integração de captura
funcional. Verificar também condições de reutilização dos dados.

## Implementação offline

`atlasquant_trader_eurusd_policy_levels_lab.py` contém:

1. `parse_ecb_dfr_daily_csv_lab` (atual): valida chave exata, dimensões, data,
   unidade, percentual Decimal, status, duplicidade e ordenação do BCE.
2. `parse_fed_target_range_csv_lab`: valida duas séries da mesma data, limite
   inferior não maior que superior, faltas explícitas `.` sem interpolação,
   datas futuras, duplicidade e ordenação. Último dia ausente bloqueia a leitura.
3. `compare_eurusd_policy_levels_lab`: permite mostrar etiquetas distintas,
   **não calcula spread FX, ranking de moedas, surpresa ou sinal**.

O parser recebe `bytes` fornecidos por um chamador. Hash SHA-256 e horário
informado pelo relógio local são apenas metadados de integridade e coleta;
**não autenticam origem, publicação, disponibilidade histórica ou consenso**.
Não há rotina HTTP, escrita em disco, cron, Worker, Render, publicação,
contratação de serviço, ordem nem ponte com o Radar ao vivo.

## Testes desta etapa

`python -m unittest -q test_atlasquant_trader_eurusd_policy_levels_lab.py`

Cenários sintéticos offline: válido para cada banco, ausência de decisão e
expectativa, pares de taxas incompletos, duplicidade de datas, valores
inválidos, limites invertidos, dados futuros, colunas inesperadas e CSV malformado.
A Quality CI recebe o novo módulo de testes; a execução no GitHub deve ser
conferida no SHA que contiver esta alteração.

## Próxima verificação e critérios de saída

1. Em revisão manual separada, obter **uma única resposta real de cada fonte**,
   com autorização para HTTPS, bytes originais, URL, cabeçalhos, horário de
   captura e hashes arquivados; verificar conformidade com o parser.
2. Vincular cada alteração da taxa ao **comunicado oficial datado** do BCE/FOMC
   e distinguir decisão, data de vigência, horário de publicação e correções.
3. Obter a expectativa *pré-evento* com timestamp independente/licença adequada,
   depois preços FX independentes e validação histórica ponto-no-tempo/OOS.

Até completar tudo isso: `operational_bias=AGUARDAR`, `trade_authorized=false`,
`can_feed_live_radar=false`. **Não inferir que a moeda com juro nominal maior
deve subir**: os instrumentos, regimes, expectativas e riscos diferem.
