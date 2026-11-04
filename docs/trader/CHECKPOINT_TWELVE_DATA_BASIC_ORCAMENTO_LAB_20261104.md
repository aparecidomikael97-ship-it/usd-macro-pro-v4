# AtlasQuant Trader — Twelve Data Basic: capacidade gratuita (LAB, sem acesso)

Data: 04/11/2026. Este checkpoint é uma estimativa **offline** e conservadora;
não cria conta, não executa requisições, não usa token e não valida dados reais.

## Condições publicadas da modalidade Basic

- 8 créditos API por minuto; 800 créditos por dia (reinício às 00:00 UTC).
- Exemplo oficial de `/time_series`: um crédito por símbolo solicitado,
  inclusive quando os símbolos são agrupados em uma requisição.
- 8 créditos WebSocket experimentais; não equivalem a 28 assinaturas.
- Uso Basic: **interno sem exibição**; distribuição, exibição externa ou
  comercialização exigem análise contratual e, quando aplicável, licenciamento.
- Os termos, intervalos efetivamente habilitados e os símbolos disponíveis
  podem mudar ou exigir acesso específico.

Fontes oficiais:
- https://twelvedata.com/pricing
- https://support.twelvedata.com/en/articles/5615854-credits
- https://twelvedata.com/terms
- https://support.twelvedata.com/en/articles/5332349-commercial-and-personal-usage

## Cálculo conservador: 24 horas por dia

| Amostra | Consultas por símbolo por dia | Créditos totais | Restrição |
| --- | ---: | ---: | --- |
| 28 pares / 15 min | 96 | 2.688 | Ultrapassa 800/dia e 8/min |
| 28 pares / 60 min | 24 | 672 | Cabe no dia, mas 28 símbolos não cabem numa mesma janela de 8/min |
| 7 pares EUR / 15 min | 96 | 672 | Cabe na capacidade matemática de 8/min e 800/dia |

Sete pares `EUR/...` cobririam USD, JPY, GBP, CHF, AUD, CAD e NZD. Os
outros 21 cruzamentos podem ser **derivados matematicamente**, mas não se
tornam cotações independentes com bid/ask, spread e liquidez observados.
Esse eventual estudo de força relativa não autorizaria gatilhos de M15
nem promoveria a matriz W1/D1/H4/M15 operacional.

Uma requisição batch não remove a cobrança por símbolo. Mesmo com
672 créditos/dia, os 28 símbolos exigiriam pelo menos quatro janelas de
quota de 8/min, sem garantir observações sincronizadas. O modelo considera
o pior caso de 24 horas completas: a redução de sessões ou cache pode mudar
o consumo, mas não transforma o Basic em feed completo de execução.

## Guarda LAB implementada

Módulo: `atlasquant_fx_free_data_budget_lab.py`,
`estimate_free_fx_collection(symbols, poll_minutes=...)`.

Rejeita pares desconhecidos/invertidos/duplicados, periodicidade inválida,
excesso de créditos diários e coleções que excedem a quota de uma janela de
um minuto. O resultado positivo significa somente `RESEARCH_CAPACITY_ONLY`.
As flags `publishable`, `display_authorized`,
`provider_authenticated`, `data_coverage_verified`,
`market_data_connected`, `trade_authorized` e
`operational_m15_radar_ready` permanecem **falsas**, sempre.

## Decisão

- **GO-LAB de planejamento de capacidade** para testar matemática e quotas.
- **NO-GO para integração de preços no Radar** e para qualquer gasto.
- Antes de eventual acesso Basic: verificar cobertura real dos sete símbolos,
  direito de uso interno, restrições de exibição e a disponibilidade efetiva
  de `15min`. Não solicitar chaves nem contratar nesta fase.
- Para 28/28 observações de mercado sincronizadas, será necessária outra
  solução autorizada, ainda não selecionada.
