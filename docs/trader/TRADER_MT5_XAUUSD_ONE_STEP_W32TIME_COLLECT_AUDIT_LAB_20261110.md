# AtlasQuant Trader — XAU/USD em um comando: relógio, coleta, auditoria

**Checkpoint: 10/11/2026. Preparado e testado com MT5 falso; não executado
no terminal Pepperstone real.**

## Objetivo

Para agilizar a coleta quando o usuário voltar ao computador, adicionar um
único programa `atlasquant_mt5_xauusd_one_step_lab.py` que executa, nessa
ordem, a consulta **read-only** do status do relógio Windows, a coleta de
velas fechadas do ouro no MT5 já aberto e a auditoria local independente.
Não acessa informações de conta, posições ou ordens.

## Bloqueio essencial de relógio

Capturas enviadas pelo usuário em 09/11 mostraram erro de sincronização do
Windows (`w32tm /resync`: nenhuma informação de hora disponível). Como o
relógio influencia o corte temporal dos candles e das notícias, o novo
programa exige **antes de qualquer chamada ao MT5** a resposta local de
`w32tm /query /status /verbose`, comando documentado pela Microsoft.

Parser do LAB aceita inglês e campos equivalentes em PT-BR e exige:

- Comando de status concluído com código zero, sem fonte local como `Local
  CMOS Clock` ou relógio livre.
- `Leap Indicator` igual a zero e `Last Sync Error` igual a zero.
- `Time since Last Good Sync Time` de até **3.600 segundos**.
- `Phase Offset` em módulo de até **1 segundo**.
- Campos ausentes, saída truncada, dados antigos, fonte local ou erro no
  serviço: **bloqueia antes de carregar/importar a API MT5**.

Esses campos são autorrelatos do Windows. Mesmo com `PASS`,
`clock_utc_independently_attested=false` e não há comprovação externa do UTC.
O coletor de dados preserva todos os bloqueios de fonte/point-in-time.
O programa **não** executa `/resync`, não edita registro ou serviço de tempo
e não tenta corrigir a configuração do usuário.

Referência oficial: documentação Microsoft `Windows Time Service Tools and
Settings` sobre `/query /status /verbose`.

## Execução manual futura — Windows autorizado

Depois de confirmar onde o `terminal64.exe` da Pepperstone realmente fica e
que o Python tem o módulo oficial `MetaTrader5`, o comando proposto é:

```powershell
py -3.11 atlasquant_mt5_xauusd_one_step_lab.py --terminal-path "C:\Program Files\MetaTrader 5\terminal64.exe"
```

O caminho acima é **apenas exemplo** e não foi verificado no notebook.
Não instalar pacotes nem executar ordens automaticamente.

Saída local: uma pasta nova sob
`%LOCALAPPDATA%\AtlasQuant\LAB\MT5_Snapshots\XAUUSD_YYYYMMDDTHHMMSSZ`,
três CSV.gz (3.000 M15, 500 D1, 200 W1) e manifesto. O segundo passo
reabre todos os arquivos e recalcula os hashes e metadados. Se o auditor
falhar, os arquivos da pasta nova permanecem para diagnóstico, **sem uso**.
Tentativa de repetir o segundo UTC não sobrescreve pasta anterior.

## Evidência local

- `test_atlasquant_mt5_xauusd_one_step_lab.py`: **18/18 testes**.
  PT-BR/inglês, relógio de hardware local, sincronização muito antiga,
  salto/erro, offset alto, campo ausente, MT5 desconectado, W1 incompleto,
  falha da auditoria, duplicidade e proibição de operações.
- Regressão `python -m unittest discover -q -p 'test_atlasquant*.py'`:
  **399/399 testes aprovados**.
- Execução do CLI no Linux: `BLOCKED: WINDOWS_ONLY`, código de saída 2,
  sem conexão com MT5.

## Permanecem NO-GO

`os_clock_independently_authenticated=false`,
`pepperstone_broker_identity_independently_authenticated=false`,
`historical_point_in_time_verified=false`, `gold_bias=null`,
`validated_accuracy=null`, `operational_bias=AGUARDAR`,
`trade_authorized=false`, `can_feed_live_radar=false`.

**Próximo passo real:** usuário no Windows, terminal MT5 disponível,
verificar o relógio por fonte confiável; se o preflight passar, executar a
coleta read-only local e auditar a qualidade temporal. Sem merge, deploy,
Worker, trade, novos serviços pagos ou publicação ao Radar.
