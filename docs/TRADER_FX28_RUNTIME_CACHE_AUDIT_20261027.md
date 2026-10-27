# AtlasQuant Trader — Auditoria real de cobertura FX28 (27/10/2026)

**Somente leitura; sem chamada de API, segredo, compra, ordem, Worker ou deploy.** Esta nota registra o que foi observado no repositório e separa prova de teste sintético.

## Evidência de runtime conferida

- Branch: `atlasquant-runtime`, commit observado `f66e5ed3c84639f3147c34262034f32d320755a0` em 27/10/2026 às 08:22 UTC.
- `dados/twelve_series_v1108.json`: conteúdo literal `{"series": {}}`. **0 instrumentos/timeframes persistidos no arquivo lido**. Isto impede tanto a avaliação de 28 pares observados quanto a inferência atual via sete pares USD a partir desse arquivo.
- `dados/autopilot_status_v107.json`: `last_run=2026-10-27T08:22:18.917859+00:00`; `twelve_daily_blocked=true`, `twelve_block_type=CONTROLE_INDISPONIVEL`, `twelve_calls_this_run=0`, `scanner_ready=false`, `operational_readiness=DEGRADED`.
- Orçamento persistido interno no relatório: `used=14`, `limit=480`, `remaining=466` naquele instante. **São contadores internos**, não prova de créditos reais restantes na Twelve Data. Um bloqueio de controle não deve ser confundido com esgotamento do fornecedor.
- `dados/scanner_tecnico_v934.json` registra `last_fetches` de sete pares USD por volta de 02:23 UTC no mesmo dia; esse campo não comprova que as séries estejam presentes agora no cache compartilhado.
- `autopilot_v107.td_fetch` contém recusa explícita para par fora de `PAIR_ORDER` (sete pares). O módulo `atlasquant_pair_matrix_core.py` também monta sete pares USD. O registro canônico `FX_28` tem 28; **cadastro != séries observadas != análise operacional**.
- A execução programada 40472852203 terminou `success` como job, mas o JSON de estado nela exibiu o mesmo bloqueio. **CI/schedule success não implica scanner saudável.**

Referências de inspeção:
- [Cache compartilhado](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/blob/atlasquant-runtime/dados/twelve_series_v1108.json)
- [Status Autopilot](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/blob/atlasquant-runtime/dados/autopilot_status_v107.json)
- [Código do coletor](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/blob/main/autopilot_v107.py)
- [Run do Autopilot](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40472852203)

## Dois níveis de contexto cambial — sem confusão

1. **OBSERVADO_28**: 28 séries reais completas, sincronizadas e recentes. Somente `assess_28_pair_strength` pode produzir `COMPLETE_CONTEXT_ONLY` com 28 retornos efetivamente observados. Não é sinal.
2. **IMPLÍCITO_7_USD**: sete retornos observados dos pares com USD podem determinar, por diferença, 21 retornos cruzados teóricos. `implied_28_from_7_usd` registra `IMPLIED_28_CONTEXT_ONLY` com exatamente sete etiquetas `OBSERVED_USD_LEG` e 21 `IMPLIED_CROSS_NOT_QUOTED`. **Não substitui preços próprios de EUR/GBP, GBP/JPY etc., spreads, liquidez ou candles de FVG/OB.**

O adaptador `implied_28_from_supplied_cache` é totalmente offline, só recebe um cache já fornecido e fica em WAIT se os sete USD legs não estiverem presentes, frescos e sincronizados. A condição observada em runtime hoje é WAIT, não sucesso de mercado.

## Próximos testes antes de qualquer alteração operacional

1. Identificar a falha específica que gerou `CONTROLE_INDISPONIVEL` na inicialização do orçamento, sem exibir credenciais, aumentar cota, limpar contadores ou repetir consulta automaticamente.
2. Confirmar de modo independente a persistência dos sete pares no cache em uma execução futura; **não** forçar o collector nem gerar chamadas adicionais no ambiente real para fabricar estado verde.
3. Medir com dados históricos disponíveis o desempenho de contexto implícito versus 28 pares observados. Incluir defasagem, spread, eventos, sessões e reversões; preservar fontes e carimbos de tempo.
4. Só projetar uma coleta direta dos 28 pares após cálculo completo de orçamento por horizonte e autorização do proprietário se houver custo/consumo adicional. O limite interno de 480 não equivale a permissão para gastar.
5. AION: seis P0 continuam abertas e HARD NO-GO. Este laboratório não modifica as regras de autoridade, Worker, Outbox ou SEND.

**Status da entrega:** especificação e 53 testes sintéticos (38 do bloco anterior + 15 para inferência); aprovações de CI devem ser conferidas por commit. Nenhuma taxa de acerto foi demonstrada.
