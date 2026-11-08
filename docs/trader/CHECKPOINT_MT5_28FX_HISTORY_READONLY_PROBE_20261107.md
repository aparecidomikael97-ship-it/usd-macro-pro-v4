# AtlasQuant Trader — MT5 no AM12: cobertura REAL de históricos G8/28 (07/11/2026)

**Estado:** observação remota real e limitada ao terminal autorizado. **Uso:** laboratório/read-only, sem ordem, login administrativo, broker, deploy, Worker ou compra.

## Contexto e objetivo

O proprietário informou que estava no computador com MetaTrader 5 aberto e pronto para testes. Foi verificado via Desktop Commander que o dispositivo **am12** estava `Online` e que o processo `terminal64.exe` já estava em execução, sem reiniciar ou fechar o terminal. Objetivo P0: verificar se realmente existem velas históricas para os **28 pares G8**, M15/D1/W1, antes de fazer backtests de qualidade do viés (W1/D1, execução M15).

## Pré-voo reproduzido no AM12

- Windows; terminal instalado em `C:\Program Files\MetaTrader 5`; versão reportada pela API `(500, 6306, '6 Nov 2026')`. Terminal `connected=True`, configurado com `maxbars=100000`.
- Python 3.12 e 3.11 instalados. Módulo `MetaTrader5` não estava disponível em nenhum desses interpretadores globais; `numpy` já estava presente no Python 3.11.
- Para a consulta foi instalado o pacote gratuito `MetaTrader5 5.0.6231` com `py -3.11 -m pip ... --no-deps --target`, **apenas na pasta temporária** `%TEMP%\atlasquant_mt5_readonly_20261107`. Nenhuma instalação global, assinatura, cobrança ou mudança de ambiente permanente.
- API `mt5.initialize(path=..., timeout=10000)` foi confirmada; em todas as execuções Python com êxito foi chamado `mt5.shutdown()` para encerrar a **conexão da API**, não o terminal MT5.
- No perfil associado ao executável havia **28 pastas/símbolos com arquivos HCC de 2026** (48 arquivos, ~479 MiB). EURUSD, GBPUSD, USDCHF, USDJPY também tinham HCC associados a 2023–2025. **Arquivo HCC não prova cobertura/qualidade de velas nem é fonte confiável de OHLC sem API.**

## Diagnóstico da causa da leitura parcial e resolução

| Medida | Antes | Depois |
| --- | --- | --- |
| 28 pares canônicos reconhecidos por `symbol_info` | 28/28 | 28/28 |
| Visíveis/selecionados na Observação do Mercado | 7/28 | **28/28** |
| Consulta inicial `copy_rates_from_pos(pair, TF, 1, 200)` nos 3 TFs | 23/84 retornaram 200 velas | Insuficiente como prova final, pois 21 símbolos estavam ocultos |
| Consulta controlada após habilitar 28: M15 50, D1 50, W1 20, `start_pos=1` | — | **84/84 retornaram a quantidade solicitada** |
| Invariantes OHLC e timestamps nas 84 séries retornadas | — | **0 anomalias** nas verificações básicas: tempo estritamente crescente, high >= max(open, close), low <= min(open, close), preços positivos |

- Os 21 símbolos ocultos foram habilitados por `mt5.symbol_select(symbol, True)`, incluindo primeiro EURJPY como prova isolada. Esse comando **apenas altera a Observação do Mercado** (interface) e NÃO negocia, fecha posições, consulta saldo ou configura automação.
- A consulta de 84 séries durou ~94 s no notebook: **não repetir continuamente** e não agendar leituras grandes sem autorização, controle de recursos e avaliação de impacto.
- O teste `start_pos=1` evita reutilizar a vela de posição zero, que pode estar em formação no terminal. Ele é conservador mesmo durante o fechamento semanal, e não constitui sozinho atestado do relógio do broker.
- Amostras dos últimos horários retornados: M15 `2026-11-06T23:30:00Z`, D1 `2026-11-05T00:00:00Z`, W1 `2026-10-25T00:00:00Z`. São tempos de abertura das velas reportados pelo terminal e podem depender da convenção do broker.
- O mercado Forex estava fechado no sábado à noite; não se inferiu cotação ao vivo da última vela.

## Teste de profundidade: 4 pares, não os 28

