# A278 — Diário local de planos históricos com cadeia SHA-256 (LAB)

**Não é uma prova externa de tempo, identidade ou custódia.** A278 oferece verificação de consistência do diário e um vínculo local com o backtest A277. O HARD NO-GO continua.

## Problema que tratamos

Um backtest histórico pode parecer excelente porque os planos de entrada, stop e alvo foram escolhidos depois de observar os preços futuros. Para começar a controlar isso, registramos cada plano com:

- número de sequência;
- horário de captura **declarado pelo originador** (timezone-aware);
- dados completos do plano manual: fechamento da vela de sinal, setup FVG/OB/PULLBACK, BUY/SELL, entrada, stop e alvo;
- hash da entrada anterior e hash SHA-256 do registro atual.

Ao terminar uma fase de registro, conserve o `head_sha256` **separadamente** do diário. Na avaliação, ele deve ser fornecido como `expected_head`; qualquer alteração, remoção, inversão ou inserção indevida muda a cadeia e é detectada **se o digest esperado permaneceu preservado**.

## Uso resumido

```python
from datetime import datetime, timezone
from atlasquant_aion_plan_journal_lab import (
    empty_plan_journal, append_manual_plan, verify_plan_journal,
)

diario = empty_plan_journal(symbol="EURUSD", timeframe="M15")
plano = {
    "signal_time": "2026-10-30T11:00:00+00:00",
    "setup": "FVG", "side": "BUY",
    "entry": 1.1000, "stop": 1.0980, "target": 1.1040,
}
resultado = append_manual_plan(
    diario,
    plan=plano,
    captured_at=datetime(2026, 10, 30, 11, 1, tzinfo=timezone.utc),
)
assert resultado["accepted"]
diario = resultado["journal"]
hash_guardado_separadamente = resultado["head_sha256"]
assert verify_plan_journal(
    diario, expected_head=hash_guardado_separadamente,
)["valid"]
```

O exemplo demonstra apenas sintaxe e verificação local; **não** confirma que a captura aconteceu na hora declarada.

Para testar os planos, `research_backtest_journal_csv(csv_text, journal=diario, expected_head=hash_guardado_separadamente, symbol=..., timeframe=..., timestamp_basis=..., now=..., validation_start=..., cost_r=..., slippage_r=...)` só chama o backtest A277 quando a cadeia e o identificador do ativo/TF conferem. Mantém o corte treino/validação, a censura na borda e a contabilidade em R.

## Contrato de recusa

- Apenas objetos Python nativos; planos com campos desconhecidos ou inválidos são recusados sem conversões implícitas.
- Tempo de captura declarado não pode ser posterior ou igual ao fechamento **da primeira vela elegível à entrada**, isto é, a vela seguinte ao sinal. O registro deve ser monotônico em relação à captura anterior.
- O mesmo sinal/setup/direção não pode ser duplicado no diário.
- A cadeia começa em `00…00` (64 zeros), usa sequência crescente e tem limite de 200 entradas.
- Modificações na sequência, timestamp, plano, hash anterior, hash atual, identificador do ativo, timeframe ou campos de autoridade invalidam o diário.
- Uma cadeia reescrita do zero com **novo hash esperado também reescrito** ainda poderá passar na verificação. SHA-256 não fornece testemunha nem impede backdating se o originador controla tudo.
- O módulo não salva automaticamente o diário em disco; não contata serviços externos, não registra preço de mercado, não envia ordens e não cria sinais.
- `externally_attested=False`, `time_provenance=CALLER_DECLARED_LOCAL_ONLY`, `authorizes_send=False`, P0 homologadas `0/6`.

## O que falta para evidência independente

A P0 de origem e custódia continua aberta: será necessário um terceiro confiável que assine data, identidade e conteúdo fora do controle de quem produz os planos, com proteção contra rollback e duplicação. Não simulamos essa autoridade; o diário A278 não pode acioná-la ou substituí-la.

Para alegações de validação histórica robusta também faltam estratégias gerando planos apenas com candles disponíveis naquele instante, coleta de séries auditadas, custos específicos (inclusive vencimento/rolagem WIN/WDO) e avaliação walk-forward que não reutilize os dados de validação para ajustes.

**HARD NO-GO, sem merge na main, sem Worker/deploy, sem contratação ou custo adicional.**
