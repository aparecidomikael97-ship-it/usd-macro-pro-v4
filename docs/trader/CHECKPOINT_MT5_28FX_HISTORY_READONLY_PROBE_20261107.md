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


## Correção de proveniência após captura enviada pelo proprietário — 07/11/2026

O proprietário enviou **captura do painel Navegador do MT5** mostrando **Contas → MetaQuotes-Demo**. **Pepperstone não aparece nesse recorte**. A imagem continha identificadores de contas, que foram **deliberadamente omitidos** desta documentação; a imagem original **não foi enviada ao GitHub**. A inspeção visual comprova apenas o **rótulo de servidor agrupador visível na interface**, não qual conta estava ativa nem qual servidor originou historicamente os candles coletados.

**Retificação explícita do adendo anterior:** a hipótese declarada verbalmente de Pepperstone **não está confirmada** e **não deve ser aplicada como calendário do histórico do AM12**. O resultado anterior de `terminal_info.company=MetaQuotes Ltd.` identifica a fabricante do software; combinado com o Navegador, é consistente com um ambiente de demonstração MetaQuotes, mas **não é atestado de origem do feed da coleta**. Manter o campo de proveniência `MT5_TERMINAL_UNATTESTED`; não reetiquetar os 103.600 candles como Pepperstone ou MetaQuotes certificado.

**Consequências operacionais:**

1. A ausência isolada `GBPNZD D1 2025-09-30` continua `REVIEW_UNEXPLAINED` e `BLOCKED_UNVERIFIED_GAP`, sem preenchimento ou dedução de erro de corretora.
2. Calendários gerais da Pepperstone e referências do BCE permanecem **contexto externo**, não certificados do servidor que produziu os arquivos.
3. A futura verificação de proveniência deve confirmar o **servidor efetivamente conectado na coleta** usando método consentido que não revele login, número de conta, saldo ou credenciais. Se esse dado não puder ser confirmado, preservar `broker_calendar_verified=False` e não liberar backtests.
4. **GO-LAB apenas para auditoria**; `historical_point_in_time_verified=False`, `backtest_approved=False`, `operational_bias=AGUARDAR`. Sem merge, deploy, Worker, assinatura, ordens ou custo.


## Incremento LAB — matriz macro bilateral G8 para os 28 pares, D1/W1

**Implementação:** `atlasquant_trader_g8_macro_matrix_pit_lab.py` e `test_atlasquant_trader_g8_macro_matrix_pit_lab.py`. Reaproveita o gate de tempo existente em `atlasquant_trader_g8_macro_asof_lab.py`, sem reescrever o validador individual. **Não foram ingeridos dados macro reais nesta rodada.**

**Contrato conservador:**

1. Uma coleção única de evidências *alegadas* para cada uma das **8 moedas G8** é aplicada consistentemente aos **28 cruzamentos canônicos**. A mesma notícia de uma moeda não pode assumir valores diferentes em pares diferentes apenas por duplicação de formulários.
2. O processo é chamado separadamente para o instante de decisão **D1** ou **W1**. O gate de cada par exige `published_at_utc <= captured_at_utc <= decision_at_utc <= evaluated_at_utc` para todas as evidências fornecidas. Uma publicação/captura futura **não** é promovida retroativamente a dado conhecido na decisão; o par é rejeitado.
3. Se falta CPI ou taxa de política monetária de qualquer uma das moedas, o par fica incompleto; **ausência do registro não significa ausência real do indicador**. Cópias divergentes para o mesmo indicador/período são recusadas como *vintage* ambíguo.
4. Nenhum valor numérico é exportado para um motor de direção; saem apenas contagem e motivos de cobertura **de metadados declarados pelo chamador**. Hash, URL, origem e horários informados **não** constituem autenticação independente. `historical_point_in_time_verified=False`, `backtest_approved=False`, `operational_bias=AGUARDAR`, `score_0_to_10=None`, `directional_probability=None`, `trade_authorized=False` permanecem fixos.
5. Este componente **não** substitui nem está conectado ao bloqueio de lacunas do MT5. Os 103.600 candles permanecem na máquina, com origem ainda não certificada e com a exceção GBPNZD bloqueada.

**Testes locais:** **42/42 PASS**, reunindo as suítes já existentes de cronologia do par e junção MT5/macro com **12 novos cenários da matriz**. Os dados de teste são inteiramente **sintéticos**: 8 moedas completas geram 28/28 cruzamentos com **cobertura de alegações, não verificação econômica**; retirar CPI de NZD torna **7 pares** incompletos; uma publicação futura de GBP bloqueia **7 pares**; uma captura posterior à decisão e duplicatas de revisão também são recusadas. **Nenhum teste nesta rodada atestou indicadores econômicos reais ou gerou viés.**

**Próxima prova P0:** anexar, com origem verificável, calendários e releases CPI/juros para GBP, EUR, USD, NZD, JPY, CHF, CAD e AUD, preservando período observado, publicação original, primeira captura comprovada e cada revisão. Só depois associar preços e macro por ponto-no-tempo em backtest separado, com embargo e custo operacional. Sem merge, deploy, Worker, pagamento ou ordem.