Para `EURUSD`, `AUDNZD`, `GBPUSD` e `USDJPY`, a API retornou, cada:
- **M15:** 3.000 velas (`start_pos=1`), abertura mais antiga consultada em **24/09/2026**;
- **D1:** 500 velas, abertura mais antiga em **02–04/12/2024**, conforme par;
- **W1:** 200 velas, abertura mais antiga em **01/01/2023**.

Isso confirma que pelo menos quatro pares permitem amostras maiores, mas **não** prova que os outros 24 tenham a mesma profundidade, nem que dados históricos estivessem disponíveis na mesma versão em decisões passadas.

## Limites de segurança e de precisão — mantenha bloqueados

1. A API entrega OHLC do terminal conectado, **não** certifica origem, integridade histórica, timezone/ticks da corretora, lacunas de mercado, spread, slippage, diferenças de contrato ou comparabilidade entre servidores.
2. Checagem `OHLC` e `time` é apenas uma validação estrutural rápida; falta auditoria de gaps por sessão/feriados, duplicatas em longos intervalos, picos, histórico de preços de outro provedor e snapshot reproduzível com SHA.
3. O histórico econômico CPI, juros, expectativas, nowcast e geopolítica continua com fontes/vintages próprios; **não** misturar os timestamps dos candles com `published_at` de indicadores.
4. A consulta atual não mede poder preditivo nem produz `directional_probability`, `score_0_to_10`, acerto, ranking ou viés de índice/FX. Os **28 pares continuam `AGUARDAR`** até amostras temporais validadas e calibração fora de amostra.
5. Não houve chamada de `order_send`, `order_check`, `positions_get`, `account_info`, envio de ordens, alteração de parâmetros operacionais ou integração com broker para execução.
6. A alteração visível feita no terminal foi **habilitar os 21 símbolos adicionais na Observação do Mercado**. Pode ser revertida manualmente pelo proprietário; os gráficos e ordens não foram alterados.

## Fila de execução

- **P0.1:** registrar snapshot somente leitura dos candles com hashes de arquivos, ID de símbolo/timeframe/broker **sem credenciais**, relógio de extração, esquema UTC, flag `start_pos=1` e monitoramento leve.
- **P0.2:** verificar a profundidade e qualidade dos **outros 24 pares**, lacunas e custo de consulta, preferencialmente em lotes pequenos, sem sobrecarregar AM12.
- **P0.3:** unir preços com os registros macro bilaterais verificáveis de ambas as moedas, como camada separada; não juntar dado futuro em backtest.
- **P1:** definir rótulos W1/D1 por par, baselines, walk-forward com embargo, custo/risco e abstenção; testar seletor 0–10 sem inventar probabilidade. Micro/geopolítica continuam fatores condicionais auditáveis.
- **P2:** somente após evidência estatística e paper trading, considerar indicadores de qualidade no Radar; **sem deploy/merge/ordem/Worker** neste checkpoint.

**Foco preservado:** AtlasQuant Trader, abas Início / Radar / Painel Mestre; Forex 28 pares e índices em esteira separada; AION/Negócios/Investimentos congelados. Nenhum custo novo.


## Adendo: snapshots locais completos e auditoria independente — 07/11/2026 (AM12)

**Mudança executada, observada no AM12 conectado, sem ordens:** ferramenta `atlasquant_mt5_closedbar_snapshot_lab.py` buscou as 28 moedas/cruzamentos em **7 lotes sequenciais de 4 pares**, evitando consultas pesadas concorrentes. O MT5 já estava aberto e os 28 pares foram habilitados na Observação do Mercado na etapa anterior. O pacote Python `MetaTrader5 5.0.6231` permanece isolado em `%TEMP%\atlasquant_mt5_readonly_20261107`; a leitura utiliza `start_pos=1`, excluindo a barra potencialmente inacabada.

### Resultado observado, não estimado

| Medida | Resultado |
| --- | --- |
| Pares Forex G8 | **28/28** |
| Séries / consultas | **84/84** |
| Velas M15 por par | **3.000** |
| Velas D1 por par | **500** |
| Velas W1 por par | **200** |
| Total de candles salvos | **103.600** |
| Arquivos de velas compactados | **84 × CSV.gz** |
| Manifestos com SHA-256 dos CSV descompactados | **7 JSON**, um por lote |
| Integridade medida por um segundo programa | **LOCAL_INTEGRITY_PASS; 84 arquivos e 103.600 linhas válidas; zero erros** |
| Tamanho comprimido somado | **1,556 MiB** |
| Janela mais antiga de *alguma* série M15 | 24/09/2026, 17:00 UTC |
| Janela mais antiga de *alguma* série D1 | 02/12/2024, 00:00 UTC |
| Janela mais antiga de *alguma* série W1 | 01/01/2023, 00:00 UTC |
| Abertura mais recente observada (por TF) | M15 06/11/2026 23:30 UTC; D1 05/11/2026 00:00 UTC; W1 25/10/2026 00:00 UTC |
| Intervalos maiores que duração nominal (não necessariamente falhas) | M15 **168**, D1 **2.887**, W1 **0**, agregados nos 28 pares |

