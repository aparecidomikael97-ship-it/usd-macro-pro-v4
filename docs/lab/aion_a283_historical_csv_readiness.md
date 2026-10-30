# AION A283 — Pré-checagem de históricos (LAB)

**Situação:** somente pesquisa offline; **HARD NO-GO** na operação real.
P0: **0/6 homologados**. Sem Worker, deploy, alertas, ordens ou serviços
pagos novos. Negócios permanece congelado. Foco no Trader/Investimentos.

## O problema

A282 compara três regras históricas (FVG, FVG+BOS e FVG+BOS+OB)
corretamente com a mesma divisão cronológica. Mas um arquivo curto,
plano ou repetitivo pode parecer bem formatado mesmo sem oferecer um
estudo minimamente útil. A283 faz o *preflight* **antes** da comparação,
sem presumir que dados exportados sejam verdadeiros ou independentes.

## O que é conferido

- O importador A276 valida CSV UTF-8, OHLC, datas com fuso, símbolo
  permitido, timeframe e ordem crescente, com limite de 1 MB e
  10.000 velas por arquivo.
- O limite treino/teste precisa coincidir **exatamente** com o
  timestamp de uma vela fechada. Usa a semântica declarada `OPEN`
  ou `CLOSE`, sem inventar conversão de timeframe.
- Cada parcela precisa ter **no mínimo 100 velas**, pelo menos
  **8 preços de fechamento distintos** e **25 velas com máxima maior
  que mínima**. São filtros conservadores contra arquivos triviais,
  **não** garantias de qualidade.
- Detecta intervalos de tempo mais longos ou fora da grade, mas os
  informa como advertência: fins de semana, feriados ou suspensão
  podem justificar lacunas. A283 **não conhece** as sessões por
  ativo ou o motivo da ausência de dados.
- Para `WIN` e `WDO`, avisa que o contrato/vencimento do futuro
  **não foi resolvido**.
- O SHA-256 do CSV e o SHA-256 das velas normalizadas devem ser
  iguais no pré-check e no relatório A282. A separação treino/teste
  e a ausência de autoridade operacional também precisam coincidir.
- Em lote, até **8 séries** (ativo/timeframe) são conferidas primeiro.
  Se uma falhar, **nenhuma comparação é executada** e não há
  relatório parcial. Resultados de ativos diferentes não são somados.

## Dois critérios diferentes

1. **`ready_for_offline_research`** só significa que o arquivo tem
   estrutura mínima para ser estudado, sem afirmar autenticidade.
2. **`INSUFFICIENT_HOLDOUT_SAMPLE_FOR_COMPARISON`** vem de A282
   quando qualquer uma das três versões tem menos de **30 operações
   realmente executadas no holdout**. Passar em A283 não elimina
   essa insuficiência.

Mesmo se os dois critérios forem atendidos, o estudo permanece
**descritivo**, sem previsão de preço, edge provado ou modelo vencedor.

## Exemplo offline

```python
from datetime import datetime, timezone
from pathlib import Path
from atlasquant_aion_csv_readiness_lab import (
    preflight_historical_csv, compare_if_preflight_ready_csv,
)

csv_text = Path("EURUSD_M15_exportado.csv").read_text(encoding="utf-8")
shared = dict(
    csv_text=csv_text,
    symbol="EURUSD", timeframe="M15", timestamp_basis="CLOSE",
    now=datetime.now(timezone.utc),
    validation_start="2026-08-01T10:00:00+00:00",
)
preflight = preflight_historical_csv(**shared)
if preflight["ready_for_offline_research"]:
    report = compare_if_preflight_ready_csv(
        **shared, cost_r=0.1, slippage_r=0.05,
    )
    # Apenas pesquisa; NUNCA colocar em gate/sinais/ordens.
```

Para vários arquivos, use `compare_if_preflight_ready_batch` com os
mesmos campos por série exigidos pela A282; não inclui operações
reais nem consulta qualquer provedor.

## Limitações conscientemente preservadas

- Dados e origem são fornecidos pelo pesquisador e **não atestados**;
  timezone e fonte podem ter sido informados incorretamente.
- Não há validação independente de sessões, volume efetivamente
  negociado, spread, rollover, mudanças de contrato ou ajustes de
  séries de índices.
- O corte treino/holdout **não** comprova que foi escolhido antes
  de olhar os resultados; não é teste fora de amostra independente.
- Estatísticas de testes sintéticos **não equivalem** a uma
  validação do mercado real.
- Nenhum histórico real foi comprado, baixado ou verificado em A283.

## Validação

Workflow isolado Python 3.12 Ubuntu/Windows, 28 testes A283 mais
regressões A282→A268, guardião de risco, simulador e scanner.

Permanecem **0/6 P0**, **HARD NO-GO** e sem promoção de produção.
