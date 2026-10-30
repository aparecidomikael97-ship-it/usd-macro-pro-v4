# AION A284 — Ponte offline de exportação MT5 (LAB)

**HARD NO-GO**. P0 **0/6** homologados. Não há Worker, deploy,
alertas, ordens, contato automático com MetaTrader/corretora nem
contratação de serviço pago. `Negócios` permanece congelada.

## O problema

Para avaliar FVG / BOS / OB com históricos reais sem usar replay pago,
o pesquisador pode exportar barras que já estejam disponíveis no
MetaTrader 5. A documentação oficial do MT5 descreve a opção
**Observação do Mercado → Símbolos → Barras → Pedido → Exportar**:
https://www.metatrader5.com/pt/terminal/help/trading/market_watch

O formato nativo mostrado no livro oficial de MQL5 é um arquivo
delimitado por **tabulações** com nove colunas:
`<DATE>, <TIME>, <OPEN>, <HIGH>, <LOW>, <CLOSE>, <TICKVOL>, <VOL>, <SPREAD>`.
As vírgulas aqui apenas separam os nomes na explicação; o delimitador
real do arquivo é TAB:
https://www.mql5.com/en/book/common/files/files_txt_atomic

A ponte A284 transforma essas barras, **offline**, no CSV exigido
pelo A276/A283/A282: `closed_at,open,high,low,close`.

## Atenção: fuso horário declarado, não adivinhado

A fonte normalmente apresenta data e hora sem offset UTC explícito.
É obrigatório informar `server_utc_offset_minutes` como **inteiro**,
por exemplo `+120` **somente se o usuário tiver conferido** que os
horários daquele arquivo representam UTC+2.

A284 **não** determina o fuso real do broker, nem detecta transições
de horário de verão (DST). Um offset fixo aplicado a um histórico que
atravessa mudança de DST pode produzir tempos errados. Nesses casos,
**não aceite o relatório como válido para trading**; separe períodos
cujo offset for conhecido ou obtenha fonte com UTC explícito.

Os timestamps MT5 são tratados como **abertura da vela**, convertidos
para UTC com o offset declarado e depois avançados em **um timeframe
completo** para o timestamp de fechamento. A276 valida a ordem e a
geometria; a saída volta a ser validada em `CLOSE` para impedir
mudança acidental de uma vela.

## Contratos de dados

- Cabeçalho nativo exato; separador TAB; datas `AAAA.MM.DD`,
  horas `HH:MM:SS`; campos OHLC positivos e finitos.
- `TICKVOL`, `VOL` e `SPREAD` precisam estar presentes e ser
  inteiros não negativos. Eles **não** são tratados como volume real,
  liquidez confirmada ou custo de transação confiável.
- Entrada limitada a 1,6 MB e 10.000 velas; a saída ainda precisa
  atender aos limites de 1 MB do A276.
- Simbolização de research `EURUSD`, `US30`, `WIN` etc. não
  comprova contrato ou símbolo equivalente do broker. `WINZ26`
  é rejeitado; futuro-raiz `WIN` continua sem vencimento validado.
- SHA-256 registra o arquivo bruto e o CSV normalizado; **não** é
  assinatura externa nem prova de origem.
- A283 mantém seus critérios mínimos de amostra estrutural.
- A282 continua exigindo 30 operações executadas no holdout
  por modelo, sem vencedores nem previsão.

## Exemplo de uso (somente pesquisa)

```python
from pathlib import Path
from datetime import datetime, timezone
from atlasquant_aion_mt5_bars_bridge_lab import (
    normalize_mt5_bars_tsv, preflight_mt5_bars_tsv,
    research_mt5_bars_tsv,
)

raw = Path("EURUSD_M15_Exportado_MT5.csv").read_text(encoding="utf-8")
normalized = normalize_mt5_bars_tsv(
    raw, symbol="EURUSD", timeframe="M15",
    now=datetime.now(timezone.utc),
    server_utc_offset_minutes=120,  # EXEMPLO, NAO presumir UTC+2
)
# Se o fuso/offset nao foi confirmado, PARE: nao interpretar a pesquisa.
```

Para rodar o preflight A283, use `preflight_mt5_bars_tsv`
com um `validation_start` ISO/UTC que coincida com uma vela
**fechada**. Para o estudo A282 depois do preflight, use
`research_mt5_bars_tsv` com `cost_r`, `slippage_r` e a
mesma fronteira. O corte é declarado pelo usuário e não
**independentemente pré-registrado**.

## Limitações fundamentais

- A disponibilidade de dados depende do servidor MT5 e corretora;
  o AION não faz download, login ou operação.
- Nada comprova que preço, abertura/fechamento, timezone ou offset
  vieram de uma fonte independente, completa ou correta.
- Não há conversão de tick volume para volume de bolsa.
- Spread bruto exportado **não** vira slippage/custo real.
- Arquivos longos com DST variável exigem tratamento adicional
  de timezone, não simples offset fixo.
- Nenhum histórico real foi incluído nesta PR. Testes usam
  dados artificiais com o formato nativo MT5.

## Verificação

CI isolado Ubuntu e Windows Python 3.12, 26 testes A284
e regressões A283→A268, guardião de risco, simulador/scanner.

**Sem ativação de produção, sem P0 promovidos.**
