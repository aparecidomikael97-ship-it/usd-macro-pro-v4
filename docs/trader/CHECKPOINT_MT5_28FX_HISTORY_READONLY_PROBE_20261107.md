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
