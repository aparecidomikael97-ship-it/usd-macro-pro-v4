# AtlasQuant Trader — fechamento da auditoria de fontes SR3/ESR e vintage bilateral — 10/11/2026

**LAB / NO-GO operacional / nenhuma assinatura, ordem, worker, deploy ou acesso à corretora.** Este checkpoint é a continuação da pesquisa de expectativas de juros SR3 e ESR para EUR/USD. A prioridade de longo prazo continua sendo macro G8 + 28 pares Forex; XAU/USD e índices têm trilhas próprias.

## Resultado da investigação de amostras reais

- A [CME confirma a convenção de juros do SR3](https://www.cmegroup.com/markets/interest-rates/stirs/three-month-sofr/specs) e a [CME confirma a convenção do ESR](https://www.cmegroup.com/education/courses/introduction-to-estr/trading-estr-futures). Isso **não** entrega cotações de dois dias por contrato.
- O [calendário oficial do ESR](https://www.cmegroup.com/markets/interest-rates/stirs/euro-short-term-rate/calendar) identifica **ESRU26** (último dia negociável 15/12/2026, ajuste final 16/12/2026) e **ESRZ26** (16/03/2027 e 17/03/2027). Códigos/períodos são verificados documentalmente; volumes/ajustes por vencimento ainda não foram arquivados nem autenticados.
- As [páginas de ajuste do SR3](https://www.cmegroup.com/markets/interest-rates/stirs/three-month-sofr/settlements) e [ESR](https://www.cmegroup.com/markets/interest-rates/stirs/euro-short-term-rate/settlements) não devolveram tabelas de valores legíveis no acesso de pesquisa desta rodada. A [visão geral CME de ajustes](https://www.cmegroup.com/market-data/daily-settlements.html) aponta o CME DataMine para séries históricas. Não concluir que não existem preços; concluir **que não obtivemos amostra primária reproduzível e historicamente auditável nesta consulta**.
- Uma tabela de terceiros ([GoCharting / lista de futuros, página 54](https://gocharting.com/markets/futures?page=54)) mostrou uma linha chamada **ESRU26** com valor e volume. Contudo **não** foi vinculada a um arquivo primário, licença, horário de primeira divulgação nem ao registro SR3 do mesmo instante. **Não importada** para a matriz. A tabela pode mudar dinamicamente.
- **Resultado:** zero conjuntos oficiais autenticados com duas vintages por contrato e ambos os produtos; **nenhum movimento relativo SR3−ESR calculado para viés**, nenhuma fonte paga contratada.

## Lacuna real encontrada no código e corrigida

O verificador anterior só exigia igualdade do **dia final** USD/EUR, permitindo que as duas moedas tivessem **dias iniciais diferentes**. Além disso, poderia calcular a mudança de taxa de uma única moeda misturando **cotação de negociação** (TRADE) com **preço de ajuste** (SETTLEMENT). Mesmo sendo LAB/NO-GO, ambos geravam rótulos enganadores de comparabilidade.

Correção em `atlasquant_trader_eurusd_sr3_esr_quarter_lab.py`:
1. Dentro de cada moeda, dois registros devem usar o **mesmo tipo de cotação**; se forem settlements, o canal declarado deve ser consistente.
2. Entre as moedas, é preciso que **ambos os dias de negociação (inicial e final)** coincidam e que os tipos das duas séries também coincidam.
3. Novo campo explícito `both_claimed_vintage_dates_and_kinds_aligned` só fica verdadeiro após todas essas exigências. Continua sendo **afirmação de dados sintéticos, sem autenticação externa**.
4. Três novos testes regressivos para datas iniciais diferentes, mistura TRADE/SETTLEMENT dentro de um produto e mistura entre produtos. **34 testes locais** de SR3/ESR + gate público CME passaram.

## Critério concreto de próxima coleta

Para receber e avaliar evidência real, cada amostra deve declarar: instituição/URL da fonte original, classe `TRADE` ou `SETTLEMENT`, código exato (**SR3U26/ESRU26** ou trimestre equivalente), vencimento, data da sessão, observação/preço, volume e OI **daquele vencimento**, timestamp da publicação **efetiva**, timestamp da captura e hash SHA-256 dos bytes originais arquivados. As duas vintages precisam ser da mesma classe, mesmo trimestre, mesmas datas inicial/final nos dois países, com disponibilidade point-in-time e **direitos de uso verificados**.

**Não transformar uma linha de busca, cotação pontual sem histórico, posição de página web, volume de todo produto ou preço de settlement com volume zero em comprovação de trade.** Não extrapolar variação do referencial monetário para direção spot; SOFR vs €STR possuem diferenças econômicas, de hedge e de cross-currency basis.

## Decisão de engenharia

Não construir o módulo de score/viés baseado em SR3−ESR até existir conjunto de evidências aprovado. O bloqueio `operational_bias=AGUARDAR` permanece. Investigar acesso legítimo a dados de fechamento por vencimento, idealmente gratuito, com primeiro horário acessível auditável, antes de avaliar qualquer plano pago. O Flow v1.1 continua reservado na Biblioteca /AtlasQuant/Flow.
