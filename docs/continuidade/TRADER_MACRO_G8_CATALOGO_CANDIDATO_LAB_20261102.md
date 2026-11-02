# AtlasQuant Trader — Catálogo candidato por país para as 8 moedas (LAB)

Data: 02/11/2026 | PR #1803 DRAFT | HARD NO-GO

## Problema que estamos resolvendo

No Trader, D1 deve mostrar o viés de cada um dos 28 pares, W1
confirmar e MN1 dar contexto. Antes de testar se a macro melhora o
viés, precisamos evitar tratar publicações de países diferentes como
se tivessem a mesma frequência, medida econômica, definição ou hora
de disponibilidade. **Nenhuma linha abaixo é um sinal ou aprovação
final de indicador.**

## Candidatos específicos para pesquisa (8 moedas x 4 grupos)

| Moeda | Inflação | Emprego | Juros | Atividade |
|---|---|---|---|---|
| USD | CPI/BLS (mensal) | Desemprego/BLS (mensal) | Federal Reserve, taxa-alvo (decisões) | PIB/BEA (trimestral) |
| EUR | HICP/Eurostat (mensal; flash/final precisam ser distinguidos) | Desemprego/Eurostat (mensal) | ECB, depósito (decisões) | PIB/Eurostat (trimestral) |
| GBP | CPI/ONS (mensal) | Desemprego/ONS (mensal) | BoE Bank Rate (decisões) | PIB/ONS (trimestral) |
| JPY | CPI/Statistics Bureau (mensal) | Desemprego/Statistics Bureau (mensal) | BoJ, taxa curta (decisões) | PIB/Cabinet Office (trimestral) |
| CHF | CPI/FSO (mensal) | Desemprego/SECO (mensal) | SNB Policy Rate (decisões) | PIB/SECO (trimestral) |
| CAD | CPI/Statistics Canada (mensal) | Desemprego/Statistics Canada (mensal) | BoC overnight target (decisões) | PIB/Statistics Canada (trimestral) |
| AUD | CPI/ABS (mensal) | Desemprego/ABS (mensal) | RBA cash rate target (decisões) | PIB/ABS (trimestral) |
| NZD | CPI/Stats NZ (trimestral em 2026) | Desemprego/Stats NZ (trimestral) | RBNZ OCR (decisões) | PIB/Stats NZ (trimestral) |

A lista é de PRODUTORES/CONCEITOS CANDIDATOS, não comprova
que séries históricas, consensos anteriores, direitos de
reutilização, vintages ou preços spot estejam disponíveis.
A unidade econômica é ainda "PERCENT" no contrato sintético,
porém GDP q/q anualizado x não anualizado, métodos de desemprego,
níveis-alvo de juros, calendário de decisões e CPI/HICP NÃO
são comparáveis diretamente sem harmonização auditada.

## Descobertas oficiais que justificam exceções

1. A inflação da zona do euro é HICP. A Eurostat divulga
   estimativa flash e dados finais, com revisões possíveis.
   O identificador HICP foi acrescentado ao parser do LAB
   separadamente de CPI, sem substituição silenciosa.
   https://ec.europa.eu/eurostat/web/hicp/information-data
2. A Statistics New Zealand publicava o CPI principal
   TRIMESTRALMENTE em 2026, e anunciou um CPI mensal a
   partir de 2027. Isso não significa que existam 12
   observações mensais de NZD em 2026.
   https://www.stats.govt.nz/indicators/consumers-price-index-cpi/
3. O CPI australiano é publicado mensalmente pela ABS
   em 2026 (inclui variação anual).
   https://www.abs.gov.au/statistics/economy/price-indexes-and-inflation/consumer-price-index-australia/latest-release
4. Os oito bancos centrais não compartilham uma taxa-base
   idêntica; a definição exata do nível-alvo e o horário
   de divulgação devem ser confirmados antes de calcular
   diferenciais. A frequência é EVENT_DRIVEN, não D1.

## Implementação

- atlasquant_trader_g8_country_macro_catalog_lab.py:
  catálogo de 32 sugestões, com órgão candidato,
  frequência MONTHLY / QUARTERLY / EVENT_DRIVEN,
  unidade, detalhes de definição e URL informativa
  APENAS quando verificada nesta pesquisa.
- draft_g8_country_macro_policy_lab produz um **TEMPLATE
  NÃO CONGELADO** compatível com o contrato anterior de
  pré-seleção, para posterior revisão humana. NÃO o
  registra ou aprova automaticamente.
- atlasquant_trader_macro_surprise_pit_lab.py e
  atlasquant_trader_g8_macro_context_lab.py aceitam HICP
  sem confundi-lo com CPI nacional. Uma pré-seleção
  HICP recusará uma troca posterior para CPI.
- test_atlasquant_trader_g8_country_macro_catalog_lab.py:
  24 testes sintéticos, executados na suíte Quality:
  completude 8x4, 28 pares, HICP, calendários NZD/AUD,
  instituições candidatas, eventos trimestrais, preservação
  dos contratos anteriores, recusas de substituição e
  nenhuma autorização de preço/ordem.

## Portões necessários antes da homologação do viés macro

- Registrar para cada série a frequência/medida exata,
  revisões, estágio flash/final, calendário e horário de
  captura, além do direito de uso comercial.
- Verificar uma fonte histórica independente de CONSENSOS
  e vintages: estatísticas finais não revelam sempre o que
  o mercado esperava em cada data.
- Pré-definir empiricamente ou com hipótese fundamentada
  o indicador por moeda e grupo, antes do teste OOS.
- Definir janela do estudo, baseline FX, pares e retornos
  posteriores sem sobreposição ou seleção retrospectiva.
- Avaliar macro como CONTEXTO/FILTRO, sem supor que
  maior inflação sempre fortalece a moeda.
- Confirmar fonte, governança e autorização humana antes
  de qualquer integração fora do LAB.

Estado: somente candidatos, nenhum dado real adquirido,
nenhuma precisão comprovada, nenhuma atualização do Radar
publicado, nenhuma chamada de API, sem Worker, cron, merge,
deploy, ordem ou gasto adicional. HARD NO-GO permanece.