## Incremento LAB — piloto macro real GBP/NZD com horários de divulgação

**Pesquisa em fontes primárias (08/11/2026 UTC), não captura arquivada point-in-time.** Esta etapa confirma quatro valores publicados nas páginas dos próprios órgãos, distinguindo o período da observação econômica da data/hora de divulgação:

| Fonte/documento oficial | Indicador e período | Valor na página | Evidência de disponibilidade local | Limite conservador UTC para pesquisa |
| --- | --- | --- | --- | --- |
| ONS, CPI britânico, `https://www.ons.gov.uk/economy/inflationandpriceindices/bulletins/consumerpriceinflation/september2026` | CPI 12 meses, setembro/2026 | **3,5%** | página de release ONS: **21/10/2026, 07h Londres (BST)**; `https://www.ons.gov.uk/releases/consumerpriceinflationukseptember2026` | 21/10, **06h00Z** |
| Stats NZ, `https://www.stats.govt.nz/information-releases/consumers-price-index-september-2026-quarter/` | CPI 12 meses, trimestre encerrado em setembro/2026 | **3,7%** | publicação: **22/10/2026, 10h45 Auckland (NZDT)** | 21/10, **21h45Z** |
| Bank of England, `https://www.bankofengland.co.uk/monetary-policy-summary-and-minutes/2026/november-2026` | Bank Rate, decisão 05/11/2026 | **4,00%** | publicação específica declara **05/11/2026**, sem horário próprio; política geral registra publicação do MPC às 12h, `https://www.bankofengland.co.uk/monetary-policy` | **06/11, 00h00Z** (início do dia seguinte; **não é horário de divulgação**) |
| RBNZ, `https://www.rbnz.govt.nz/news-and-events/news/2026/10/ocr-held-at-2-75-percent` | OCR, decisão 28/10/2026 | **2,75%** | página pública de taxa registra **atualizado às 14h NZDT de 28/10** em `https://www.rbnz.govt.nz/monetary-policy/about-monetary-policy/the-official-cash-rate`; **não prova horário de arquivamento da comunicação específica** | 28/10, **01h00Z** |

**Cuidado econômico:** CPI da GBP é mensal e da NZD é trimestral: não são observações de frequência idêntica. Juros nominais, CPI e diferenças de taxas **não produzem, isoladamente, recomendação ou viés**. A data de pesquisa é distinta do período e do horário em que o órgão publicou.

**Código LAB:** `atlasquant_trader_gbp_nzd_official_pilot_lab.py` e `test_atlasquant_trader_gbp_nzd_official_pilot_lab.py`. Uma consulta com corte anterior ao limite UTC **oculta o número futuro**; depois dele, o número é exposto somente em campo rotulado `research_value_percent`, marcado como evidência histórica não atestada. Para a decisão BoE com horário específico não demonstrado, o gate só permite *contexto de pesquisa* no dia seguinte. Para RBNZ, a hora vem da página mutável de taxa, não de uma cópia contemporânea autenticada.

**Testes locais:** **56/56 PASS** (14 novos cenários do piloto + 42 dos gates existentes de matriz/as-of/junção), com dados de relógio sintéticos nos testes. Nenhum arquivo macro original foi baixado e arquivado com cadeia de custódia, nenhum hash de bytes oficiais foi atestado, e não há evidência de primeira captura/revisões para emissão histórica. `historical_capture_attested=False`, `point_in_time_backtest_approved=False`, `operational_bias=AGUARDAR`; preço MT5 e broker seguem bloqueados nos pontos anteriormente identificados. **Sem merge, deploy, Worker, agendamento, cobrança ou ordens.**

**Próximo P0:** capturar versões originais com timestamp independente verificável e revisões, comparar **surpresas** com expectativas disponíveis na época, depois vincular às 28 séries respeitando os gaps e o horário do servidor, antes de backtest fora da amostra.


## Incremento LAB — correção CPI trimestral e cadeia local de versões macro GBP/NZD

**Problema concreto corrigido:** a porta `atlasquant_trader_g8_macro_asof_lab.py` aceitava período econômico CPI somente como `YYYY-MM` e aplicava 60 dias de validade para todos os CPIs, embora **Stats NZ tenha publicado CPI trimestral `2026-Q3` em 22/10/2026 e agendado a publicação seguinte para 27/01/2027**. Isso provocaria rejeição do período trimestral ou falsa condição `STALE` antes do próximo dado. Fontes: `https://www.stats.govt.nz/information-releases/consumers-price-index-september-2026-quarter/` e `https://www.stats.govt.nz/indicators/consumers-price-index-cpi/`.

**Correção conservadora:**

