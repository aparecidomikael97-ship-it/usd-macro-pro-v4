# A280 — Estrutura causal de pesquisa: pivôs, BOS e CHOCH (LAB)

**HARD NO-GO. Somente histórico offline.** A280 complementa os candidatos FVG A279 com uma classificação objetiva e conservadora de rompimentos de estrutura. Não é confirmação institucional de ICT/SMC, não prevê reversão e não é um sinal operacional.

## Contrato matemático A280_DELAYED_PIVOT_BREAK_V1

1. Pivô de topo `j`: `high[j]` precisa ser **estritamente maior** que as máximas das 2 velas fechadas anteriores e das 2 posteriores. Fundo usa mínima estritamente menor. Empates não passam.
2. **O pivô só é conhecido na vela `j+2`**, quando as duas velas posteriores também já fecharam. A vela que confirmou o pivô não pode usar esse mesmo pivô para declarar rompimento; é necessário pelo menos o próximo fechamento.
3. Uma quebra de alta requer o fechamento cruzar **de baixo para cima** o topo confirmado mais recente e ainda não consumido. Baixa requer cruzar o fundo confirmado mais recente de cima para baixo.
4. Primeira quebra sem direção anterior: `INITIAL_BREAK`, **não** chamada de BOS. Próxima quebra na mesma direção: `BOS` (continuação). Quebra contrária: `CHOCH` (mudança de contexto **histórica**, não previsão de reversão).
5. Um pivô rompido é marcado como consumido e não pode produzir vários eventos. Se níveis contraditórios gerarem dois rompimentos opostos na mesma vela, a leitura é invalidada até aparecer um novo contexto.
6. Cada evento documenta `pivot_time`, `pivot_confirmed_at`, `detected_at`, preço do pivô, direção, tipo e SHA-256 encadeado do histórico conhecido até esse fechamento.

## Filtro sobre FVG A279

O detector FVG já exigia gap de três candles, SMA5 alinhada e target fixo 2R. A280 **não altera os parâmetros da A279**. Acrescenta:

- Só admitir o candidato FVG para simulação quando **o último evento estrutural histórico** for BOS da mesma direção e ocorrido nos últimos **8 candles fechados** (oito barras, não oito minutos).
- Primeiro rompimento, CHOCH, direção contrária, BOS antigo ou falta de estrutura: **candidato FVG rejeitado pelo filtro**, mas registrado em `filter_decisions` com motivo.
- Os eventos CHOCH ficam em `reversal_context_records` exclusivamente como diagnóstico. Nada dispara alerta ou ordem.
- Mesmo um FVG com BOS alinhado continua um **candidato mecânico não validado para operar**, sem comprovação de liquidez, sessão, mitigação, contexto macro ou força relativa das moedas.

## Saída

- `generate_causal_structure_csv(csv_text, symbol=..., timeframe=..., timestamp_basis=..., now=...)` devolve `structure_events`, `reversal_context_records`, `filter_decisions`, `filtered_candidate_plans`, contadores e fingerprints de histórico.
- `research_structure_filtered_backtest_csv(..., validation_start=..., cost_r=..., slippage_r=...)` usa esses planos apenas no motor A277 de pesquisa: entradas depois da vela sinal, treino/holdout separados, saída censurada na borda e cenários de custos em R.
- É permitido testar 28 Forex + 7 referências internas do Radar, incluindo WIN/WDO **como raízes sem contrato por vencimento verificado**.
- Nenhuma otimização é realizada no holdout. `structure_spec_sha256` é um hash de parâmetros locais, não autenticação de dados ou assinatura externa do programa.

### Precauções importantes

- Mesmo uma implementação prefix-only reconstruída hoje sobre CSV antigo **não comprova** quando os planos foram efetivamente criados. A280 não escreve recibos A278 com horário histórico fictício.
- BOS/CHOCH são convenções operacionais dependentes da definição de pivôs e fechamento; o código não afirma consenso ICT/SMC nem comportamento futuro.
- Filtrar mais candidatos pode reduzir o tamanho da amostra e piorar resultados. Comparações em séries amplas e separadas ainda serão necessárias.
- Sem feed ao vivo, broker, ordens, sinais autorizados, Worker, alertas, deploy, merge em main ou serviço novo.
- **Seis P0 seguem 0/6 homologadas. Operação real permanece HARD NO-GO.**

Próxima pesquisa possível: medir de forma descritiva o impacto de filtros por sessões, volatilidade e OB com dados de procedência verificável; depois avaliar walk-forward com amostras suficientes, sem otimizar no holdout.
