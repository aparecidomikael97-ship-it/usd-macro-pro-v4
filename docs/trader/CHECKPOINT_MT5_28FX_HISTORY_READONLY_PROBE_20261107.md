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
| **Total de intervalos não nominais** | **3.055** | Soma das três linhas; não confundir com número de erros |

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


## Adendo 07/11/2026 — proteção fail-closed de janelas para futuros backtests (LAB)

**Código preparado, não executado contra os 103.600 candles originais nesta rodada.** Foi adicionado `atlasquant_mt5_backtest_gap_guard_lab.py` e sua suíte `test_atlasquant_mt5_backtest_gap_guard_lab.py`, na mesma branch da PR #1851. Esta etapa desenvolve uma **porta de segurança temporal para futuros consumidores**, sem ativar o backtest operacional existente ou alterar o aplicativo.

### Contrato do bloqueio

1. Para cada par/timeframe, `partition_series` preserva os índices originais e separa segmentos nos intervalos cuja classificação **não seja `NOMINAL`**. Isso inclui `REVIEW_UNEXPLAINED`, `REVIEW_NON_GRID_DELTA` e `WEEKEND_CANDIDATE`: ainda não existe confirmação independente do horário do servidor. Nada é interpolado, preenchido ou reamostrado.
2. `window_decision` recebe os índices inclusivos da primeira e última vela do candidato. Se o candidato atravessar uma única lacuna, informa `BLOCKED_UNVERIFIED_GAP`; `require_contiguous_window` interrompe com `UNVERIFIED_GAP_CROSSED`. Em uma janela temporalmente contínua, retorna apenas `CALENDAR_CONTIGUOUS_UNATTESTED`, **nunca** `backtest_approved=True`.
3. O leitor de arquivo `audit_archive` primeiro executa a auditoria temporal e exige exatamente **28 pares, 84 séries, 103.600 velas e zero erros estruturais**. Depois reabre os mesmos CSV.gz em modo somente leitura, inspeciona esquema/manifestos, constrói as partições e mantém `broker_calendar_verified=False`, `historical_point_in_time_verified=False`, `backtest_approved=False`, `operational_bias=AGUARDAR` e `trade_authorized=False`. Um arquivo ausente/inválido falha fechado.
4. O incidente **GBPNZD D1 29/09 → 01/10/2025** fica representado como barreira, caso seja encontrado no arquivo. Não se marca 30/09 como feriado. Os **86 demais intervalos D1** de Natal/Ano-Novo continuam pendentes, assim como **2.968** pausas candidatas de fim de semana (168 M15 + 2.800 D1). Não são 3.055 defeitos confirmados; são 3.055 cruzamentos que o modo estrito não pode autorizar sem política independente.
5. O script não acessa a API MT5, conta, credenciais, terminal, ordens, rede ou fontes macro. CLI para execução **futura** no AM12: `python atlasquant_mt5_backtest_gap_guard_lab.py --root <pasta-dos-snapshots>`; saída 3 para intervalos bloqueados, 2 para arquivo inválido. Não cria relatório persistente nem altera candles.

### Verificação deste incremento

- Na cópia de trabalho isolada, **26 testes PASS e 2 SKIP** (regressões reais do AM12 ausentes deste ambiente). Um dos testes monta **103.600 velas sintéticas em 84 arquivos e 7 manifestos temporários** para exercitar o leitor completo, incluindo o caso GBP/NZD e a recusa após adulteração do arquivo temporário. Isso **não** constitui rerun real dos 103.600 candles originais nem CI do GitHub. O teste real continua exigido antes de liberar qualquer integração.
- A função é intencionalmente separada dos motores legados: **eles não estão automaticamente protegidos por esta nova porta**. Qualquer futuro backtest MT5 deve chamar a porta explicitamente e passar também por auditorias de proveniência de preços, agenda da corretora e dados macro *point-in-time* antes de gerar rótulos/vieses confiáveis.
- Sem merge, deploy, Worker, cobrança, sinal, probabilidade ou ordem. O material está somente em LAB e a PR continua rascunho.

**Próximo P0:** comprovar feriados/horários da corretora (com evidência datada e comparador independente), rodar a regressão da porta nos 84 snapshots do AM12 sem recopiar preços, e só depois decidir que lacunas podem ser tratadas como pausas legítimas. Integrar as fontes macro bilaterais pelo instante **em que foram publicadas**, não pela data da observação econômica.