`atlasquant_mt5_snapshot_audit_lab.py` foi executado **separadamente e sem acesso ao MT5**. Reabriu as 84 cópias locais, descompactou cada CSV, recalculou SHA-256, conferiu esquema, linhas por timeframe, aberturas UTC inicial/final, monotonicidade, OHLC, positividade e ausência de volumes/spreads negativos. **Zero falhas.**

`atlasquant_mt5_snapshot_integrity_demo_lab.py` fez um teste adversarial sobre uma **cópia temporária dos 84 arquivos e 7 manifestos**: alterou um byte do CSV.gz EURUSD/M15; a auditoria respondeu com código 2 e `LOCAL_INTEGRITY_FAIL` (`CSV_VERIFY_FAILED:EURUSD:M15:EOFError`). O teste terminou **PASS**; todos os arquivos originais permaneceram intactos.

### Local dos dados e proteção de informações

Os candles e os manifestos de cada lote estão **somente no computador AM12**, na pasta privada `%LOCALAPPDATA%\AtlasQuant\LAB\MT5_Snapshots\20261107_AM12`. O relatório de auditoria foi salvo como `audit_summary.json` nesse diretório. O repositório GitHub guarda **somente os scripts e este documento**, e não os candles, as credenciais, o saldo, o número da conta ou o servidor de negociação.

**GATE NÃO LIBERADO:** `LOCAL_INTEGRITY_PASS` garante apenas integridade estrutural das cópias *depois* da captura, não que cotações sejam completas, que o broker esteja autenticado, que o histórico seja ponto-no-tempo verdadeiro, nem que o retorno líquido e as probabilidades tenham vantagem estatística. Os 168/2887 intervalos superiores ao TF incluem fechamentos normais de fins de semana, feriados e mudanças de sessão; para determinar lacunas, é necessário comparar a um calendário específico da corretora e aos históricos independentes. O registro de início mais antigo por TF é o **mínimo observado entre as séries**, não prova de mesma janela em todos os pares.

### Ordem restante antes dos vieses

1. **P0 integridade temporal:** auditar janelas de negociação, alterações de horário/NY close, gaps de sessão, spread histórico e proveniência de outro provedor, sem confundir a data de captura de hoje com disponibilidade em 2023/2024/2025.
2. **P0 macro ponto-no-tempo:** construir e atestar fontes CPI/juros/expectativas por **ambas as moedas** no instante original da decisão; nunca inferir viés de só um diferencial de inflação.
3. **P1 pesquisa:** baseline simples por par, rótulos W1/D1, walk-forward com embargo e custo, calibração de probabilidades, regime, micro e geopolítica; depois teste seletivo **0–10** com abstenção.
4. **NO-GO permanece:** sem mudança na UI publicada, Worker, merge, deploy, dados de conta, pagamentos, ordens, sinais automáticos ou classificação operacional fora de `AGUARDAR`.

A **PR #1851 continua rascunho**; novas verificações locais reais são relatadas separadamente de CI GitHub ou acurácia de previsão.


## Adendo 07/11/2026 — separação conservadora de lacunas de calendário

**Prioridade P0, sem mudança de escopo:** feita nova auditoria **somente dos snapshots já arquivados** no AM12 (`%LOCALAPPDATA%\AtlasQuant\LAB\MT5_Snapshots\20261107_AM12`). Não ocorreu nova coleta pesada dos 28 pares, nenhum login, negociação ou alteração de preços. Código em `atlasquant_mt5_calendar_gap_audit_lab.py`, testes em `test_atlasquant_mt5_calendar_gap_audit_lab.py`. O relatório local adicional fica em `calendar_gap_audit_summary.json` no mesmo diretório. **Arquivos de preços não foram enviados ao GitHub**.

### Resultado observado — candidatos, não certificação de sessão

