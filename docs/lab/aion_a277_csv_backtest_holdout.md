# A277 — Backtest mensal offline por planos manuais e validação cronológica

**Status: LAB. HARD NO-GO.** Esta etapa liga o importador estrito A276 ao motor de simulação histórica `atlasquant_operational_backtest.backtest_signal`, sem gerar sinais, operar ou conectar provedores.

A277 **não** escolhe operações sozinho: cada plano de entrada, stop e alvo precisa ser fornecido explicitamente. Assim, nenhum resultado descrito aqui é previsão, garantia ou evidência de que o plano era conhecido antes dos preços futuros.

## Exemplo

```python
from datetime import datetime, timezone
from atlasquant_aion_csv_backtest_lab import research_backtest_csv

csv_text = (
    "closed_at,open,high,low,close\n"
    "2026-09-30T23:00:00+00:00,10,10.2,9.8,10\n"
    "2026-09-30T23:15:00+00:00,10,10.2,9.9,10\n"
    "2026-09-30T23:30:00+00:00,10,12.2,10,12\n"
    "2026-10-01T00:00:00+00:00,10,10.2,9.8,10\n"
    "2026-10-01T00:15:00+00:00,10,10.2,9.9,10\n"
    "2026-10-01T00:30:00+00:00,10,10.1,8.8,9\n"
)
resultado = research_backtest_csv(
    csv_text,
    symbol="EURUSD", timeframe="M15", timestamp_basis="CLOSE",
    now=datetime(2026, 10, 30, tzinfo=timezone.utc),
    validation_start="2026-10-01T00:00:00+00:00",
    manual_plans=[
        {
            "signal_time": "2026-09-30T23:00:00+00:00",
            "setup": "FVG", "side": "BUY", "entry": 10,
            "stop": 9, "target": 12,
        }
    ],
    cost_r=0.10, slippage_r=0.05,
    max_wait_bars=2, max_hold_bars=3,
)
assert resultado["valid"]
assert resultado["no_orders"] and not resultado["authorizes_send"]
```

## Regras da pesquisa

- Entrada CSV: A276, com datas timezone-aware, candles fechados e OHLC válidos, no máximo 1 MB/10.000 candles. Ativos: 28 Forex e 7 identificadores internos do Radar; WIN/WDO continuam **raízes sem série por vencimento e ajustes verificados**.
- Planos: lista de até 200 dicionários Python nativos, apenas `signal_time,setup,side,entry,stop,target`. Setups iniciais são `FVG`, `OB` e `PULLBACK`, **rótulos informados pelo usuário**, não detectores automáticos. `signal_time` deve coincidir com o fechamento de uma vela existente, em UTC, e a geometria do trade precisa ser coerente.
- `validation_start`: data exata do fechamento de uma vela; obrigatoriamente pelo menos três candles em treino e três em validação. Nenhum plano ou preço da outra partição é utilizado para simular o resultado de uma partição.
- O motor só começa a buscar entrada **depois** da vela sinalizada; simula uma posição por ativo e evita operações sobrepostas. Em vela que atinge stop e alvo juntos, conserva a regra conservadora existente: considera stop primeiro.
- Se uma operação chega ao fim da partição sem completar o número declarado de candles de permanência, ela vira `CENSORED_AT_PARTITION_END`. Não recebe ganho/perda fictícia nem entra no denominador de trades, e outras operações sobrepostas são bloqueadas.
- `cost_r` e `slippage_r`: premissas informadas em **R por trade**, ambas finitas e não negativas. Resultados também incluem `ZERO_FRICTION`, `CONFIGURED` e `STRESS_X2`. Não são cotações reais de spread, comissões ou custos de execução.
- Cada partição traz `summary`, `monthly_utc`, `setups`, `friction_scenarios`, `ledger` e número de trades censurados. Operações executadas são atribuídas ao **mês de saída UTC**; recusas, ao mês do sinal. Isso é pesquisa descritiva, não ranking de estratégia.
- Amostras com menos de 30 trades executados são marcadas `INSUFFICIENT_SAMPLE`; amostras maiores continuam descritivas e sem probabilidade de lucro.
- Todo erro de CSV, corte, plano, custos ou janela invalida o estudo inteiro e retorna `train=None` e `holdout=None`.

## O que esta etapa não comprova

Um corte cronológico não prova que os planos foram gerados *antes* dos candles posteriores. Se o pesquisador escolheu as entradas após ver todo o histórico, o resultado continua sujeito a **viés de retrospectiva e ajuste excessivo**. É preciso preservar planos gerados ponto-no-tempo e avaliação walk-forward real antes de alegar validação fora da amostra.

O A277 não contém interface de replay, coletor de dados históricos, detector FVG/OB, varredura automática, precificação de contratos WIN/WDO, custos em R$ ou conexão com corretora. O importador A276 não é propagado ao Radar residente nem à cobertura M15 atual.

**Invariantes:** sem sinal automático, Worker, broker, ordem, envio, alerta, deploy, mudança de main ou cobrança nova. HARD NO-GO permanece; seis P0 continuam 0/6 homologados.

## Próxima pesquisa sugerida

Registrar a origem temporal dos sinais históricos (geração antes da vela seguinte), expor a síntese em tela LAB, testar grandes séries reais legalmente obtidas e adicionar uma matriz walk-forward sem otimizar parâmetros com dados de validação.