## Revisão forense no AM12 — 07/11/2026: execução real e correção aritmética

O AM12 voltou a estar online. Foi confirmada a existência dos **84 CSV.gz e 7 manifestos originais** em `%LOCALAPPDATA%\AtlasQuant\LAB\MT5_Snapshots\20261107_AM12`. Os hashes SHA-256 dos scripts de classificação e proteção copiados em pasta temporária separada foram comparados aos arquivos do repositório e coincidiram. Os preços e manifestos **não foram modificados, copiados para a nuvem ou enviados ao GitHub**.

### Resultados observados na execução somente leitura

| Medida | Resultado real |
| --- | ---: |
| 28 pares, 84 séries, 103.600 velas | **Confirmados** |
| Candidatos a fim de semana M15 | **168** |
| Candidatos a fim de semana D1 | **2.800** |
| Lacunas D1 com revisão pendente | **87** |
| **Total de intervalos não nominais** | **3.055** |
| Segmentos separados em fronteiras não verificadas | **3.139** |
| GBP/NZD D1 30/09/2025 permanece bloqueado | **Sim** |
| Estado da porta | `BLOCKED_UNVERIFIED_GAPS` |
| Aprovado para backtest operacional | **Não** |
| Erros de integridade reportados pela porta | **0** |

**Retificação de soma:** o valor **2.968** não era o total de intervalos não nominais como descrito no adendo inicial; é a soma dos candidatos de fim de semana (168 + 2.800). As **87** lacunas D1 de revisão são adicionais. Portanto, **2.968 + 87 = 3.055**. A nova regressão real expôs esse erro na expectativa do teste, que foi corrigida. A classificação das 87 pendências, incluindo a exceção do GBPNZD, não mudou.

A primeira execução da nova suíte apresentou **27 PASS / 1 FAIL** devido **exclusivamente à expectativa aritmética incorreta** (`2968 - 87` e contagem de segmentos); a porta retornou os números reais e conservou `backtest_approved=False`. As duas expectativas foram corrigidas, os hashes SHA-256 do teste editado foram conferidos iguais no repositório de trabalho e no AM12, e a suíte foi reexecutada no AM12: **28/28 PASS (2,105 s), sem SKIP**. Também foi executada a CLI da porta diretamente contra o arquivo real: `BLOCKED_UNVERIFIED_GAPS`, **3.139 segmentos**, `gbpnzd_2025_09_30_blocked=True`, `backtest_approved=False`, zero erros de integridade. Nenhuma validação de dados macro P-I-T, calendário oficial do broker, corretora independente, acerto ou probabilidade foi feita nesta etapa.

**Próximo P0 após a regressão real:** buscar evidência oficial do *trading schedule* da corretora/servidor e comparação independente para a vela GBPNZD D1 30/09/2025; criar uma política documentada de exceções só depois dessa prova. Em paralelo, especificar os timestamps de publicação dos indicadores macro das duas moedas para prevenir vazamento de informação futura. Os motores legados de backtest ainda não foram conectados à nova porta de segurança.


## Corroboração externa — GBP/NZD, 30/09/2025 (LAB, evidência parcial)

**Fontes primárias consultadas, sem acesso à conta MT5:**

- **Jornal Oficial da União Europeia, C/2025/4506**, referente a **30/09/2025**, publicado em **01/10/2025**: `1 EUR = 0,87340 GBP` e `1 EUR = 2,0257 NZD`, com indicação explícita de que são taxas de referência publicadas pelo BCE. URL canônica: `https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=OJ:C_202504506`.
- **Banque de France**, quadro `Exchange rates (daily parities) - 2025-09-30`, publicado em 30/09/2025: confirma **GBP 0,8734** e **NZD 2,0257** para essa data, exibindo também 29/09 e 01/10 como dias adjacentes de publicação. URL: `https://www.banque-france.fr/en/statistics/rates-and-prices/exchange-rates-daily-parities-2025-09-30`.
- **BCE, metodologia:** taxas normalmente atualizadas por volta de **16:00 CET** em dias úteis (salvo fechamento TARGET), com concertação em torno de **14:10 CET**; o BCE desencoraja usá-las em transações. URL: `https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.eu.html`.

