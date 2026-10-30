# AION A282 — comparação descritiva A279/A280/A281 (LAB)

Status: **HARD NO-GO**. Todos os dados são CSV OHLC históricos fornecidos
pelo pesquisador; não há acesso a broker, provedor, rede, Worker, alerta ou
ordem. Custos adicionais: nenhum. P0 homologados: **0/6**.

## Para quê serve

A282 permite observar, **por ativo e timeframe**, o efeito de três regras
fixas sobre o mesmo histórico, a mesma separação cronológica e os mesmos
custos de execução assumidos:

1. `FVG_SMA5`: gap geométrico de três velas com filtro SMA5 (A279).
2. `FVG_BOS`: apenas FVG alinhado com BOS confirmado causalmente (A280).
3. `FVG_BOS_PLUS_OB_PROXY`: FVG+BOS e candidato OB mecânico com
   preferência pelo FVG em colisão na mesma vela confirmada (A281).

O rótulo BOS/CHOCH é uma **aproximação mecânica**, não validação ICT
institucional. OB é um *proxy* e não demonstra ordem institucional real.
As regras não são adaptadas ao holdout. O resultado não contém vencedor,
recomendação, ganho previsto ou ranking.

A engine A277 faz entrada simulada apenas depois da vela do candidato;
a divisão treino/holdout não deixa uma posição atravessar sem censura o
limite. Os mesmos valores de custo/slippage em R, janela de entrada e
janela de encerramento são usados para os três modelos.

## Contrato de uso

```python
from datetime import datetime, timezone
from pathlib import Path

from atlasquant_aion_three_variant_comparison_lab import (
    compare_causal_variants_csv, compare_causal_variants_batch,
)

csv_text = Path("meu_historico_exportado.csv").read_text(encoding="utf-8")
result = compare_causal_variants_csv(
    csv_text, symbol="EURUSD", timeframe="M15",
    timestamp_basis="CLOSE",
    now=datetime.now(timezone.utc),
    validation_start="2026-08-01T10:00:00+00:00",
    cost_r=0.1, slippage_r=0.05,
)
# A fronteira deve coincidir com uma vela fechada dentro do CSV.
# Apenas pesquisa descritiva. Não enviar ordens ou alertas.
```

O CSV exige cabeçalho `closed_at,open,high,low,close` (ou
`time` / `datetime`), timestamp ISO com fuso explícito e velas em ordem.
A entrada é limitada pelo importador A276 (até 1 MB/10.000 candles/arquivo)
e pela comparação A282 (até oito séries por chamada). Símbolos aceitos:
28 pares FX e sete IDs de apresentação de índices e futuros-raiz.
`WIN` e `WDO` **não** verificam vencimento/contrato.

Para múltiplas séries, use `compare_causal_variants_batch(slices=[...], now=...,
cost_r=..., slippage_r=...)`. Cada item é um dicionário com exatamente
`symbol, timeframe, timestamp_basis, csv_text, validation_start`.
A mesma combinação símbolo/timeframe não pode aparecer duas vezes.
Uma série inválida bloqueia a entrega de *todas* as séries. Valores de R de
ativos/timeframes distintos **não são somados**.

## Interpretação e limites

- `train` e `holdout` são separações cronológicas **não atestadas
  independentemente**. Se alguém escolheu a fronteira depois de ver
  resultados, isso não vira um teste fora da amostra verdadeiro.
- Cada modelo possui o próprio conjunto de candidatos; as amostras
  (e a concorrência de posições) diferem. Comparar `net_r` bruto entre
  modelos com quantidades diferentes não prova superioridade.
- Menos de **30 operações executadas no holdout, para qualquer modelo**:
  `INSUFFICIENT_HOLDOUT_SAMPLE_FOR_COMPARISON`.
- Até quando houver 30+, as métricas continuam apenas descritivas, não
  indicam acurácia de futuros movimentos e não comprovam edge.
- A282 preserva estatísticas e cenários de fricção `ZERO_FRICTION`,
  `CONFIGURED` e `STRESS_X2` por modelo, inclusive hash do livro
  histórico. Não emite recibo de custódia externa nem inventa timestamp
  independente de captura.
- **Nenhuma amostra real de Forex ou índice foi obtida nesta alteração**:
  os testes automatizados usam dados artificiais determinísticos.

## Verificação

CI de LAB em Ubuntu e Windows, Python 3.12:
`labs.test_a282_three_variant_comparison`, regressões A281→A268,
A277/A276, risk guardian, simulador e scanner.

**Não** liberar Worker, deploy, merge de produção, sinal ao vivo ou
contrato de operação real. Seis P0 permanecem 0/6 homologados.
