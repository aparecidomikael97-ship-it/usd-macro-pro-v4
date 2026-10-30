# A279 — Detector histórico causal de candidatos FVG (LAB, HARD NO-GO)

A279 cria **somente candidatos matemáticos para pesquisa histórica**. Não comprova ordem institucional, FVG "válido" no sentido de mercado, reversão, assertividade ou probabilidade de lucro. Não é detector de Order Block, BOS/CHOCH nem indicador de tela para operar.

## Por que esta etapa existe

Na A277 o usuário precisava digitar entrada/stop/alvo de cada estudo. A279 começa a produzir planos de pesquisa por uma regra **fixa e pública**, usando apenas velas que já estavam fechadas no instante do sinal. Isso permite testar uma regra com menos subjetividade e sem escolher entradas olhando os movimentos futuros.

## Regra A279_FIXED_FVG_SMA5_V1

1. Ler CSV histórico pelo importador estrito A276; cada candle tem timestamp de **fechamento** conhecido, corpo/range válido e ativo canônico.
2. Para o candle fechado `i`, exigir histórico de pelo menos cinco barras anteriores. Olhar FVG mecânico de três velas:
   - alta: `low[i] > high[i-2]`;
   - baixa: `high[i] < low[i-2]`.
3. Confirmar tendência apenas com informação até `i`: média simples de cinco fechamentos atual maior que a anterior e último fechamento acima da média para compra; sinais inversos para venda.
4. Exigir tamanho do gap >= 15% da amplitude média (`high-low`) dos últimos cinco candles fechados. Esse filtro é fixo, não otimizado.
5. Definir **plano candidato histórico** com `signal_time=close_time[i]`, entrada no meio do gap, stop na mínima/máxima das últimas três velas e alvo a 2R. Se os valores derivados não forem positivos e finitos, recusar o candidato.
6. O simulador histórico A277 só pode procurar entrada **após** a vela `i`. Stop e alvo na mesma barra continuam resolvidos conservadoramente pelo stop.
7. Para auditoria, registrar em cada candidato: timestamp, direção, quantidade de velas fechadas disponíveis, SHA-256 encadeado do prefixo de candles (de 0 a `i`), gap e médias de tendência. Isso permite verificar que adicionar candles futuros **não altera** as decisões antigas da regra fixa.

`strategy_spec_sha256` identifica os parâmetros declarados; não é assinatura externa do código ou origem do CSV.

## Interface de pesquisa

```python
from datetime import datetime, timezone
from atlasquant_aion_causal_fvg_lab import (
    generate_causal_fvg_csv, research_causal_fvg_backtest_csv,
)

# csv_text = seu CSV histórico válido no contrato A276
dados = generate_causal_fvg_csv(
    csv_text,
    symbol="EURUSD", timeframe="M15", timestamp_basis="CLOSE",
    now=datetime(2026, 10, 30, tzinfo=timezone.utc),
)
if dados["valid"]:
    print(dados["candidate_count"], dados["candidate_audit"])

# Para simular:
resultado = research_causal_fvg_backtest_csv(
    csv_text,
    symbol="EURUSD", timeframe="M15", timestamp_basis="CLOSE",
    now=datetime(2026, 10, 30, tzinfo=timezone.utc),
    validation_start="2026-10-01T00:00:00+00:00",
    cost_r=0.10, slippage_r=0.05,
    max_wait_bars=8, max_hold_bars=96,
)
```

Os relatórios de backtest continuam separados em treino/holdout, por mês UTC e com cenários de custos em R. Sinais não podem ser treinados/tunados olhando os resultados do holdout; a A279 usa parâmetros fixos.

## Limites e bloqueios

- Uma regra mecânica de três velas **não confirma FVG de alta qualidade**, mitigações, liquidez, sessões ou viés macro. OB, BOS/CHOCH, força de moedas e radar de reversão ainda estão fora desta etapa.
- A detecção é causal na lógica do código, mas foi reconstruída a partir de CSV histórico: **não registra recibo A278 com hora histórica falsa** e não prova quando o plano foi realmente criado. Os hashes locais não substituem a testemunha externa das P0.
- Os identificadores `WIN`/`WDO` são raízes sem vencimentos/rolagem verificados; `DXY`/`NAS100`/etc. não são feed autenticado. Não há integração a corretora nem custos/variações em pontos reais.
- Se houver mais de 200 candidatos, erro invalida a saída sem devolver resultados parciais. Indicadores com aritmética não finita falham fechados. Não há dados ao vivo nem calls de rede.
- Nenhuma autorização de `send`, ordem, sinal operacional, alerta, Worker, deploy, merge ou cobrança.

**P0 homologadas: 0/6. HARD NO-GO mantido.**

Próximo estudo sugerido: comparar regras alternativas sem uso do holdout para seleção e, antes de falar em FVG realmente válido, auditar contexto de estrutura, zona, reação, sessão e dados de mercado externos confiáveis.