1. CPI agora aceita `YYYY-MM` (frescor estrutural de 60 dias) ou `YYYY-Q[1-4]` (frescor estrutural de 120 dias). **A regra é determinada pelo formato da observação**, não por moeda fixa: isso evita impor CPI trimestral à NZD após eventual migração da fonte para divulgação mensal em 2027.
2. Observação trimestral só é estruturalmente aceita depois de **encerrado o trimestre**; `2026-Q4` com publicação em outubro/2026 e `Q0/Q5` são recusados. `POLICY_RATE` continua exigindo `YYYY-MM` e não recebe validade trimestral.
3. A seleção explicita `observation_frequency` e `freshness_limit_days` por indicador. Esses limites são política de triagem LAB, não garantia de disponibilidade da próxima divulgação. Calendários reais precisam prevalecer; um dado de inflação pode ficar obsoleto por revisão/evento antes desse limite. Nenhuma attestation ou viés foi concedido.

**Novo contrato de versões:** `atlasquant_trader_gbp_nzd_vintage_chain_lab.py` e `test_atlasquant_trader_gbp_nzd_vintage_chain_lab.py`. Aceita apenas bytes **fornecidos pelo chamador**, de uma das **quatro URLs exatas** do piloto GBP/NZD. Checa tamanho, SHA-256 de conteúdo, metadados HTTP alegados, hora de captura alegada, ordenação estrita por documento, ID de revisão único e encadeamento SHA-256 com antecessor. No corte de decisão, seleciona **a última versão alegadamente capturada até aquele momento**, bloqueando contaminação estrutural por revisão posterior. Não interpreta valores econômicos e não registra cópias reais em GitHub.

**Limite de evidência crucial:** nenhum snapshot real das páginas foi capturado ou armazenado nesta etapa; testes usam bytes deliberadamente **sintéticos**. Mesmo uma cadeia consistente pode ser inteiramente remontada e retrodatada por seu próprio emissor. Faltam testemunha independente de horário, arquivo original do servidor, verificações de origem TLS e selo externo de cadeia. Por isso `original_historical_capture_attested=False`, `point_in_time_backtest_approved=False`, `operational_bias=AGUARDAR`, `trade_authorized=False` continuam invariantes. O caso da vela GBPNZD D1 de 30/09/2025 e a proveniência MT5 seguem pendentes, sem preenchimento.

**Validação local:** **78/78 PASS** (56 testes anteriores, 6 novos cenários de CPI trimestral e 16 de cadeia de versões). Cenários incluem revisão posterior à decisão, captura anterior à publicação, duplicata, hash adulterado, clocks inválidos, URL não permitida e ausência de prova independente. PR permanece DRAFT sem merge, deploy, Worker, agendamento, ordens ou custo novo.

**Próxima prova P0:** obter capturas autenticáveis de origem e carimbo externo a partir da data real de coleta (não inventar histórico de captura), conservar vintages e revisões, e só então estudar junção temporal das surpresas macro às 28 séries e separar dados aptos/inaptos a backtest. 


## Incremento LAB — captura HTTP real das publicações GBP/NZD no AM12 (08/11/2026 UTC)

**Resultado observado no AM12, sem conta MT5:** o coletor Python stdlib `atlasquant_trader_gbp_nzd_official_capture_lab.py` foi colocado na pasta LAB isolada `%LOCALAPPDATA%\\AtlasQuant\\LAB\\MacroOfficial\\20261108_GBPNZD_PILOT`. **Hash SHA-256 normalizado do script executado no AM12 = `371291eff2053347eb2db04d12e33cb08e1cdd6977ce20d08f5c9b12b0e18f32`**, idêntico ao arquivo local testado. Nada foi escrito na árvore de preços MT5, arquivos da conta ou configurações operacionais. Apenas páginas públicas fixadas; HTTPS stdlib padrão, sem desabilitar validação de certificado, redirects limitados ao mesmo hostname, GET limitado a 2 MiB, escrita exclusiva (sem sobrescrever arquivo histórico), leitura posterior e comparação SHA-256.

**Três HTMLs reais baixados com HTTP 200 e manifesto JSON local por documento**, registrados abaixo como SHA dos bytes da resposta HTTP recebida, sem envio dos corpos ao GitHub:

| Documento | Captura UTC (relógio AM12) | Bytes | SHA-256 do HTML local | SHA-256 do manifesto JSON local | HTTP Date do servidor | Título HTML observado |
|---|---|---:|---|---|---|---|
| ONS CPI GBP setembro/2026 | `2026-11-08T03:00:10Z` | 145100 | `e072c7cb9810acb7fae428e9e25c44d4f682554a0a9a723c585110d877e9b731` | `a6c3a0fe8c3712113492f57f0fc5b6e05a580b3375b869c7536f31ba6704b9fe` | 03:00:15Z | Consumer price inflation, UK - Office for National Statistics |
| Stats NZ CPI NZD trimestre setembro/2026 | `2026-11-08T03:00:16Z` | 87900 | `60d8a4e18bab2aa456ad4db023f328c9bb91a094f58b6057928450fd22ddb35f` | `c52909a02c17c7154a73c47b0d92281896dd74c4cde7344d2c2d1ea369cb3a6f` | 03:00:18Z | Consumers price index: September 2026 quarter - Stats NZ |
| BoE Bank Rate GBP novembro/2026 | `2026-11-08T03:00:17Z` | 104879 | `288a9039e016a279fd2ca264dd43628ff124226606060f71d309322b03833433` | `71c91d79c9aaf7f26d3387bdb22710dde5f8aca994a1131a5bc96a04f26b2090` | 03:00:23Z | Bank rate increased to 4% - November 2026 Monetary Policy Summary and Minutes |