| Intervalo entre velas consecutivas | Quantidade | Tratamento |
| --- | ---: | --- |
| M15: padrão de pausa de fim de semana (sexta até domingo/segunda) | **168** | `WEEKEND_CANDIDATE` — só candidato |
| D1: padrão sexta→segunda (3 dias) ou sexta→domingo (2 dias) | **2.800** | `WEEKEND_CANDIDATE` — só candidato |
| D1: saltos adicionais em dias de semana | **87** | `REVIEW_UNEXPLAINED` — **não homologado** |
| W1: saltos superiores ao passo semanal de 7 dias | **0** | Sem lacunas detectadas nessa amostra |
| **Total de intervalos não nominais** | **2.968** | Não confundir com número de erros |

Os **87 intervalos D1** concentram-se em **cinco datas UTC**; os números abaixo são *contagens de pares afetados*, não eventos macroeconômicos distintos:

- `2024-12-25`: **10 pares**; candidato a fechamento de Natal, sem confirmar calendário da corretora.
- `2025-01-01`: **20 pares**; candidato a Ano-Novo, sem confirmação.
- `2025-09-30`: **1 par**, **GBPNZD**; **suspeita isolada prioritária**, sem prova de que seja feriado ou dado inválido.
- `2025-12-25`: **28 pares**; candidato a Natal, sem confirmação.
- `2026-01-01`: **28 pares**; candidato a Ano-Novo, sem confirmação.

**Verificação independente e focalizada no MT5:** a consulta somente leitura `copy_rates_range` para 26/09 a 03/10/2025 mostrou **GBPNZD D1 sem candle 30/09/2025**, ao passo que **GBPJPY** e **EURNZD** apresentaram o candle nessa mesma data. Logo, o sistema não deve interpolar, duplicar, usar fechamento da vela seguinte como substituto ou tratar esse trecho como amostra contínua no futuro backtest GBPNZD. A decisão de excluir/segmentar janelas depende de investigação de feed de corretora e comparação com outra fonte legítima, não de adivinhação.

**Regra fail-closed:** a ferramenta devolve `LOCAL_CALENDAR_REVIEW_REQUIRED` enquanto esses intervalos não estiverem comprovados. As classificações `WEEKEND_CANDIDATE` dizem apenas que os **dias extremos do intervalo** são compatíveis com uma pausa típica de fim de semana; **não** provam horário oficial de negociação do broker, horário de verão, ausência de barras intrassessão, disponibilidade P-I-T nem integridade de preço. Calendários de Natal/Ano-Novo devem ser validados por corretora e período antes de converter essas exceções em justificadas.

### Evidência de execução e proteção

- **12/12 testes locais PASS no AM12**, com **11 testes sintéticos da política** e **1 regressão sobre os 84 arquivos e 103.600 velas reais arquivados**.
- Com os snapshots do projeto, a auditoria reconferiu hashes, cobertura (28/84/103600), monotonicidade, horários dos manifestos, regime de 15 minutos e dias, identificou os 87 intervalos D1 e confirmou o par isolado.
- Os hashes Git blob de **ambos os scripts** coincidem *exatamente* com o conteúdo executado no AM12; a execução automática do GitHub não foi alegada.
- `historical_point_in_time_verified=False`, `broker_trading_schedule_verified=False`, `out_of_sample_probability_verified=False`, `trade_authorized=False`, `operational_bias=AGUARDAR`. O período W1/D1 do viés e o M15 de execução continuam com políticas separadas. **Nenhuma nota 0–10, previsão, recomendação ou trade emitida**.
- Não consultar ou gravar saldo, posições, servidor, login ou credenciais. Não mexer em gráficos, Worker, deploy, merge, orçamento ou produção.

### Próximas tarefas, por ordem

1. Corroborar o calendário de sessão do servidor/broker e de feriados com fontes independentes, especialmente **GBPNZD 30/09/2025** e as mudanças de Natal/Ano-Novo.
2. Construir partição de dados com **bloqueio explícito de janelas que cruzem lacunas não verificadas**, sem introduzir fill-forward artificial; documentar a decisão de retenção/exclusão.
3. Confirmar vintage macro bilateral com primeiro horário de captura verificável, validar reagendas e distinguir informações que não existiam na data histórica.
4. Somente depois definir labels D1/W1, validação cronológica fora da amostra, baselines e nota seletiva 0–10. Geopolítica e micro continuam na fila sem inventar sinais.

**Status desta rodada:** GO-LAB para auditoria estrutural; **NO-GO para backtests definitivos e sinais**. Branch isolada PR #1851 continua rascunho, sem merge/deploy ou custos adicionais.
