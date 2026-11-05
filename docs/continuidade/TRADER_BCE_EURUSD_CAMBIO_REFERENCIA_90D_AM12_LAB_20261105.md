# AtlasQuant Trader — BCE EUR/USD referência diária (LAB, 05/11/2026)

## Resultado comprovado, sem inferir operação

- Fonte primária: BCE, histórico XML dos **últimos 90 dias**: `https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist-90d.xml`.
- Política de publicação declarada pelo BCE: taxas de referência fixadas em torno de **14h10 CET** e publicadas geralmente em torno de **16h CET** em dias úteis do TARGET, **somente informativas**. O BCE desaconselha usá-las para transações: `https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html`.
- Captura manual pontual HTTPS no AM12, sem agendamento e sem chave paga, salva privada em `C:\Users\apare\AtlasQuant_Trader_G8_LAB_20261104\evidence\ecb_eurofxref_hist_90d_capture_20261105.xml`.
- Horário UTC de criação do arquivo no AM12: **2026-11-05T02:23:54.490554Z**. Esse é o instante local de criação registrado no dispositivo, **não** o horário oficial/publicação histórica da taxa e nem uma prova externa assinada de disponibilidade.
- Bytes originais: **69.509**. SHA-256: **`5505c5bd9b1a8883d62991ccde9ad9fadba9245d612ff635dce2a5c7e0cd1690`**.
- Leitor estrito `atlasquant_trader_ecb_eurusd_reference_history_lab.py` processou os bytes reais no AM12, com **64 datas diárias distintas, de 07/08/2026 a 04/11/2026**.
- Amostras retornadas do próprio XML (USD por **1 EUR**): **28/10 1,1133**, **29/10 1,1130**, **30/10 1,1172**, **04/11 1,1267**. O último valor foi conferido com a tabela publicada pelo BCE. Não são preços de execução.

## Contrato técnico V1

- Entrada exclusivamente **bytes XML já capturados** e carimbos de tempo explícitos `captured_at_utc`, `as_of_utc` com fuso; **nenhum acesso de rede** no leitor.
- Verifica origem declarada no XML, namespaces, formato de data e valor, ordenação estritamente decrescente, ausência de datas e moedas duplicadas, cotação USD válida e limites de tamanho.
- Rejeita DTD/ENTITY, `NaN`, infinito, índices/indicadores em vez de cotação, taxa zero, fim de semana no documento, arquivo futuro, capturas após `as_of` e datas de comparação sem observação exata. **Sem forward-fill ou interpolação**.
- Guarda apenas dois valores de referência selecionados, contagem, intervalo, SHA-256, bytes e horário da captura. Não produz retorno percentual implícito, força da moeda, viés, surpresa, spread, conselho de negociação nem preço M15.
- Todos os ramos mantêm `operational_bias=AGUARDAR`, `fx_bias=null`, `trade_authorized=false`, `can_feed_live_radar=false`, `worker_enabled=false`, `scheduler_enabled=false`, `publishable=false`, `new_cost_brl=0`.

## Limites de inferência e próximo gate

1. **A série pode ajudar a descrever dias anteriores** e apoiar futuros estudos. Não mede preço de negociação, slippage ou reação de segundos/minutos às decisões Fed/BCE.
2. Um arquivo coletado **em 05/11** não prova quais observações ou revisões estavam acessíveis em um evento **em 28–29/10**, nem a hora exata da publicação original de cada valor. O último preço diário também não comprova um fechamento de mercado negociável.
3. O bloqueio de vintage no consenso USD (NY Fed SME), a incompatibilidade de horizontes dos surveys EUR/USD e a ausência de preços independentes no momento do evento **persistem**. Não calcular acerto histórico nem ativar ranking dos 28 pares.
4. Próximos passos, apenas LAB: matriz de janelas de evento em UTC com carimbos de publicação efetivamente comprovados, referência diária como contexto separado, e no futuro fonte de preços **independente com timestamps verificáveis** para validar janelas M15 sem look-ahead.

Esta etapa não alterou Trader UI (#1816), não fez merge, deploy, Worker, ativação, compra de dados nem operações reais. Continua na PR #1815 **Draft**.
