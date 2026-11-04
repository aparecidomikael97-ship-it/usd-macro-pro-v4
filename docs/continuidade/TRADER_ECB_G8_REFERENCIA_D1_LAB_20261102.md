# AtlasQuant Trader — referência cambial BCE/ECB: pesquisa de viés (LAB)

Data: 02/11/2026 · PR #1803 DRAFT · HARD NO-GO.

## Decisão do Checkpoint Mestre
O viés diário dos 28 pares é o alvo principal. W1 confirma o D1,
MN1 mostra contexto. A estratégia de FVG/OB/BOS/CHoCH permanece
separada no TradingView. **Uma medida histórica relativa de moedas
não é previsão**, taxa de acerto nem sinal de entrada.

## Alternativa oficial estudada

O Banco Central Europeu (BCE/ECB) publica referências diárias
EUR-base para as sete moedas G8 não-EUR: AUD, CAD, CHF, GBP,
JPY, NZD, USD. As referências normalmente são determinadas cerca
de 14:10 e divulgadas por volta de **16:00 Europe Central** em
dias úteis, salvo feriados relevantes. Não equivalem a fechamento
de Forex e o próprio BCE desencoraja seu uso para transações.

- Página oficial: https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html
- API documentada: https://data.ecb.europa.eu/help/api/data-examples
- Convenção do conjunto: EXR/D.{AUD+CAD+CHF+GBP+JPY+NZD+USD}.EUR.SP00.A
  (serviço SDMX, CSV format=csvdata).
- Política de reutilização: https://www.ecb.europa.eu/stats/ecb_statistics/governance_and_quality_framework/html/usage_policy.ga.html
- Condições sobre conteúdo modificado e dados reproduzidos:
  https://www.ecb.europa.eu/services/using-our-site/disclaimer/html/index.en.html

As estatísticas públicas do ESCB podem ser reutilizadas livremente
sob condições de atribuição e disclaimers. **Os números originais
e os cruzamentos/fatores derivados não devem ser apresentados como
uma única estatística oficial do BCE.** Transformações devem ser
claramente identificadas; metadados e taxas originais preservados.

## Entrega técnica em LAB, sem qualquer chamada à API

atlasquant_trader_ecb_reference_expost_lab.py recebe apenas um
envelope com state=LAB_SYNTHETIC_ECB_CSV e texto CSV artificial,
para duas datas de referência. Regras:
- Exige exatamente **7 taxas EUR-base** em cada data, 14 no total.
  Data, método (D, EUR, SP00, A), série, moeda, valor e duplicatas
  são verificados; dados parciais e taxas zero/NaN recusados.
- Datas são de dias úteis com intervalo limitado. É somente
  verificação estrutural, **não** confirmação de feriados ou revisão.
- No horário Europe/Berlin, 18:00 do próprio dia foi escolhido
  como **fronteira conservadora de pesquisa**, não como horário
  comprovado da publicação. Captura declarada anterior à fronteira
  recusa. Captura não é imutável nem autenticada nesta etapa.
- Para moeda C: d_C = ln((EUR/C)_hoje / (EUR/C)_anterior).
  Fatores relativos centrados satisfazem x_EUR - x_C = d_C.
  Para par A/B, mudança de referência = x_A - x_B.
- A saída mostra sete pares diretamente relacionados às séries
  EUR (referências NÃO negociáveis), mais 21 cruzamentos DERIVADOS
  matematicamente, e zero cotações spot independentes certificadas.
- Nunca gera viés D1/W1/MN1 para operação, ranking de
  oportunidades, gatilho, operação, taxa de acerto ou previsão.
- Identifica explicitamente os dados de teste como SINTÉTICOS.
- **21 testes** artificiais cobrem oito moedas, 28 cruzamentos,
  orientação USD/JPY e EUR/USD, Europa DST, datas úteis,
  falta/duplicata de moeda, denominador errado, preço inválido,
  dados futuros e travas de execução. Executados via Quality CI.

## Por que isso importa para a assertividade

A fonte é uma referência mais clara para estudar *movimento
relativo diário*, mas **NÃO substitui preços de negociação** e
não prova que o viés teria previsto o movimento subsequente.
Uma comparação séria terá duas séries diferentes: (a) fundamento
macro/força calculado apenas com dados disponíveis ANTES da
previsão, (b) resultado posterior em preços spot auditados
de outro fornecedor com horário e convenção comprovados.

Próximos portões: confirmar termos de uso no cenário final,
captura realmente registrada, disponibilidades ponto-no-tempo,
calendário de publicações/feriados, histórico de preços
independentes e backtest OOS pré-definido. Sem requisição a
dados reais, sem publicação de "assertividade" e sem ativação.

**HARD NO-GO:** sem API, deploy, merge, Worker, cron, ordem real,
compra de serviços ou custos novos. App publicado intocado.