HTTP Date ficou de 1 a 5 segundos à frente do horário final observado no AM12; isso **não** é carimbo independente, apenas outro cabeçalho alegado pelo servidor. O script armazena hora inicial/final UTC do sistema, URL de origem/final, status e tipo HTTP, hash/bytes do corpo, metadados e flags NO-GO. Sua execução final informou `LOCAL_INTEGRITY_PASS` para **3/3 manifestos**, zero falha; uma **segunda execução somente de leitura** repetiu `3/3 PASS`. O registro dos digests neste commit GitHub é posterior à coleta e ajuda a detectar alterações futuras, **não** prova que a página exibia esses bytes na data da divulgação de outubro/novembro.

**Quarta fonte bloqueada:** a URL fixada de release RBNZ (`https://www.rbnz.govt.nz/news-and-events/news/2026/10/ocr-held-at-2-75-percent`) devolveu **HTTP 403 Forbidden** para a consulta automatizada, confirmado em diagnóstico read-only. Nenhum HTML dessa fonte foi capturado e **não** foi usada rota alternativa para contornar a restrição. O dado oficial do OCR 2,75% permanece apenas como pesquisa web anterior, não como arquivo bruto com integridade local comprovada.

**Testes de desenvolvimento:** **92/92 PASS locais** (78 anteriores + 14 novos do coletor, com respostas HTTP sintéticas e diretório temporário); casos de corpo adulterado, arquivo órfão, host/redirect inesperado, conteúdo muito grande, HTTP errado, caminho inseguro e duplicidade sem sobrescrita. As três cópias reais foram validadas **no AM12**, separadamente dos testes sintéticos. Nenhum arquivo fonte real foi enviado ao GitHub.

**Regras:** `source_http_body_captured_now=True` apenas nas três fontes; `issuer_document_semantics_verified=False` no coletor, `independent_timestamp_authority_verified=False`, `historical_vintage_at_original_release_verified=False`, `historical_backtest_authorized=False`, `operational_bias=AGUARDAR`, sem confiança estatística, sem merge/deploy/worker/agendamento/trade ou novo custo. Origem MT5 e lacuna GBPNZD D1 30/09/2025 continuam pendentes.

**Próximo P0:** fechar a quarta fonte por canal oficial autorizado (sem contornar HTTP 403); implementar auditoria dos valores dentro dos arquivos HTML que foram guardados, cruzar releases com calendário de revisões e preservar digests em commit de revisão. O corpus capturado agora só pode contribuir, após verificações adicionais, para decisões **posteriores à sua coleta**, nunca provar vintages retroativos de 2025–2026.


## Incremento LAB — verificador semântico offline dos 3 HTMLs oficiais capturados

**Contexto:** Mikael estava apenas pelo celular em 08/11/2026; dispositivo AM12 observado como **OFFLINE** no Desktop Commander (último contato ~6h antes). Portanto, **não** foi lido nenhum dos três HTMLs salvos na máquina nesta etapa, não se fez coleta nova e **não** houve validação de conteúdos reais agora. A auditoria continua pronta para ser executada quando o dispositivo autorizado voltar a ficar disponível.

**Novo verificador somente de leitura:** `atlasquant_trader_gbp_nzd_snapshot_semantics_lab.py`, com testes `test_atlasquant_trader_gbp_nzd_snapshot_semantics_lab.py`. Lê exatamente os nomes de 3 arquivos e seus manifestos JSON listados na seção de captura anterior, fixando **dois SHA-256 por documento** (HTML e manifesto) a partir do checkpoint já registrado no GitHub. Rejeita arquivo ausente, bytes/manifesto divergente, fonte ou período falsificados, URL diferente, metadata incongruente, HTTP inesperado ou UTF-8 inválido.

**Verificação de conteúdo planejada:** usa `HTMLParser` da biblioteca-padrão para verificar **texto visível** (ignora `script/style/noscript/template/svg`). Cruza título, período, texto contextual de inflação ou decisão de juros, e data de divulgação:

- ONS/GBP: CPI 12 meses `3.5%`, setembro/2026, data `21 October 2026`;
- Stats NZ/NZD: CPI 12 meses `3.7 percent`, trimestre setembro/2026, data `22 October 2026`;
- BoE/GBP: Bank Rate `4%`, decisão de 4/nov com anúncio em 5/nov/2026.

