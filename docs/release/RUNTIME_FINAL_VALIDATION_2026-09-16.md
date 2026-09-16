# AtlasQuant — Runtime final code-level validation 2026-09-16

Status: **RUNTIME_CODE_VALIDATED_EXTERNAL_CHECKS_PENDING**

## Runtime validada

- Runtime atual: `911a8a2968b6391d8306f421d5d7dce328f33a74`
- Quality run: `35114708095`
- Compile gate: **verde**
- Testes: **652/652 OK**
- UI smoke headless: incluído na suíte da própria Runtime
- `main`: não alterada nesta etapa

## Smoke da UI

O teste `test_atlasquant_runtime_smoke.py` abre `usd_macro_pro_v4_cloud.py` via
Streamlit AppTest com provedores indisponíveis e valida:

- boot sem exceções;
- simples abertura sem chamadas Twelve Data;
- simples abertura sem escritas HTTP remotas;
- renderização da interface principal.

## Compatibilidade Streamlit

Os usos app-facing de `use_container_width` que apareciam no smoke foram migrados para a
API atual `width`.

Foi adicionado `test_streamlit_width_compat.py` para impedir regressão nos módulos cobertos.

No run Runtime `35114708095`, a suíte terminou sem os avisos
`Please replace use_container_width with width` que apareciam no smoke anterior.

## Dados operacionais preservados

Os sete blobs divergentes de Runtime permanecem preservados após a promoção de compatibilidade:

- `dados/autopilot_inputs_v107.json`
- `dados/autopilot_status_v107.json`
- `dados/configuracoes_completas_v937.csv`
- `dados/currency_news_current_v107.json`
- `dados/currency_news_validation_v1061.csv`
- `dados/master_market_map_v102.json`
- `dados/scanner_tecnico_v934.json`

Nenhuma substituição por dados DEV foi realizada.

## Limites externos que continuam pendentes

Esta validação fecha o código/CI da Runtime, mas não substitui verificações que dependem de
ambiente externo:

1. abrir a URL real de produção, se houver, e confirmar health check HTTP;
2. conferir visualmente todas as telas em navegador real;
3. validar as credenciais/secrets efetivamente configuradas no ambiente hospedado;
4. compilar as cinco Pine Strategies dentro do TradingView;
5. executar uma rodada live controlada respeitando quota e Gate antes de considerar operação real.

Essas pendências não são falhas detectadas pelo CI; são verificações externas que o repositório
sozinho não consegue provar.

## Estado de fechamento

- Código Runtime promovido: **sim**
- Suíte Runtime verde: **sim**
- UI headless sem exceções: **sim**
- Twelve Data no boot: **zero chamadas no smoke**
- Escritas HTTP no boot: **zero no smoke**
- Dados Runtime preservados: **sim**
- Main alterada: **não**
- Deploy real validado: **pendente**
- TradingView Pine compilado no ambiente real: **pendente**

