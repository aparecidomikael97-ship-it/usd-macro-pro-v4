# AtlasQuant Trader — fontes de expectativas monetárias: adequação e direitos (LAB 03/11/2026)

## Objetivo
Antecipar o **viés relativo** por D1/W1/MN1 exige observar as **expectativas e mudanças no diferencial futuro** entre moedas, não apenas comparar as taxas nominais atuais. Juros maiores, sozinhos, NÃO dizem se uma moeda subirá. Não usar FVG/OB/BOS como etapa principal.

## Cinco fontes primárias avaliadas

| ID | Fonte oficial | O que mede | Acesso e restrição | Situação |
|---|---|---|---|---|
| `BOE_GBP_OIS_DAILY_ARCHIVE` | Banco da Inglaterra | Curva forward implícita em OIS com SONIA, não a taxa básica observada | Arquivo ZIP diário público; Banco informa **sem API**, pretende publicar até meio-dia no próximo dia útil. Material e preços subjacentes podem envolver terceiros; permissões de reuso comercial **não homologadas**. | Candidato a pesquisa pessoal/offline; não elegível ao Radar |
| `ECB_EUR_ESTR_OVERNIGHT` | BCE €STR | Taxa de empréstimo overnight **realizada**, baseada em transações anteriores | BCE diz que não cobra nem licencia o uso do €STR. Não é curva forward de decisões futuras. | Contexto monetário histórico, NÃO antecipação de juros |
| `ECB_EUR_SOVEREIGN_YIELD_FORWARD` | BCE curvas soberanas | Forward derivado de **títulos públicos** com riscos de crédito, inflação e prazo, não OIS | Página afirma que não se destina a identificar oportunidades de trading ou aconselhar preço/ativos. | **EXCLUIR como motor de viés operacional** |
| `CME_USD_FEDWATCH_PAID_API` | CME Group | Probabilidades implícitas em futuros Fed Funds para reuniões do FOMC, sob hipóteses do modelo | Serviço API anunciado a partir de **US$ 25/mês**. | **BLOQUEADO por custo e sem autorização** |
| `NYFED_USD_SOFR_FIXING` | Fed de Nova York | Financiamento overnight **realizado e colateralizado** em repos | Página pública de referência; não equivale a curva esperada de decisão do Fed. | Contexto, não substitui futuro Fed Funds |

### Provas da classificação
- Banco da Inglaterra: https://www.bankofengland.co.uk/statistics/yield-curves
- Regras/termos BoE: https://www.bankofengland.co.uk/legal
- €STR BCE: https://www.ecb.europa.eu/stats/financial_markets_and_interest_rates/euro_short-term_rate/html/index.en.html
- Curva soberana BCE, incluindo finalidade: https://www.ecb.europa.eu/stats/financial_markets_and_interest_rates/euro_area_yield_curves/html/index.en.html
- CME FedWatch API: https://www.cmegroup.com/market-data/market-data-api/fedwatch-api.html
- Fed de Nova York, SOFR: https://www.newyorkfed.org/markets/reference-rates/sofr

## Contrato LAB

O módulo `atlasquant_trader_rate_source_suitability_lab.py` mantém cinco metadados de pesquisa. `assess_rate_source_pair_lab` **rejeita** pares de fontes quando há:
1. custo API não autorizado;
2. fonte não conferida ou comparação da moeda com ela própria;
3. mistura de forward OIS com taxa overnight já observada, futuros de reunião, ou retorno de título público;
4. ausência de dados independentes capturados com histórico point-in-time, de direitos para operação real ou de instrumentos comparáveis.

Mesmo duas séries com nome parecido precisam casar maturidade, colateral, convenção de juros, corte temporal e licenças. O contrato **não inventa** nenhuma cotação de futuros, paridade ou probabilidade.

`test_atlasquant_trader_rate_source_suitability_lab.py` contém 25 testes, incluindo os cinco itens acima, comparação incompatível GBP/EUR e EUR/USD, rejeição de CME pago e garantias HARD NO-GO.

**Situação:** catálogo avaliado em 03/11/2026, sem ingestão de ZIP, API, serviços externos, sinais, corretora, ordens, Worker, cron, merge, deploy, custos nem alteração da interface aprovada. A meta de 90% permanece *não demonstrada*.