Os marcadores são **heurísticas de conteúdo textual** apoiadas em páginas oficiais, não uma extração normalizada do indicador, nem prova de primeiro anúncio original ou de ausência de revisão. Se os marcadores estiverem ausentes, resultado será `LAB_SEMANTIC_REVIEW_REQUIRED`, nunca preenchimento automático. Mesmo com todos verdadeiros, resultado é `LAB_VISIBLE_CONTEXT_MATCH_UNATTESTED`, não aptidão a viés. O quarto documento RBNZ **não** está no conjunto de pins (coleta negada por HTTP 403), permanece pendente sem tentativa de contornar o acesso.

**Testes locais (arquivos HTML sintéticos exclusivamente): 104/104 PASS**, sendo **12 novos** para este verificador e **92 anteriores**. Verificam pin das 3 fontes, texto oculto em script, período divergente, alteração de 1 byte no corpo ou manifesto, fonte falsa, UTF-8 inválido, ausência de arquivo e saída `NO-GO`. **Ainda não há resultado de `audit_am12_directory_lab` executado contra os arquivos oficiais reais**. Nenhuma compra, instalação, serviço em background, conexão à conta MT5, merge, publicação ou ordem.

**Próximo P0:** assim que o AM12 estiver online, executar **somente leitura** `python atlasquant_trader_gbp_nzd_snapshot_semantics_lab.py --capture-dir <pasta LAB da captura>` e revisar possíveis diferenças do HTML real, sem afrouxar os hashes. Depois reconciliar release e revisão e, por fim, ampliar fontes às 8 moedas e 28 pares. `historical_backtest_authorized=False` e `operational_bias=AGUARDAR` seguem invariantes.


## Incremento LAB — catálogo oficial USD/EUR (08/11/2026; sem AM12)

**Escopo:** expandir as pesquisas oficiais para USD e EUR da matriz de 28 pares, sem acessar a conta, executar ordens ou promover vieses. O AM12 foi observado **OFFLINE**; nenhum HTML/CSV dele foi lido ou alterado, nenhum novo corpo HTTP de fonte oficial foi capturado nesta etapa. Fontes verificadas por leitura web em 08/11, não por snapshot P-I-T.

**Novo módulo:** `atlasquant_trader_usd_eur_official_pilot_lab.py` e 15 testes `test_atlasquant_trader_usd_eur_official_pilot_lab.py`. Cinco observações independentes, cada uma com **período econômico**, **data de anúncio**, **limite conservador de disponibilidade**, **fase da publicação**, **definição do indicador** e URL oficial:

1. **USD inflação:** BLS CPI-U anual de setembro/2026 **3,7%**, comunicado de **14/10/2026 08h30 EDT = 12h30 UTC**. https://www.bls.gov/news.release/archives/cpi_10142026.htm
2. **EUR inflação definitiva:** Eurostat HICP da zona do euro em setembro/2026 **3,8%**, comunicado de **16/10/2026**. Hora específica não estabelecida; simulação só considera após **17/10/2026 00h00 UTC** (limite conservador, não horário de publicação). https://ec.europa.eu/eurostat/en/web/products-euro-indicators/w/2-16102026-ap
3. **USD juros:** FOMC de **28/10/2026 às 14h EDT = 18h UTC** manteve a faixa de meta de Fed Funds **3,75%–4,00%**. Guardada como **RANGE**, sem inventar taxa-ponto ou usar ponto médio. https://www.federalreserve.gov/newsevents/pressreleases/monetary20261028a.htm
4. **EUR juros:** BCE decisão de **29/10/2026**, taxa de depósito **2,50%** (operações principais de refinanciamento 2,65%, cedência marginal 2,90%). Hora da decisão não provada na página, embora haja horário de coletiva; limite conservador **30/10/2026 00h00 UTC**. **Não comparar como instrumentos equivalentes com faixa do Fed.** https://www.ecb.europa.eu/press/pr/date/2026/html/ecb.mp261029~9a493adf17.en.html
5. **EUR inflação preliminar:** Eurostat *flash* HICP de **outubro/2026 4,0%**, divulgado em **04/11/2026**, disponível no piloto após limite conservador **05/11/2026 00h00 UTC**. **Não** é a versão definitiva de outubro, prevista para **18/11/2026**; **não substitui** a observação final de setembro. https://ec.europa.eu/eurostat/web/products-euro-indicators/w/2-04112026-ap

**Teste temporal:** o piloto oculta valores até o limite respectivo, inclusive bloqueando o segundo anterior; distingue CPI-U/HICP, prévia/final, faixa/ponto, recusa datetimes sem timezone e preserva abstinência. Os **15 testes novos passaram**; a bateria LAB ampliada registrou **126 testes (125 OK, 1 ignorado)**, sendo o ignorado o que necessita dos manifestos locais do AM12. *Testes de lógica são sintéticos, não verificação dos bytes econômicos originais nem prova da publicação histórica.*

