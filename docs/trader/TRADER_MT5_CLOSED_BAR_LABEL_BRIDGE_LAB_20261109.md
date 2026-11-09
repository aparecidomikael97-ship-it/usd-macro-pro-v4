# AtlasQuant Trader — Leitor conservador de resultado D1/W1 do arquivo MT5 (LAB)

**Desenvolvido em 09/11/2026 (UTC).** Escopo: 28 pares Forex G8; sem índices nesta função, sem novas consultas MT5, sem ordens, worker, agendamentos, merge, deploy ou gastos.

## Situação e fonte real

- O notebook **AM12 está offline no Desktop Commander** nesta sessão. Portanto **não foi possível abrir os 84 CSV.gz / 103.600 candles originais** nesta rodada. Não foi executado backtest real nem calculada qualquer taxa de acerto.
- Os arquivos reais permanecem no AM12, em `%LOCALAPPDATA%\AtlasQuant\LAB\MT5_Snapshots\20261107_AM12`. O repositório guarda só código, testes sintéticos e documentação.
- A auditoria anterior identificou uma ausência isolada do candle **GBPNZD D1 30/09/2025** e outras lacunas/candidatos a pausas de mercado. Não interpretar automaticamente nenhuma delas como feriado; não preencher valores.

## Novo arquivo

- `atlasquant_trader_mt5_closedbar_outcome_lab.py`
- `test_atlasquant_trader_mt5_closedbar_outcome_lab.py`

A função `inspect_mt5_closedbar_outcome_lab` recebe uma **previsão já congelada** (par, D1/W1, `decided_at`, `prediction_locked_at`, SHA alegado), o horário do candle-alvo e o diretório de cópias locais. Ela abre os manifestos de lotes, localiza um dos CSV.gz, verifica hash SHA-256 do CSV original descompactado, os campos e números OHLC, a quantidade de linhas (D1=500, W1=200), o período UTC e a captura *posterior* ao fechamento da série.

Não permite rótulo quando há arquivo ausente, captura impossível, duplicata no manifest, tempos invertidos, candle ainda aberto, preço inválido ou diferença não nominal **imediatamente antes do candle**. Não usa fechamento seguinte no lugar de fechamento ausente. O rótulo eventual é `ALTA`, `BAIXA` ou `SEM_VARIACAO` **para a própria vela**, calculado de `open` e `close` (não é previsão nem recomendação). Um preço final igual ao inicial deve contar como **erro** para uma hipótese ALTA/BAIXA no comparador de vieses.

**Limite importante:** a checagem da adjacência é restrita ao candle-alvo e seu predecessor imediato. Ela **não** homologa os 32 candles usados pelo filtro de regime nem substitui a auditoria global de 84 séries `atlasquant_mt5_backtest_gap_guard_lab.py`. O módulo mantém explicitamente `full_archive_84_series_reaudited_here=False`.

Mesmo resultado documental válido retorna `LAB_ARCHIVED_BAR_DOCUMENTARY_ONLY_NO_GO`, `operational_bias=AGUARDAR`, `publishable=False`, `trade_authorized=False`, `calibrated_direction_probability=None`. O hash do arquivo e horários no manifesto são **alegações locais**: não provam feed da corretora, disponibilidade histórica no tempo da decisão, previsão registrada externamente antes do candle ou precisão futura. Esses controles são indispensáveis antes de alimentar estatísticas de acerto do produto.

## Próxima execução segura quando o AM12 ficar disponível

1. Ler **somente** os arquivos já arquivados; não refazer a coleta dos 28 pares.
2. Reexecutar auditoria global e cruzar calendário do broker; manter bloqueadas janelas com qualquer lacuna não certificada, inclusive o GBP/NZD em 30/09/2025.
3. Aplicar o leitor apenas a candles fechados e a decisões **previamente registradas com prova temporal externa**. Não reconstruir previsões antigas olhando candles posteriores.
4. Unir esses resultados à comparação pareada do filtro de regime, contabilizando todos os sinais emitidos, recusados e períodos em `AGUARDAR`, com janelas cronológicas predefinidas, amostra suficiente e sem ajuste no período de teste.
5. Reportar percentuais de D1 e W1 **se** existirem previsões e evidências aptas; caso contrário, registrar `NÃO MENSURÁVEL`.

## Testes

Executado localmente: `21/21` testes **sintéticos** com `unittest` e uma cópia local temporária da constante canônica FX_28 para carregamento (o repositório original já fornece a constante). A suíte confirma casos positivos documentais, rejeições por adulteração, arquivo comprimido corrompido, duplicatas, leituras futuras, vela incompleta, horários inválidos, preços inválidos e reprodução sintética da lacuna GBP/NZD. **Não existe execução de teste real com as 103.600 velas nesta rodada.**

**NO-GO:** nenhuma alteração no app publicado; nenhuma operação ou recomendação no mercado; sem confiança calibrada/percentual de acerto alegado.
