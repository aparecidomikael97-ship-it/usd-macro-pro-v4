# A268 — Núcleo AION Trader, observação offline e sem custos novos

**Escopo:** LAB e READ-ONLY; HARD NO-GO operacional; 0/6 P0; sem Worker, corretora, ordens, alertas automáticos, merge ou deploy. Negócios permanece congelada **nesta composição de leitura**, não nas configurações globais ainda instaladas. Investimentos fica como estrutura prevista.

## Reutilização real em vez de criar outro scanner

O repositório já contém `atlasquant_trader_resident.py` (leitor de snapshot e cache residente), `atlasquant_instrument_registry.py` (28 pares FX canônicos), `atlasquant_risk_guardian.py` (Guardião de Risco), `atlasquant_scanner_coverage.py` e estratégia de replay FVG offline. A268 **não duplica motores, não calcula novos sinais e não busca preços**.

A nova função pura `atlasquant_aion_trader_observation.trader_readonly_observation` recebe apenas a apresentação que já foi carregada pelo Trader (ou dados sintéticos em testes), reaproveita o registro canônico dos 28 pares e devolve um painel:

- **Um registro para cada um dos 28 pares**, sem confundir DXY/índices/cripto com FX. Duplicações ou aliases repetidos de um par impedem que ele seja classificado como atual.
- **M15 apenas quando há série de candles fechados existente**, fonte reconhecida do scanner/cache ou cache Twelve atual, carimbo de tempo timezone-aware realmente dentro de 70 min, `validated=True`, estado de apresentação `CURRENT` e nenhum marcador de histórico. Um snapshot recente **não renova** candle técnico velho; carimbo futuro ou ingênuo não autoriza current.
- Matriz de timeframes `M5/M15/M30/H1/H4/D1`. Somente M15 recebe evidência do cache disponível; **os demais sempre exibem `NO_SEPARATE_TIMEFRAME_EVIDENCE`** até haver dados fechados por período, não calculados artificialmente a partir de M15.
- `all_28_fresh_closed_m15` somente quando os 28 pares passam individualmente pelos critérios acima; jamais chamar esse quadro de 28/28 se os pares faltam ou estão velhos.
- Força relativa de moedas opcional, aplicada a **todos os pares FX**, se o chamador **fornecer** oito pontuações finitas `USD/EUR/GBP/JPY/CHF/CAD/AUD/NZD`, com fonte e horário recente. Não inventa scores e rotula o comparativo `UNVERIFIED_INPUT_CONTEXT_ONLY` (base mais forte, cotação mais forte ou empate). Não utiliza esses scores como ordem nem como recomendação.
- Integra a avaliação existente `RiskLimits/RiskState/evaluate_risk_guard` somente se os dois forem fornecidos. Sem parâmetros, risco `UNVERIFIED_BLOCKED`. Mesmo quando o estado simulado de risco não está travado, continua **NO TRADING**.
- Exibe apenas `context_bias_not_signal` como histórico/contexto; todas as linhas têm `recommendation=NONE_READ_ONLY` e `authorizes_order=False`. Nenhum broker, API, chamada HTTP, sinal de entrada/saída ou timer.

`atlasquant_trader_resident.hydrate_trader_resident_state` passa a incluir `atlasquant_aion_trader_observation` **exclusivamente a partir do estado que já estava em memória**; sem novos pedidos de API. Se um refresh falha, o campo é retirado do `session_state`, preservando contrato antigo de limpar todos os dados anteriores, sem deixar uma avaliação velha como atual.

## Interface e teste

```python
from atlasquant_aion_trader_observation import trader_readonly_observation
board = trader_readonly_observation(existing_resident_dict)
# board["rows"] contém os 28 pares, evidence por M15, comparação opcional.
# board["no_orders"] == True; board["mode"]["authorizes_send"] == False.
```

Ensaios A268: falta total de dados, scanner M15 atual/velho, snapshot atual com técnico velho, fonte desconhecida, timestamp futuro, entrada `validated` falsa, cache Twelve existente, contagem 28/28 exata, duplicação de símbolos FX, comparação opcional em todos os 28, rejeição NaN e source ausente, bloqueios Guardião de Risco, Negócios congelada apenas neste read-model, atualização e limpeza de sessão e ausência de chamadas a corretora/provedor.

CI dedicada Ubuntu/Windows com A268 + regressões do pipeline `test_atlasquant_reference_resident.py`, cadastro FX e Guardião de Risco, em paralelo ao anterior A267. O plano de congelar operações B2B globalmente **não está implementado aqui**: o `AION_BUSINESS_ENABLED` global pré-existente pode continuar True até decisão e alteração específica revisada. Isto é apenas um módulo de leitura de Trader.

**P0 0/6, HARD NO-GO e UNCERTAIN=ZERO_AUTO_RESEND preservados**. CI de LAB não é homologação operacional nem prova de atualidade dos feeds externos. Nenhuma cobrança nova.