**NO-GO explícito:** `historical_capture_attested=False`, `point_in_time_backtest_approved=False`, `macro_cross_currency_comparison_approved=False`, `forecast_probability=None`, `operational_bias=AGUARDAR`, `trade_authorized=False`. Não existe sinal USD/EUR, validação estatística de acerto ou autorização de negociação. CPI-U EUA e HICP europeu têm cestas/metodologias distintas; inflação isolada e diferença nominal de juros não formam viés cambial, pois faltam surpresas versus consenso, trajetória de política, micro e geopolítica. Pendências anteriores (GBPNZD D1 30/09/2025, corretora/servidor MT5 não certificados, teste semântico dos 3 HTMLs reais no AM12 e RBNZ HTTP 403) permanecem.

**Próximo P0:** quando o AM12 voltar, aplicar auditoria de conteúdo **somente leitura** aos 3 HTMLs reais já coletados e manter a quarta fonte RBNZ como indisponível; depois vincular releases a calendários/expectativas verificáveis sem olhar o futuro. Sem merge, deploy, worker, agendamento, gastos ou trades.


## Incremento LAB — inventário de cobertura de pesquisa oficial G8/28, D1 e W1 (08/11/2026)

**Contexto:** AM12 consultado via Desktop Commander: **OFFLINE** (~8 horas desde último contato). Nenhum dado real remoto foi tocado. Avanço apenas no código de inventário da mesma branch de LAB, sem inferir compra/venda.

**Novo módulo:** `atlasquant_trader_g8_official_research_coverage_lab.py`, acompanhado de `test_atlasquant_trader_g8_official_research_coverage_lab.py`. Consome os dois **catálogos de pesquisa de páginas oficiais** já registrados: GBP/NZD e USD/EUR. Varre todas as 8 moedas canônicas e 28 cruzamentos e lista **apenas a presença de pesquisas** nas famílias INFLATION e POLICY com limite conservador por data do anúncio. Não exporta valores econômicos, diferenciais, força de moeda, score, probabilidades ou sinais; não aceita dados fornecidos por usuário e não cria recibo certificado para o gate G8 P-I-T. A indicação de publicação é retrospectiva, não captura original ou garantia anti-revisão.

**Inventário para corte de pesquisa em 08/11/2026:** moedas com pesquisas publicadas de inflação e política: **USD, EUR, GBP, NZD (4/8)**. Moedas sem pesquisa completa: **AUD, CAD, CHF, JPY (4/8)**. Cruzes com pesquisa retrospectiva de duas moedas: **6/28**; uma moeda: **16/28**; nenhuma moeda: **6/28**. Este agrupamento combinatório descreve estritamente **cobertura da pesquisa**, e jamais maturidade operacional. Em todas as 28, `backtest_approved=False` e `operational_bias=AGUARDAR`. FOMC permanece faixa e HICP setembro/final e outubro/flash permanecem registros separados, sem conversão ou valor sintetizado.

**Segurança temporal:** corte antes dos anúncios retorna zero moeda apta à cobertura e todos os pares sem duas famílias; um segundo antes do limite da prévia HICP outubro não a utiliza. Timezones normalizados; cortes sem timezone, com microssegundo ou TF diferente de D1/W1 ficam bloqueados. Mesmo após todos os limites, não há prova de captura histórica, fonte imutável, vintage, surpresa versus consenso, preço certificado ou validação estatística; nenhum número pode ir ao motor de força cambial.

**Testes:** **17/17 novos aprovados**. A bateria LAB combinada deste recorte registrou **143 testes descobertos: 142 passaram e 1 foi ignorado** por depender de arquivos de candles existentes só no AM12. Resultados locais de lógica sintética, não reexecução dos HTMLs reais no dispositivo, nem verificação de GitHub Actions.

**Próximo P0:** (1) AM12 online: auditoria semântica read-only dos três HTMLs originais GBP/NZD com hashes pinados; (2) resolver dados de AUD/CAD/CHF/JPY usando fontes primárias e horários verificáveis; (3) obter vintages certificados/consenso temporalmente alinhado antes de avaliar força ou viés. Pendências MT5 (conta demonstrativa MetaQuotes, Pepperstone não certificada), GBPNZD 30/09/2025 e RBNZ HTTP 403 permanecem. Sem custos, merge, deploy, worker, scheduler, ordens ou alteração em conta.


## Incremento LAB — AUD/CAD oficiais e matriz G8 de pesquisa atualizada (08/11/2026)

**Escopo:** avançar com pesquisa de fontes primárias para AUD/CAD, sem AM12, sem terminal MT5 ou qualquer conta. O novo `atlasquant_trader_aud_cad_official_pilot_lab.py` registra quatro publicações com períodos econômicos e limites temporais separados, e `test_atlasquant_trader_aud_cad_official_pilot_lab.py` exercita cronologia e recusa. As páginas foram **pesquisadas em 08/11**, sem captura original contemporânea de outubro/novembro nem garantia de não-revisão.

