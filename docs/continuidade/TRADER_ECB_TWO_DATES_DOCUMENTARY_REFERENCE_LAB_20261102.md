# AtlasQuant Trader — 2 datas reais BCE + 28 cruzamentos REFERENCIAIS (LAB)

Data: 02/11/2026 · PR #1803 DRAFT · HARD NO-GO
Visual V2 aprovado pelo proprietário: INTACTO, sem merge/deploy.

## O que foi confirmado documentalmente

O BCE publica uma tabela de **1 EUR = N unidades de outra moeda**,
em regra em dia útil por volta de **16h na Europa**. Essas taxas
são referências informativas, não ofertas negociáveis, bid/ask
ou preço vivo do mercado. Não devem ser utilizadas como fixação
de transação. A publicação exata e o recibo histórico da
AtlasQuant NÃO foram atestados neste experimento.

Dois conjuntos de taxas publicadas em documentos oficiais,
transcritas como texto sem alterar as casas decimais:

| Moeda por 1 EUR | 30/10/2026 | 02/11/2026 |
|---|---:|---:|
| USD | 1.1172 | 1.1216 |
| JPY | 175.68 | 177.10 |
| GBP | 0.83380 | 0.83580 |
| CHF | 0.9194 | 0.9193 |
| AUD | 1.5904 | 1.6004 |
| CAD | 1.5606 | 1.5673 |
| NZD | 1.9823 | 1.9934 |

Documentos consultados:
- BCE PDF oficial mostrado como **30 October 2026**:
  https://www.ecb.europa.eu/stats/shared/pdf/eurofxref.pdf
- BCE tabela web oficial mostrada como **2 November 2026**:
  https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html
- Arquivos históricos esperados, ainda não baixados:
  https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.csv
- API oficial de EXR: https://data.ecb.europa.eu/help/api/data-examples
- Política estatística de reutilização: https://www.ecb.europa.eu/stats/ecb_statistics/governance_and_quality_framework/html/usage_policy.en.html

**Limitação importante de proveniência:** as páginas de referência
e o PDF "latest" são MUTÁVEIS e podem ser atualizados; os valores
foram conferidos por páginas/resultados oficiais que exibiam
essas datas, porém os bytes originais NÃO foram arquivados com
hash e recibo externo. Esse não é um arquivo histórico
imutável nem uma consulta API com carimbo de recebimento.

## Resultado do cálculo, sem recomendação

A partir das **7 taxas publicadas contra o euro**, a álgebra
permite calcular os **21 pares G8 restantes**, totalizando
28 pares como comparação informativa de duas datas:
\`cross(base/quote) = rate(EUR/quote) / rate(EUR/base)\`,
e para EUR a taxa usada é 1. Esses 21 preços são DERIVADOS,
não 21 fontes independentes de spot. A triangulação dá
resíduo matemático praticamente zero por construção e
NÃO constitui verificação externa de qualidade de mercado.

Comparação 30/10 → 02/11 apenas a posteriori:
- EUR/USD de 1.1172 a 1.1216: aproximadamente **+0,394%**.
- USD/JPY derivado de EUR/JPY dividido por EUR/USD:
  aproximadamente **+0,413%** entre as referências.
- No ranking MATEMÁTICO relativo entre essas duas referências,
  CHF ficou acima das demais e JPY abaixo. Isso NÃO é
  indicação de compra de CHF nem venda de JPY.

O método preserva os sete textos originais em \`eur_quotes\`
e rotula todos os cálculos e cruzamentos como derivados
pela AtlasQuant, com atribuição explícita ao BCE.

## Contrato do laboratório

\`atlasquant_trader_ecb_documentary_reference_lab.py\` recebe
exclusivamente dois documentos explicitamente marcados
\`LAB_PUBLIC_ECB_REFERENCE_DOCUMENT_REVIEW_CANDIDATE\`.
Confere sete moedas, denominação EUR, valores positivos
finitos, fonte e URL esperadas, datas úteis distintas e
intervalo máximo de cinco dias. As informações e o endereço
são enviados pelo pesquisador — podem ser falsificados;
a validação estrutural NÃO autentica o servidor do BCE.

Para evitar uso de divulgação futura no histórico, o corte
artificial exige avaliação às **18h UTC ou depois** da
segunda data, mais tarde que a divulgação normalmente prevista
pelo BCE em verão ou inverno. Não é testemunho do horário
real da divulgação e NÃO prova disponibilidade intradiária.
O código não depende do pacote de fusos \`tzdata\` do Windows.

\`test_atlasquant_trader_ecb_documentary_reference_lab.py\`
possui **20 testes** de recusa e cálculo. No AM12 o teste
inicial falhou porque Python Windows estava sem \`tzdata\`;
o mecanismo foi simplificado para UTC de forma conservadora.
**61 testes locais PASS** no conjunto: 20 desta entrega,
26 do validador de entrada de FX e 15 da interface aprovada.

Arquivo de evidência:
\`docs/continuidade/TRADER_ECB_TWO_DATES_DOCUMENTARY_CASE_LAB_20261102.json\`

**Travas permanentes:** \`can_feed_live_radar=false\`,
\`can_feed_real_oos=false\`, \`trade_authorized=false\`,
\`worker_enabled=false\`, \`scheduler_enabled=false\`;
\`real_currency_strength=null\`; zero sinais/ordens;
sem backtest real, custódia histórica, consenso macro
ou promessa de acerto dos 28 pares.

## Comparação de custos e próximos passos

O BCE é opção oficial gratuita de **referência diária**.
A política de reutilização de estatísticas do SEBC
admite reutilização comercial e não comercial com
atribuição da fonte, dados originais inalterados e
exceções para dados de terceiros. Para integrar ao produto
comercial, revisar termos específicos e distinguir
rigorosamente cálculos derivados de estatísticas originais.

- **Twelve Data Basic:** anúncio oficial de Forex com
  parcerias e série histórica; tabela atual lista US$0,
  **8 créditos/minuto e 800/dia**, mas plano Basic é
  para avaliação/desenvolvimento e NÃO autoriza produção/
  redistribuição. Nenhuma chave/API ou crédito foi usado.
  https://twelvedata.com/pricing
- **Frankfurter:** API aberta e sem chave para histórico
  e referências de muitos bancos centrais. Usa por
  padrão combinação de provedores; para estudar BCE
  exigir filtro específico \`providers=ecb\`. Ainda não
  atestou séries e licenças para entrada operacional.
  https://frankfurter.dev/

**Rota recomendada sem custo:** primeiro comprovar os
dois snapshots diretamente do CSV histórico oficial
(\`eurofxref-hist.csv\`), preservar bytes/hash e captura
atual autêntica, e só então estudar séries para D1.
Depois avaliar, separadamente, preços Forex independentes
com horários e licença adequados a M15/H1/H4/swing.
Nenhuma cota de dados econômicos ou reference daily
pode substituir histórico spot de 28 pares em teste
real de assertividade sem validação independente.

HARD NO-GO: sem nova contratação, API paga, Worker,
agendamento, ordens, merge, deploy ou mudança no
Radar publicado.
