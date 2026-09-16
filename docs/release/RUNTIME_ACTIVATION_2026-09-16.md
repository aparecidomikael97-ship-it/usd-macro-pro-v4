# AtlasQuant Runtime activation — 2026-09-16

Status: **RUNTIME_BRANCH_PROMOTED_AND_VALIDATED**

## Promotion

A promoção foi executada de forma preservadora de dados.

Referências:

- DEV candidata promovida: `001522d98d927cca2255a55decba1b7d4b71b8de`
- Runtime anterior: `ff979dc7c66ace0bc9b7355d19313f1cc6919511`
- Runtime atual: `998ef4ba8030d6babd73f43a287c7eeb33ebcdb3`
- Backup pré-promoção inicial: `atlasquant-runtime-backup-20260916-7a2ad3e`
- Backup intermediário: `atlasquant-runtime-backup-20260916-ff979dc`

A árvore promovida usa o código da DEV validada e preserva os blobs operacionais da Runtime.

## Dados preservados

Os sete caminhos mutáveis divergentes da Runtime foram preservados:

- `dados/autopilot_inputs_v107.json`
- `dados/autopilot_status_v107.json`
- `dados/configuracoes_completas_v937.csv`
- `dados/currency_news_current_v107.json`
- `dados/currency_news_validation_v1061.csv`
- `dados/master_market_map_v102.json`
- `dados/scanner_tecnico_v934.json`

Após a promoção, o diff DEV → Runtime contém somente esses sete arquivos de dados.

## Validação Runtime

O workflow `Quality tests` foi habilitado também para pushes de código na branch
`atlasquant-runtime`.

Run Runtime:

- GitHub Actions run: `35112939791`
- Compile gate: **verde**
- Testes: **650/650 OK**
- Resultado final: **success**

Isso valida a árvore efetivamente promovida da Runtime, incluindo os dados preservados.

## Limites ainda externos ao CI

Esta validação não substitui:

- health check do URL de produção/deploy real, se houver;
- validação das credenciais reais do ambiente hospedado;
- compilação final das Pine Strategies dentro do TradingView;
- verificação visual humana de todas as telas em navegador real.

Nenhuma alteração foi feita na `main` durante a promoção.


## Atualização final de compatibilidade

- Runtime atual após migração Streamlit: `911a8a2968b6391d8306f421d5d7dce328f33a74`.
- Quality run Runtime: `35114708095`.
- Resultado: **652/652 testes OK**, compile gate verde.
- Smoke headless continuou sem exceções, sem chamada Twelve Data na abertura e sem escrita HTTP remota.
- Os avisos de `use_container_width` observados no smoke anterior deixaram de aparecer após a migração para `width`.
- Os sete arquivos operacionais divergentes em `dados/` permanecem preservados.