- **Austrália CPI:** ABS, inflação CPI *all groups* anual de **4,3%** em setembro/2026. Página oficial afirma publicação em **28/10/2026 11h30 AEDT = 00h30 UTC**. https://www.abs.gov.au/media-centre/media-releases/cpi-rose-43-year-september-2026
- **Canadá CPI:** Statistics Canada, CPI *all-items* anual **3,1%** em setembro/2026, boletim **19/10/2026**. Página específica confirma data, não hora; usar corte conservador de pesquisa **20/10/2026 00h00 UTC**, que **não é o horário real da divulgação**. https://www150.statcan.gc.ca/n1/daily-quotidien/261019/dq261019a-eng.htm
- **Canadá juros:** Bank of Canada, decisão de **28/10/2026**, meta da taxa overnight **2,50%** (não confundir com *Bank Rate* 2,75% ou taxa de depósito 2,45%). Página de agendamento previa anúncio às 09h45 ET, mas não prova captura histórica do comunicado naquele segundo; corte de pesquisa conservador **29/10/2026 00h00 UTC**. https://www.bankofcanada.ca/2026/10/fad-press-release-2026-10-28/ e https://www.bankofcanada.ca/2026/10/fad-announcement-release-mpr-2026-10-28/
- **Austrália juros:** RBA, decisão de **03/11/2026** elevou meta da *cash rate* a **4,85%**; **vigência 04/11/2026**, distinta da data do anúncio. RBA declara política de divulgação às 14h30 Sydney, sem prova do instante da página individual, então corte de pesquisa conservador **04/11/2026 00h00 UTC**. https://www.rba.gov.au/media-releases/2026/mr-26-30.html e https://www.rba.gov.au/cash-rate-target-overview.html

**Atualização do inventário** `atlasquant_trader_g8_official_research_coverage_lab.py` e testes: acrescentado terceiro catálogo ao G8 sem importar números para cálculo de moeda forte/fraca. Em 08/11 às 12h UTC, **6/8 moedas** com pesquisa publicada de inflação e decisão de política (**USD, EUR, GBP, NZD, AUD, CAD**), **CHF e JPY ainda sem pesquisa completa**. Nos 28 pares: **15** com duas moedas pesquisadas, **12** com apenas uma e **1** sem as duas; números combinatórios são **cobertura retrospectiva da pesquisa**, não qualidade de previsão ou prontidão operacional. No corte anterior às publicações não aparecem documentos futuros.

**Testes locais:** 14 novos do piloto AUD/CAD e testes da matriz ajustados; bateria ampliada neste recorte **157 testes: 156 OK, 1 ignorado** por depender dos snapshots de preços reais do AM12 indisponível. Sem teste com HTML/CPI real arquivado originalmente no AM12 e sem prova de CI GitHub.

**NO-GO invariável:** `historical_capture_attested=False`, `point_in_time_backtest_approved=False`, `macro_cross_currency_comparison_approved=False`, `forecast_probability=None`, `operational_bias=AGUARDAR`, `trade_authorized=False`; **nenhum dado financeiro foi convertido em sinal, retorno esperado ou probabilidade**. O inventário não certifica vintages P-I-T e não alimenta o gate de macro bilateral. Falta pesquisa primária para CHF/JPY, auditoria dos 3 HTMLs reais GBP/NZD, fonte RBNZ HTTP 403 e lacuna D1 GBPNZD 30/09/2025. Sem merge, deploy, worker, scheduler, trade, ou novo custo.


## Incremento LAB — CHF/JPY, fechamento de pesquisa básica G8/28 (08/11/2026)

**Escopo e honestidade:** pesquisa em páginas oficiais públicas em **08/11**, não arquivo bruto contemporâneo de cada anúncio em setembro/outubro/novembro. Todos os números são **valores de pesquisa**, sem certificado de vintage P-I-T, sem fonte imutável revisional, sem expectativas macro ou dados estatisticamente validados para estimar viés. Fontes continuam isoladas do motor de força cambial e de qualquer backtest.

**Novo catálogo** `atlasquant_trader_chf_jpy_official_pilot_lab.py`, acompanhado por 15 testes de cronologia e recusa em `test_atlasquant_trader_chf_jpy_official_pilot_lab.py`. Quatro observações com período econômico, métrica, data do emissor, precisão do relógio e corte de consulta:

1. **CHF juros:** Swiss National Bank (SNB), decisão de **24/09/2026** manteve a **SNB policy rate em 0,0%**. Documento comprova a data, sem horário específico certificado nesta pesquisa; corte conservador **25/09/2026 00h00 UTC**, que não é o horário efetivo da divulgação. https://www.snb.ch/en/publications/communication/press-releases-restricted/pre_20260924
2. **JPY inflação:** Statistics Bureau do Japão, CPI nacional **all items 2,1% a/a**, período **setembro/2026**, publicação em **23/10/2026**. Não confundir com CPI sem alimentos frescos, embora este também mostre 2,1%; hora específica não certificada → corte conservador **24/10/2026 00h00 UTC**. A URL de resumo é **rotativa/mutável**, e isso impede tratá-la como versão congelada de outubro: https://www.stat.go.jp/data/cpi/sokuhou/tsuki/index-z.htm
3. **JPY juros:** Bank of Japan, declaração PDF de **30/10/2026** estabelece meta para taxa *uncollateralized overnight call* de **aproximadamente 1,25%**, não uma taxa pontual incondicional e não a taxa de depósito. O PDF declara explicitamente lançamento **12h02 JST = 03h02 UTC**, página 3 da declaração, fornecendo a fronteira cronológica exata de publicação para pesquisa. https://www.boj.or.jp/en/mopo/mpmdeci/mpr_2026/k261030a.pdf
4. **CHF inflação:** Federal Statistical Office (FSO), CPI suíço **1,5% a/a** em **outubro/2026**, publicado em **03/11/2026**. Hora específica não estabelecida → corte conservador **04/11/2026 00h00 UTC**. https://www.bfs.admin.ch/en/newnsb/UA8hylpLYO6i

