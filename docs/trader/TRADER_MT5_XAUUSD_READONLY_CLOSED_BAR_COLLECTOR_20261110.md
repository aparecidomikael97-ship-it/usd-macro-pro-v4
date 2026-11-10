# AtlasQuant Trader — coletor XAU/USD fechado e isolado (LAB)

**Checkpoint: 10/11/2026. Apenas código preparado; não executado no MT5 real.**

## Motivação e contexto

O lote real AM12 coletado em 07/11 tinha **103.600 velas dos 28 pares Forex**,
sem XAU/USD. O ouro já possuía prioridade própria de pesquisa na PR e um
módulo de juros nominais/reais do Treasury. Faltava preparar a coleta de preço
local no terminal Pepperstone, sem modificar os snapshots dos pares existentes.

## Novo coletor `atlasquant_mt5_xauusd_closedbar_capture_lab.py`

- Execução **somente sob comando explícito** no Windows autorizado, com
  `--terminal-path` obrigatório para um `terminal64.exe` já aberto. **Não**
  importa nem conecta ao MT5 quando o módulo é apenas importado para testes.
- Usa exclusivamente `initialize`, `terminal_info`, `symbol_info(XAUUSD)`,
  `copy_rates_from_pos(..., start_pos=1)` e `shutdown`. **Não** chama
  `account_info`, `positions_get`, `orders_get`, `order_send`, `symbol_select`,
  login ou mudança de configuração.
- Caso XAUUSD não esteja visível, retorna `XAUUSD_NOT_VISIBLE_NO_AUTO_SELECT`.
  Não procura automaticamente símbolos alternativos, nem assume spread,
  horários, contrato ou equivalência com spot real.
- Requisita **3.000 M15 + 500 D1 + 200 W1 = 3.700 velas**; índice 0
  potencialmente aberto fica excluído. Toda série deve ter contagem completa,
  timestamps crescentes, OHLC positivo/coerente, volumes e spreads não
  negativos, preços finitos e abertura não declarada no futuro do relógio
  local por mais de 60 segundos. Isso é coerência básica, **não** prova UTC.
- Nenhum diretório ou arquivo é criado antes de as **três séries** passarem.
  A pasta de saída obrigatória fica sob
  `%LOCALAPPDATA%\AtlasQuant\LAB\MT5_Snapshots`, em uma subpasta nova de
  formato `XAUUSD_YYYYMMDDTHHMMSSZ`. Se já existir, **bloqueia sem sobrescrever**.
- Salva somente três `XAUUSD_{M15,D1,W1}_closedbar.csv.gz` e
  `xauusd_manifest.json` com contagens, horários alegados, SHA-256 do CSV
  descompactado e contagem dos saltos maiores que o período nominal.
- Relê e confere cada arquivo ZIP gerado. Fins de semana/feriados/sessões
  continuam **pendências para auditoria de calendário**, não velas inventadas.
  Se uma falha de disco interromper a gravação, a pasta incompleta é mantida
  para diagnóstico, mas nunca recebe autorização de uso operacional.
- Não grava informações de conta nem envia preços ao GitHub. Nenhuma ordem.

### Exemplo para execução manual futura, no ambiente Python com MetaTrader5

```powershell
py -3.11 atlasquant_mt5_xauusd_closedbar_capture_lab.py --terminal-path "C:\Program Files\MetaTrader 5\terminal64.exe"
```

**Não rodar sem verificar o caminho real do terminal, módulo Python MT5 e
disponibilidade de XAUUSD no servidor.** A execução ficará para quando o
computador estiver disponível; o usuário estava no celular nesta etapa.

## Testes desta rodada

- Novo `test_atlasquant_mt5_xauusd_closedbar_capture_lab.py`: **14/14 testes
  sintéticos com API MT5 falsa**. Verificam 3.700 velas, CSV.gz/manifesto/SHA,
  chamadas estritamente read-only, bloqueio de terminal invisível/desconectado,
  caminho inválido, série incompleta, OHLC errado, timestamp duplicado/futuro,
  volume negativo, falha de shutdown, proibição de sobrescrita e contagem
  de gap.
- Regressão local `python -m unittest discover -q -p 'test_atlasquant*.py'`:
  **329/329 PASS** no executor, sem acesso ao MT5 do usuário.
- Nenhum preço real de XAU/USD foi obtido hoje e **não** houve teste de
  desempenho real, integração com Radar, merge, deploy, Worker ou custo novo.

## Bloqueios preservados

`broker_identity_independently_authenticated=false`,
`candle_server_utc_independently_authenticated=false`,
`historical_point_in_time_verified=false`, `gold_bias=null`,
`validated_accuracy=null`, `operational_bias=AGUARDAR`,
`trade_authorized=false`, `can_feed_live_radar=false`.

**Próximo avanço:** executar o coletor read-only no MT5 autorizado quando o
usuário voltar ao computador; auditar hash, cobertura, timezone, sessão e
lacunas do ouro separadamente; depois juntar fontes macro/geopolítica com
captura point-in-time e validar vieses D1/W1 fora da amostra.
