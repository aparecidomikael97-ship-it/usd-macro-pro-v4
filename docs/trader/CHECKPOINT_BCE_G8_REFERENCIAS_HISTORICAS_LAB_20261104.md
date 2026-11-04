# AtlasQuant Trader — BCE/ECB G8: referência histórica diária em laboratório

Data: 04/11/2026 · Escopo: Trader Forex/Índices · LAB · R$ 0 adicional

## Decisão e fonte oficial
Banco Central Europeu (BCE/ECB):
- Página oficial: https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html
- XML histórico oficial dos últimos 90 dias: https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist-90d.xml
- Documentação da API: https://data.ecb.europa.eu/help/api/data-examples

O BCE publica **taxas de referência informativas** do EUR contra outras moedas em dias úteis. Elas NÃO são preços executáveis de compra/venda, não contêm bid/ask, não asseguram um preço intradiário de Forex e não equivalem a 28 cotações independentes.

As sete taxas necessárias são: EUR contra USD, JPY, GBP, CHF, AUD, CAD e NZD. Adicionamos EUR = 1. Portanto os **28 pares podem ser derivados matematicamente**, mas **21 pares sem EUR são cruzamentos derivados**, não observações de mercado independentes.

## Implementação
`atlasquant_ecb_g8_reference_lab.py`, função `analyze_ecb_reference_xml(xml_bytes, now=...)`.

O método **não faz requisições HTTP** e não lê qualquer chave secreta, arquivo local ou variável de ambiente. Recebe exclusivamente XML já fornecido ao laboratório. A saída é `RESEARCH_ONLY`, distinta de `VALIDATED_DAILY` do Radar.

Para cada par `BASE/QUOTE`, a cotação de referência é
`(unidades QUOTE por EUR) / (unidades BASE por EUR)`.
Comparar duas datas **reais de publicação**:
`100 * (referência_atual / referência_anterior - 1)`.
A ordem do Top 10 é variação **diária entre referências** (não "melhores entradas").
A força relativa G8 é construída dos retornos logarítmicos dos 28 cruzamentos, com sinal positivo para a moeda base e negativo para a moeda cotação. É **relativa e centrada**; não corresponde à probabilidade de lucro.

Contratos de segurança:
- XML inválido, data duplicada/futura, menos de duas datas, moeda faltante, taxa zero/negativa/NaN ou ausência de timezone no relógio informado => `BLOCKED`.
- Datas históricas são permitidas somente como pesquisa, com `reference_age_days` explícito.
- `publishable=false`, `provider_authenticated=false`, `trade_authorized=false` e `accuracy_verified=false`, inclusive quando o XML for estruturalmente perfeito.
- Sem dados de spread, liquidez, OB/FVG, H4/M15 ou gatilho. Nenhuma ordem, sinal ou autorização operacional.
- O código não promove dados BCE para o contrato de feed `VALIDATED_DAILY` nem para a matriz W1/D1/H4/M15.
- Sem alterar AION, Negócios, Investimentos, Worker ou Render.

## Integração futura, condicionada
1. Conferir origem de arquivos BCE por transporte e cadeia de custódia; impor horários de publicação/feriados/fusos e data de observação.
2. Criar visualização **histórica claramente rotulada**, separada de preços negociáveis, com calendário de publicação, atraso e fonte. Não sobrescrever o Top 10 operacional com referências BCE.
3. Para dados de mercado atuais, selecionar provedor com acesso contratual à cobertura 28/28 e limites de quota verificados, sem contratação sem aprovação.
4. Cruzar análise macro, estrutura de preço e risco. Validar desempenho fora da amostra com custos/slippage e R líquido antes de quaisquer alegações de assertividade.

## Critério de conclusão deste bloco
Teste de sete taxas EUR, 28 cruzamentos, orientação base/quote, datas inválidas, valores inválidos e recusa explícita de produção. GitHub CI obrigatório. Nenhuma publicação de números de mercado nesta entrega.
