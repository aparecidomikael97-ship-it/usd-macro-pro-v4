# AtlasQuant Trader — prova real de relógio no AM12 (LAB)

**09/11/2026; somente leitura; sem ordens, mudanças de posição, merge ou deploy.**

## O que foi observado diretamente

1. O dispositivo autorizado `am12` estava online. `terminal64.exe` (PID observado: 9800) estava aberto em `C:\Program Files\Pepperstone MetaTrader 5\terminal64.exe`.
2. A API Python isolada `MetaTrader5` do ambiente temporário existente inicializou com sucesso; `terminal_info().connected == True`, `terminal_info().company == 'Pepperstone Group Limited'`, build `6308`.
3. Consulta limitada à identificação da origem informou **`account_info().server == 'Pepperstone-Demo'`**. Nenhum número de conta, nome pessoal, saldo, posições ou ordens foi impresso ou armazenado.
4. `EURUSD` existia e estava visível. `GBPNZD` existia, mas estava **oculto**. A prova formal de quatro séries `EURUSD/GBPNZD × D1/W1` recusou continuar com `SYMBOL_NOT_VISIBLE_NO_AUTO_SELECT`, sem habilitar o símbolo automaticamente.
5. Leitura complementar apenas do `EURUSD` retornou 12 rótulos de barras fechadas em D1 e 12 em W1. Os D1 apareceram às **19:00 EST / 20:00 EDT** no relógio de Nova York; os W1 da amostra às **20:00 EDT de sábado**, diferentes da referência NY 17h. Nenhum timestamp foi corrigido, deslocado ou interpolado. Não inferir que o rótulo da semana representa o primeiro tick negociável.
6. Às `2026-11-09T23:17:05Z` (relógio do PC), `symbol_info_tick('EURUSD').time` interpretado como epoch UTC indicou `2026-11-10T01:17:07Z`, uma diferença aproximada de **+7201 s**. Em segunda observação com o novo guard, janela `23:20:51.915711Z`–`23:20:51.920287Z`, o tick retornou `01:20:50Z`, diferença **+7198.080 s**.
7. `w32tm /query /status` informou o serviço de tempo **não sincronizado**, fonte `Local CMOS Clock`. Uma consulta independente da hora UTC na mesma sessão mostrou a hora externa aproximadamente compatível com o relógio do PC, mas isso **não certifica sincronização contínua nem precisão histórica**.

## Interpretação conservadora

- O servidor informado pelo terminal nesta sessão é **Pepperstone-Demo**, não prova que os snapshots históricos de 07/11 vieram da mesma sessão ou servidor.
- A Pepperstone declara uso de horário de servidor **GMT+2 no inverno dos EUA e GMT+3 no verão**, coerente em magnitude com a diferença de aproximadamente +2h observada no tick. Fonte: <https://pepperstone.com/en/about-us/trading-hours>.
- A documentação da API Python MetaTrader 5 descreve timestamps de barras/ticks como UTC. A divergência real de aproximadamente +2h exige investigação específica da plataforma, terminal, relógio do PC e semântica do dado. Fonte: <https://www.mql5.com/en/docs/python_metatrader5/mt5copyratesfrom_py>.
- **Nenhuma regra de `-2h`/`+2h` foi aplicada** aos CSVs ou usada para liberar backtests. A interpretação correta exige fonte/relógio corroborados antes da primeira coorte prospectiva.

## Proteção adicionada à PR #1851

- Novo `atlasquant_mt5_tick_timestamp_guard_lab.py`: usa apenas `initialize`, `terminal_info`, `symbol_info`, `symbol_info_tick` e `shutdown`. Não chama `account_info`, login, `symbol_select`, ordens, posições nem alteração da plataforma. Não exporta preços, credenciais ou dados de conta.
- Audita relógios UTC com janela limitada, rejeita tick futuro mais de 5 s ou tick antigo mais de 300 s, sem deduzir automaticamente deslocamento de fuso. Mesmo timestamp aparentemente plausível permanece **não atestado** e inelegível para P-I-T.
- `test_atlasquant_mt5_tick_timestamp_guard_lab.py`: **11/11 testes sintéticos PASS** em ambiente local isolado, incluindo offset +7200 s, tick antigo, relógio ingênuo, símbolo oculto, timeout e superfície read-only.
- O código foi baixado no AM12 de commit GitHub imutável e seu hash Git blob conferido igual ao arquivo testado. Executado no MT5 real, resultou em `LAB_TICK_CLOCK_BLOCKED / TICK_TIMESTAMP_IN_FUTURE_RELATIVE_TO_PC`, +7198.080 s, com `safe_for_point_in_time_join=False`, `operational_bias=AGUARDAR`, `publishable=False` e `trade_authorized=False`.

## Próxima etapa estrita

1. Confirmar sincronização confiável do relógio Windows, sem alterar configurações do proprietário silenciosamente.
2. Manter evidência separada de identificação do servidor ativo e da origem de cada snapshot.
3. Tornar o `GBPNZD` visível manualmente na Observação do Mercado (sem mudança de ordens) e repetir o diagnóstico pequeno de quatro séries; manter bloqueio até então.
4. Validar convenção efetiva dos rótulos D1/W1 contra horários de sessão e uma fonte independente. Não recalcular períodos do histórico por suposição.
5. Só depois pré-registrar os 56 alvos futuros com os recibos macro bilaterais e avaliar acerto fora da amostra.

**Estado:** `RESEARCH_ONLY`, `LAB_TICK_CLOCK_BLOCKED`, `operational_bias=AGUARDAR`, `validated_directional_accuracy=None`, `new_cost_brl=0`, sem ordens ou execução automática.
