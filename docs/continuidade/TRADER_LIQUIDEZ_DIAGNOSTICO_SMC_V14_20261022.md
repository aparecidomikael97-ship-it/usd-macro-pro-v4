# Trader — Diagnóstico da ausência de BOS/CHOCH/MSS/OB/FVG e preservação de liquidez (LAB v1.4)
**Solicitação do proprietário em 22/10/2026, após imagens v1.3 DXY M15/H1.**

## Comportamento identificado na v1.3
- BOS/CHOCH/MSS expiravam após 8 velas M15 ou 6 velas H1; até um rompimento correto desaparecia rapidamente; outros dependiam de fechamentos além de pivôs e do filtro de corpo ATR.
- OBs dependiam de rompimento com deslocamento ≥0,80 ATR e da ausência de revisita à vela oposta; FVG exigia gap ≥0,30 ATR, corpo ≥0,85 ATR e rompimento estrutural recente na mesma direção.
- Referência H1 marcava `DISTANTE` no painel: filtro de distância ocultava corretamente a zona, e isso não demonstrava falha do rastreador H1.
- **Zonas de liquidez obrigatórias:** top/fundo do dia, semana e mês (em formação ou período fechado), EQH/EQL confirmados por pivôs e última varredura quando possível. A condição de mercado longínqua pode exigir ocultação visual sem apagar o cálculo; exibir razão no painel.
- Não confundir níveis potenciais de liquidez com ordens observadas ou prova de fluxo institucional.

## Protótipo offline entregue nesta conversa
`AtlasQuant_SMC_Foco_LAB_v14.pine` acompanha download em artefato de conversa, **não foi incorporado como código no GitHub e não está compilado no TradingView**. Nesta candidata:
- duração evento H4 6, H1 12, M15 20, M5/outras menores 18 velas, só o evento mais recente desenhado;
- estrutura: pivô 4, excedente 0,05 ATR, corpo ≥0,35 ATR; OB deslocamento ≥0,65 ATR; FVG gap ≥0,18 ATR e corpo ≥0,60 ATR; confluência FVG passa a opcional;
- possíveis topos/fundos iguais (EQH/EQL) ativos inicialmente, um por lado, invalidados/retirados por varredura via pavio de candle fechado ou TTL de 72 velas;
- máximas/mínimas D/W/M mantidas com filtro de proximidade; a opção de mostrar todas continua disponível;
- painel distingue `SMC local`, `Zonas locais` e `Liquidez`, preservando H4/H1 e referência H1.

**Riscos e limites:** filtros menos estritos tornam sinais mais frequentes e talvez menos precisos. OB/MSS/Sweep continuam heurísticas, não regras institucionalmente certificadas; ausência de zona num instante é possível e honesta; perspectiva H4/H1 divergente não é autorização de trade. Sem backtest, sem confirmação de compilação, sem P0 homologado e sem merge/deploy.
