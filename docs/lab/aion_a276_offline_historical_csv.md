# A276 — Entrada CSV histórica offline do AION Trader (LAB)

**Escopo:** um arquivo CSV textual por **ativo + timeframe**, sem chamadas de mercado, broker, API, assinatura ou replay pago. A276 é apenas um normalizador conservador de candles para investigação histórica: **não** calcula estratégias, não afirma performance e não transforma dados importados em evidência atual.

## Uso demonstrativo

```python
from datetime import datetime, timezone
from atlasquant_aion_historical_csv import import_historical_csv

historico = (
    "time,open,high,low,close\n"
    "2026-10-29T09:00:00-04:00,100,103,99,102\n"
    "2026-10-29T09:15:00-04:00,102,104,101,103\n"
)
resultado = import_historical_csv(
    historico, symbol="WIN", timeframe="M15",
    timestamp_basis="OPEN", now=datetime(2026, 10, 30, tzinfo=timezone.utc),
)
assert resultado["valid"]
assert resultado["status"] == "HISTORICAL_ONLY_UNATTESTED"
assert resultado["authorizes_send"] is False
```

### Formato obrigatório

- Cabeçalho: `time,open,high,low,close` **ou** `datetime,open,high,low,close` **ou** `closed_at,open,high,low,close`. É permitido acrescentar `,volume` (volume finito e não negativo).
- Os carimbos de tempo precisam ser ISO 8601 **com fuso/offset explícito**, por exemplo `2026-10-29T09:00:00-04:00`. Datas sem fuso falham; não presumimos horário de Brasília ou UTC.
- Indique `timestamp_basis="OPEN"` se a coluna informa o início da vela (comum em exportações de gráfico). O importador calcula o fechamento adicionando a duração do timeframe. Use `"CLOSE"` somente se a coluna informar o fechamento. **Sem essa escolha explícita a importação não acontece.**
- Timeframes: `M5`, `M15`, `M30`, `H1`, `H4`, `D1`. Não se cria outro timeframe por reamostragem.
- Ativos: exatamente os 28 pares Forex canônicos + `DXY`, `US30`, `NAS100`, `SPX500`, `IBOV`, `WIN`, `WDO` (nomes internos do Radar). Não se presumem equivalências com símbolos de corretoras.
- No máximo 1 MB de texto UTF-8 e 10.000 candles por chamada; mínimo de dois. Tempos crescentes com distância de pelo menos um período. Lacunas de sessão são preservadas, sem fabricação de barras.
- OHLC positivo, finito e com geometria consistente; volume opcional finito e >= 0. Rejeita timestamps posteriores ao `now` fornecido, duplicatas, linhas parciais e números não finitos. Erro invalida **todo** o arquivo, não apenas a linha problemática.

### Saída e integração futura

`candles` são registros de `datetime,open,high,low,close[,volume]` com data normalizada em UTC. Esse formato é consumível, sob responsabilidade de pesquisa, pelo normalizador já existente `atlasquant_operational_backtest.normalize_candles` através de um DataFrame. O A276 **não chama o simulador** e não produz entradas, sinais nem ordens.

`raw_csv_sha256` identifica os bytes recebidos; `normalized_candles_sha256` identifica os registros normalizados. Ambos são verificações de integridade local, **não prova de origem, autenticidade, completude nem licença** dos dados.

**Atenção ao WIN/WDO:** são raízes de contratos futuros. O CSV não resolve vencimento, rolagem, custos, ajustes ou qual série histórica foi fornecida. A análise não é comparável a contrato negociável até que o vínculo de vencimento/provedor seja comprovado separadamente.

### Limites e política

- Não obtém dados históricos automaticamente; o usuário precisa fornecer CSV legalmente obtido, de procedência conhecida. Não habilita replay gratuito no TradingView.
- Não injeta candles importados na cobertura M15 residente, no radar de dados atuais ou no gate de execução.
- Nunca autoriza `send`, ordem, alerta, Worker, deploy ou reativação. **HARD NO-GO intacto. Seis P0 seguem 0/6 homologados.**
- Nenhum novo serviço contratado ou custo recorrente.
- A entrega está em PR draft LAB empilhada sobre A275; requer revisão e CI antes de qualquer homologação, sem merge em `main`.

### Próxima pesquisa possível

1. Adaptador de um CSV real, com tratamento explícito de horários de abertura/fechamento.
2. Mapeamento verificável das séries de WIN/WDO por vencimento e ajustes.
3. Backtests com walk-forward, spread, custos e slippage usando o motor existente; sempre com separação temporal e sem prometer acerto.