**Derivação matemática apenas indicativa:** `(2,0257 NZD/EUR) ÷ (0,87340 GBP/EUR) ≈ 2,319327 NZD/GBP`. É uma taxa **cruzada de referência**, não cotação OHLC GBPNZD da corretora e **não** substitui a vela ausente. A publicação no Jornal Oficial ocorreu em 01/10; o horário exato de liberação da observação de 30/09 em cada fonte ainda não foi certificado por artefato P-I-T. **Nunca associar essa taxa ao instante de abertura da vela D1 em 30/09 00:00 UTC**.

**Conclusão limitada:** há evidência oficial de taxas cambiais das duas moedas associadas a 30/09/2025. Isso enfraquece a hipótese de uma suspensão global das referências nesse dia, mas **não prova** que o servidor MT5/fornecedor deveria ter uma vela diária GBPNZD, nem identifica a causa da ausência. Referências do mesmo sistema BCE, ainda que espelhadas por bancos nacionais, não são duas fontes independentes de preços negociáveis. O caso segue como `REVIEW_UNEXPLAINED` e `BLOCKED_UNVERIFIED_GAP`; `broker_calendar_verified=False`, `historical_point_in_time_verified=False`, `backtest_approved=False`, `operational_bias=AGUARDAR`.

**Próxima prova que falta:** identificar de forma não sensível o nome da corretora/servidor e obter seu calendário de sessões **daquela época**; confrontar o GBPNZD D1 em uma segunda fonte de barras negociáveis com a mesma convenção de corte diário. Não consultar conta, saldo, posições, credenciais ou enviar ordens para isso. Somente após essa corroboração decidir política explícita de exceção, com hash e data da evidência, sujeita à porta fail-closed.


## Hipótese Pepperstone e horário da corretora — 07/11/2026 (LAB)

O proprietário informou **"Pepperstone, se eu não tô enganado"**. É uma hipótese plausível, **não uma identificação certificada do fornecedor que gerou os 84 CSV.gz**.

**Checagem mínima, sem informações de conta:** com o MT5 já aberto no AM12, uma sonda em pasta temporária usou somente `mt5.initialize`, `mt5.terminal_info` (campos `company`, `name`, `build`) e `mt5.shutdown`. Resultado: `company=MetaQuotes Ltd.`, `name=MetaTrader 5`, `build=6308`. **Isso identifica o fornecedor do software/terminal, não comprova se o servidor de preços do histórico é Pepperstone**. Não foram consultados `account_info`, `positions_get`, credenciais ou números de conta; nenhum login, ordem ou alteração de preços.

**Fontes primárias Pepperstone:**

- Página oficial `Market trading hours`, `https://pepperstone.com/en-gb/about-us/trading-hours`: horário Forex padrão de **terça a quinta, 00:01–23:59 no relógio do servidor**, e sexta até 23:55. O próprio site informa **GMT+3 durante o horário de verão dos EUA (março–novembro)** e **GMT+2 no horário padrão**. Trata-se da tabela **atual**, não de um certificado específico de **30/09/2025**. Mercados/pares podem ter exceções e feriados.
- Página oficial `Platform and tools support`, `https://pepperstone.com/en/support/platforms-and-tools`: a documentação de MT5 menciona, como exemplos, os hosts `mt5-1.pepperstone.com` (real) e `mt5-demo01.pepperstone.com` (demo). **Não** foram usados para autenticar ou modificar o terminal; constam apenas como referências para futura verificação do nome público do servidor, se fornecido pelo proprietário.

**Leitura da evidência:** 30/09/2025 foi uma terça-feira e os bancos centrais publicaram taxas de referência GBP/NZD associadas à data (adendo anterior). Assim, **se** o feed for de fato Pepperstone, a falta isolada do candle D1 é incompatível com o padrão semanal geral publicado atualmente e merece investigação como possível falha de cobertura, histórico ou convenção de sessão. **Não** podemos deduzir que Pepperstone cometeu erro, nem preencher OHLC, sem: (1) servidor de origem confirmado sem credenciais; (2) arquivo histórico do calendário/feriados de setembro de 2025; (3) OHLC GBPNZD de fonte independente com regra de fechamento diário comparável.

**Decisão P0 inalterada:** `GBPNZD:D1:2025-09-30=REVIEW_UNEXPLAINED`, barreira `BLOCKED_UNVERIFIED_GAP`, `broker_calendar_verified=False`, `historical_point_in_time_verified=False`, `backtest_approved=False`, `operational_bias=AGUARDAR`. A PR continua DRAFT, sem merge/deploy, trading, custo ou ativação dos motores legados.
