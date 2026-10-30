# A281 — OB experimental causal + preferência FVG por proximidade (LAB)

**HARD NO-GO. Sem sinais operacionais.** A281 acrescenta um proxy objetivo de Order Block ao BOS mecânico A280 e permite estudar OB e FVG no mesmo relatório histórico A277.

## O que o código chama de OB (proxy, não comprovação institucional)

1. Detectar **BOS confirmado** conforme A280. Não criar OB no primeiro rompimento nem num CHOCH.
2. No fechamento do BOS, procurar entre as **últimas cinco velas anteriores** a mais recente com corpo oposto:
   - BOS de alta: vela anterior com `close < open`;
   - BOS de baixa: vela anterior com `close > open`.
   O próprio candle BOS nunca é usado como sua fonte.
3. Zona OB de pesquisa: máxima/mínima completas dessa vela oposta. Entrada no ponto médio; stop fora da zona, com buffer de 10% de sua amplitude; alvo fixo a 2R.
4. Se não existir vela com corpo oposto ou se qualquer nível derivado não for positivo e finito, **não criar candidato**. A razão fica em `ob_audit`.
5. O proxy só é conhecido após o fechamento do BOS e não consulta candles seguintes. O registro guarda `opposite_candle_time`, `bos_confirmed_at`, zona, direção e hash do prefixo A280.

Esse proxy **não** verifica fluxo institucional, mitigação, liquidez, origem de ordens ou reação futura. É um ponto de partida operacionalmente isolado para pesquisa, não um OB “válido” no sentido exigido para operar.

## Quando OB e FVG aparecem juntos

Por preferência de interface do AtlasQuant, o FVG fica como candidato principal somente se:

- ambos se referirem ao **mesmo fechamento de vela** e à **mesma direção**;
- o FVG já tiver passado pelo filtro BOS da A280;
- as zonas se sobrepuserem ou estiverem separadas por até **10% da largura da zona menor**.

O OB coincidente é registrado como `FVG_PREFERRED_SAME_CLOSE_NEAR_ZONE` e removido **da lista de novos candidatos desse fechamento**.

**Não apagamos um OB de uma vela anterior porque apareceu um FVG mais tarde.** Isso seria usar dados futuros para alterar decisões passadas (repaint). Planos simultâneos não colados continuam submetidos ao bloqueio de posição sobreposta do A277.

Importante: a preferência FVG é uma regra de organização/pesquisa, **não uma afirmação de maior precisão estatística**.

## Interface de pesquisa

```python
from datetime import datetime, timezone
from atlasquant_aion_causal_ob_fvg_lab import (
    generate_causal_ob_fvg_csv, research_ob_fvg_backtest_csv,
)

# csv_text = CSV de candles históricos conforme A276
resultado = generate_causal_ob_fvg_csv(
    csv_text, symbol="EURUSD", timeframe="M15",
    timestamp_basis="CLOSE",
    now=datetime(2026, 10, 30, tzinfo=timezone.utc),
)
if resultado["valid"]:
    print(resultado["ob_audit"])
    print(resultado["combined_candidate_plans"])

comparacao = research_ob_fvg_backtest_csv(
    csv_text, symbol="EURUSD", timeframe="M15",
    timestamp_basis="CLOSE",
    now=datetime(2026, 10, 30, tzinfo=timezone.utc),
    validation_start="2026-10-01T00:00:00+00:00",
    cost_r=0.10, slippage_r=0.05,
)
```

O relatório A277 continua com `train`, `holdout`, resultado mensal UTC, cenários de custos em R e resumos por setup FVG, OB e PULLBACK (o último só aparece se houver planos manuais no fluxo A277). A281 **não** otimiza parâmetros no holdout.

### Limites obrigatórios

- Padrões FVG/OB/BOS/CHOCH continuam classificações **mecânicas**, sem dados de microestrutura, contexto macro, força cambial, tick size, custos reais ou autenticação de feed.
- `WIN`/`WDO` permanecem referências de raízes de futuros sem vencimento/rolagem verificados. Nenhum nome de índice é um mapeamento de corretora autenticado.
- Não há detecção de reversão futura; CHOCH é só evento histórico.
- A281 não gera recibos históricos falsos A278; não prova que esses planos foram capturados na época das velas.
- Erro de CSV, limite de candidatos ou contrato histórico faz o fluxo de pesquisa falhar fechado.
- **Sem ordens, Worker, alertas, deploy, merge em main ou novos serviços pagos. Seis P0 seguem 0/6, e HARD NO-GO permanece.**

Para avaliar se a preferência FVG ou um OB realmente acrescentam qualidade, serão necessários CSVs reais de procedência legítima, amostras adequadas, custos calibrados e comparação walk-forward sem selecionar parâmetros olhando os resultados reservados.
