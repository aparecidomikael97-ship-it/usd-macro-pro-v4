# AtlasQuant Trader — NZD / CPI trimestral Stats NZ — LAB, 05/11/2026

## Escopo

- Fonte documental oficial: https://www.stats.govt.nz/information-releases/consumers-price-index-september-2026-quarter/
- Frequência publicada: **TRIMESTRAL**. Trimestre de setembro de 2026 (`2026-Q3`), encerrado em setembro, **não é um dado mensal de setembro**.
- Números **informados no anúncio**: índice geral de preços ao consumidor, +0,7% em relação ao trimestre anterior; +3,7% em relação ao mesmo trimestre do ano anterior. Exibição da publicação na fonte: `22 October 2026, 10:45am` — não converter para um instante UTC comprovado sem verificar fuso, documento de origem e registro de coleta.
- Fonte metodológica da cadência: https://www.stats.govt.nz/indicators/consumers-price-index-cpi/ — divulgação trimestral em 2026; indicador mensal adicional previsto para 2027. Não criar valores mensais para 2026.

## Entrega de software isolada

1. `atlasquant_trader_statsnz_nzd_cpi_quarter_text_lab.py`: leitor determinístico de **texto UTF-8 extraído e fornecido** para o anúncio de setembro de 2026. Valida título, dia e horário exibidos, colunas de variação trimestral/anual, uma linha única do CPI geral, números decimais e limites defensivos; registra hash SHA-256 e horário da captura informado pelo sistema local. Não coleta bytes oficiais pela rede.
2. `atlasquant_trader_g8_numeric_inflation_coverage_lab.py`: inclui NZD como sexta cobertura numérica **opcional** da matriz G8/28 pares. Expõe `observation_frequency=QUARTERLY`, `observation_period=2026-Q3` e `observation_month=None` para NZD. Demais fontes capturadas seguem `MONTHLY` e seus meses próprios.
3. Pares com CPI do NZD e qualquer CPI mensal recebem bloqueadores `OBSERVATION_FREQUENCIES_DIFFER` e `QUARTERLY_CPI_MUST_NOT_MASQUERADE_AS_MONTHLY`; nenhuma falsa correspondência setembro-trimestre/setembro-mês. Comparabilidade metodológica permanece negada mesmo quando os meses de duas fontes mensais coincidem.
4. Testes exclusivamente com cargas **sintéticas** para entrada válida, alteração de valores, cabeçalho mensal enganoso, edição do trimestre, campo ausente, duplicidade, formatos inválidos e relógio inexistente, ingênuo ou futuro.

## Cobertura ilustrativa (não captura real)

| Entradas sintéticas válidas | Pares com 2 moedas numericamente cobertas | 1 moeda | 0 moedas |
| --- | ---: | ---: | ---: |
| EUR, USD (padrão) | 1 | 12 | 15 |
| EUR, USD, NZD | 3 | 15 | 10 |
| EUR, USD, GBP, JPY, CAD, NZD | 15 | 12 | 1 |

**Limitações explícitas:** o texto montado para testes NÃO comprova um download original da Stats NZ, autenticidade de anúncio, timestamp de primeira publicação, conjunto histórico *point-in-time* ou consenso pré-evento. Fonte de inflação isolada **não** equivale a força cambial ou compra/venda. Há divergência de metodologias entre países.

**HARD NO-GO:** vieses D1/W1/MN1 = `AGUARDAR`; sem ranking, operações, Worker, scheduler, Radar ao vivo, merge, deploy, novas assinaturas ou novas despesas. A PR de interface #1816 permanece fora deste incremento.
