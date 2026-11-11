# AtlasQuant Trader — captura PPI de sete pares USD M15 (LAB, 11/11/2026)

**Estado: preparado e testado com dados sintéticos; nenhuma captura real executada.**
Sem alteração de conta, ordens, posições, Radar, scheduler, deployment ou custo.

## Contrato congelado antes da divulgação

- Evento estudado: PPI EUA referente a outubro de 2026, **13/11/2026, 13:30 UTC** (09:30 em Mato Grosso).
- Pares: `EURUSD`, `GBPUSD`, `AUDUSD`, `NZDUSD`, `USDJPY`, `USDCHF`, `USDCAD` — exatamente sete.
- Para cada par: **17 velas fechadas M15**, aberturas UTC de `13:15` até `17:15`, última fechando às `17:30 UTC` (13:30 em Mato Grosso).
- Consulta MT5: `copy_rates_range` com dois `datetime` *aware* UTC; os extremos são inclusivos pelo tempo de **abertura**. Contrato da MetaQuotes: https://www.mql5.com/en/docs/python_metatrader5/mt5copyratesrange_py.
- `13:15` é a vela pré-divulgação usada como linha de base. As janelas de comparação são +15m, +1h e +4h. Um único PPI é **uma observação econômica**, mesmo quando os sete pares reagem.
- A estrutura `MT5_READONLY_M15_CSV_CLAIM_UNVERIFIED` e os hashes SHA-256 permitem verificar integridade **local** dos arquivos, não atestam corretora, relógio UTC independente, liquidez, spread executável, vintage histórico ou causalidade.

## Execução futura (somente por decisão humana no PC Windows)

O módulo `atlasquant_trader_ppi_mt5_m15_capture_lab.py` **não importa nem abre MT5 sozinho**. Só depois de `13/11/2026 17:30 UTC`, em um computador Windows com terminal MT5 *já aberto*, conectado e símbolos canônicos visíveis, pode ser executado manualmente no ambiente Python que já tenha `MetaTrader5`:

```powershell
python atlasquant_trader_ppi_mt5_m15_capture_lab.py --terminal-path "C:\Program Files\MetaTrader 5\terminal64.exe"
```

Esse comando **não deve ser executado antecipadamente**; o script bloqueará a captura. Se sua instalação ou símbolos da Pepperstone tiverem nomes diferentes, não alterar nem selecionar símbolos automaticamente: registrar a divergência e revisar o mapeamento primeiro.

Somente após as sete séries completas passarem as validações, será criada **uma pasta nova sem sobrescrever anteriores** em `%LOCALAPPDATA%\AtlasQuant\LAB\PPI_20261113_MT5\PPI7_<data>`. Ela conterá sete CSVs e um manifesto local `ppi_mt5_capture_manifest.json` com os hashes. Falha em qualquer par bloqueia os 119 candles como estudo completo; não preenche lacunas.

Para o estudo offline já existente:

```python
from pathlib import Path
from datetime import datetime, timezone
from atlasquant_trader_ppi_mt5_m15_capture_lab import load_local_receipt_lab
from atlasquant_trader_ppi_usd_fx_forward_reaction_lab import inspect_ppi_fx_m15_forward_reaction_lab

folder = Path(r"C:\caminho\real\da\pasta\PPI7_<data>")
receipt = load_local_receipt_lab(folder)
result = inspect_ppi_fx_m15_forward_reaction_lab(
    archive_root=folder,
    receipt=receipt,
    as_of_utc=datetime.now(timezone.utc),
)
```

Mesmo quando `result` trouxer reações, o estado permanece **documentário / NO-GO / AGUARDAR**, sem probabilidade calibrada, comprovação causal ou autorização de operações. Os dados oficiais do BLS e o consenso pré-evento são verificados separadamente no `atlasquant_trader_ppi_one_event_study_join_lab.py`.

## Validação realizada em 11/11

`test_atlasquant_trader_ppi_mt5_m15_capture_lab.py` usa um MT5 falso em memória: exercita a janela de tempo, apenas métodos de leitura, sequência, volume, OHLC, UTC, sete arquivos/hashes, consumo pelo leitor e resistência a alterações no CSV. **Nenhum terminal real foi conectado**.

## Pendências explícitas

1. Esperar a divulgação real, a janela de quatro horas e as primeiras fontes verificadas do BLS.
2. Somente no PC de Mikael, confirmar conexão do terminal, disponibilidade M15 e os nomes canônicos dos sete pares; nunca inserir credenciais ou alterar operações automaticamente.
3. Capturar e auditar os 119 registros reais, se disponíveis; caso contrário, `AGUARDAR`.
4. Comparar os dados oficiais do evento e os preços em estudo de caso **sem alegar acurácia de sinal a partir de uma única divulgação**.
