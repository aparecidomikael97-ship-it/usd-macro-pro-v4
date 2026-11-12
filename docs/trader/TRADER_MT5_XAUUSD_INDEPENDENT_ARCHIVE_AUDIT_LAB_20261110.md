# AtlasQuant Trader — auditoria independente do snapshot XAU/USD (LAB)

**Checkpoint: 10/11/2026. Sem execução no MT5 real e sem novo dado de ouro.**

## Escopo P0

O coletor `atlasquant_mt5_xauusd_closedbar_capture_lab.py` foi preparado
separadamente dos 28 pares. Esta etapa acrescenta um **segundo programa**,
`atlasquant_mt5_xauusd_archive_audit_lab.py`, que não importa a API MT5, não
consulta a corretora, não faz requests e **não escreve nenhum arquivo**.

Ele lê uma única pasta local nova do tipo
`%LOCALAPPDATA%\AtlasQuant\LAB\MT5_Snapshots\XAUUSD_YYYYMMDDTHHMMSSZ`.
Não usa a pasta `20261107_AM12` dos 28 pares e não envia candles ao GitHub.

### Verificações realizadas

- O diretório deve ser o de um lote XAU/USD isolado e conter **exatamente**
  três CSV.gz e o `xauusd_manifest.json`; recusa links simbólicos.
- O manifesto deve preservar `METAL:XAUUSD`, escopo de pesquisa,
  `AGUARDAR` e `trade_authorized=false`; o horário UTC alegado deve
  ser compatível com o nome da pasta, sem tratá-lo como UTC atestado.
- São obrigatórias as **3.000 M15, 500 D1 e 200 W1** (3.700 velas).
  Valida nome, quantidade, `bar_position_start=1`, esquema e SHA-256
  descompactado de cada série.
- Reabre o gzip com limites de tamanho para evitar arquivo descomprimido
  exagerado; verifica cada linha CSV, abertura temporal crescente, preços
  positivos e OHLC coerente, volumes/spreads inteiros não negativos e
  timestamps não posteriores ao relógio declarado mais 60 segundos.
- Recalcula o primeiro/último timestamp e os gaps maiores que o passo nominal,
  sem inventar velas nem classificar sessões de ouro sem calendário validado.
- Se qualquer elemento falhar, retorna `LOCAL_XAUUSD_ARCHIVE_FAIL`;
  somente o lote estruturalmente íntegro recebe
  `LOCAL_XAUUSD_ARCHIVE_INTEGRITY_PASS_UNATTESTED`.

**Um SHA-256 conferido com manifesto local demonstra apenas consistência do
arquivo.** Alguém poderia alterar CSV e manifesto em conjunto. Por isso,
mesmo `PASS` **não** prova identidade Pepperstone, horário de servidor,
autenticidade externa, disponibilidade histórica point-in-time,
viés correto, lucro nem calibração probabilística.

### Exemplo de execução manual futura no Windows

Depois que o coletor real for executado e criar uma pasta concreta, substituir
o nome abaixo pelo nome efetivamente gerado:

```powershell
py -3.11 atlasquant_mt5_xauusd_archive_audit_lab.py --capture-directory "$env:LOCALAPPDATA\AtlasQuant\LAB\MT5_Snapshots\XAUUSD_YYYYMMDDTHHMMSSZ"
```

O auditor não requer a biblioteca `MetaTrader5` nem MT5 aberto.

## Evidência de laboratório

- `test_atlasquant_mt5_xauusd_archive_audit_lab.py`: **20/20 testes**
  com lote criado por MT5 falso, incluindo SHA adulterado, arquivo regravado
  com hash recalculado mas OHLC inválido, timestamp duplicado/futuro, volume
  negativo, manifesto alterado, gaps divergentes, caminho/symlink, arquivo
  ausente/extra e limite de descompressão.
- Regressão `python -m unittest discover -q -p 'test_atlasquant*.py'`:
  **349/349 aprovações locais**, sem conexão com a Pepperstone.

## Estado do portão operacional

`archive_is_independently_authenticated=false`,
`historical_point_in_time_verified=false`, `gold_bias=null`,
`validated_accuracy=null`, `operational_bias=AGUARDAR`,
`can_feed_live_radar=false`, `trade_authorized=false`.

**Próxima etapa dependente do computador do usuário:** coletar o ouro no
terminal autorizado, auditar o lote real, revisar sessão/UTC/feriados e só
então iniciar a coorte de pesquisa de vieses D1/W1, com notícias e macro
registradas antes da decisão. Sem merge, deploy, worker, cobrança ou ordens.