**Matriz de pesquisa atualizada**: `atlasquant_trader_g8_official_research_coverage_lab.py` agora consome quatro pilotos (GBP/NZD, USD/EUR, AUD/CAD, CHF/JPY) e cruza o universo canônico dos oito códigos de moeda com 28 pares sem carregar valores em sinais. Para o corte de pesquisa em 08/11/2026 UTC, **8/8 moedas têm estudos de páginas oficiais de inflação e juros**, portanto **28 pares têm as duas moedas pesquisadas** (antes 15/28). É cobertura de **pesquisa retrospectiva**, não cobertura de dados de alta qualidade verificados nem indicador de acurácia: todos os pares seguem `backtest_approved=False`, `historical_pit_verified=False`, `operational_bias=AGUARDAR`.

**Testes locais:** **15/15 novos** do catálogo CHF/JPY; a bateria LAB composta registrou **172 casos: 171 PASS e 1 SKIP** (arquivo de candles real reside só no AM12). Testes de código com fontes constantes sintéticas, não reauditoria dos valores das páginas guardados em snapshot, nem execução CI confirmada no GitHub. Casos incluem primeiro segundo de divulgação BOJ, bloqueio um segundo antes, relógios sem fuso, timestamp com microssegundos, métrica all-items, página japonesa mutável e taxa BOJ marcada como *around*.

**Próximo P0:** dado que a cobertura superficial G8/28 foi preenchida, parar de chamar esse estado de prontidão. A tarefa substantiva passa a ser autenticar vintages de cada indicador e seus horários de disponibilidade, auditar no AM12 os três HTMLs já salvos (sem extrapolar ao RBNZ 403), identificar revisões/consensos publicáveis e só então sincronizar com snapshots de preços. A lacuna GBPNZD D1 30/09/2025 e a origem do broker (navigator MetaQuotes-Demo; Pepperstone não confirmada) continuam sem certificação. Sem worker, agendamento, merge, deploy, custos ou ordens. `historical_capture_attested=False`, `point_in_time_backtest_approved=False`, `forecast_probability=None`, `trade_authorized=False`.


### 2026-11-08 — Auditoria de evidências de publicação das 8 moedas (LAB, leitura somente)

- AM12 permanece offline: não houve acesso à instância MT5, nova captura, nova verificação dos arquivos de prova locais ou execução do auditor semântico sobre os HTML reais neste checkpoint.
- Novo auditor local: `atlasquant_trader_g8_publication_evidence_audit_lab.py` e testes `test_atlasquant_trader_g8_publication_evidence_audit_lab.py`.
- Cobertura classificada: 17 observações de pesquisa em fontes oficiais usadas pelos pilotos de GBP/NZD, USD/EUR, AUD/CAD e CHF/JPY. Delas, 6 registram horário exato declarado pelo publicador, 10 dependem de data civil com horário conservador e 1 é página corrente da OCR da Nova Zelândia com data de atualização (não prova a publicação histórica da taxa anterior).
- A página do CPI nacional do Japão foi sinalizada como potencialmente rotativa (`latest release`). Nenhuma página é tratada como cópia original/imutável de uma divulgação histórica apenas pelo URL ou por ser domínio oficial.
- Existem relatos anteriores de 3 capturas de corpo HTML no AM12; não foram reabertas nem verificadas neste turno, e nenhuma equivale automaticamente a um vintage point-in-time original.
- A auditoria **não** certifica histórico revisado, consenso pré-publicação, horários completos nem as versões que eram conhecidas ao mercado em cada data. Resultado: **0 vintages históricos P-I-T comprovados, 0 pares habilitados para backtest/probabilidades, 28/28 pares com cobertura apenas de pesquisa, viés operacional AGUARDAR**.
- Regressão LAB offline com 12 módulos: **191 testes executados, 190 PASS, 1 SKIP** condicionado aos arquivos locais do AM12; acréscimo de 19 testes desta auditoria.
- Sem ordens, sinais operacionais, porcentagens de acerto inventadas, worker, execução externa, merge, deploy ou nova cobrança. PR #1851 continua rascunho. Próximo P0: aguardar retorno autorizado do AM12, revalidar os três HTML e avançar comprovação das versões históricas e do calendário da corretora.
