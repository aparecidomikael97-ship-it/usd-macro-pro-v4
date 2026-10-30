# A275 — Overlay AION Trader para Índices/Futuros (LAB, 30/10/2026)

**Base A274 #1725. PR DRAFT isolada, sem merge, Worker, Render, corretora, novos dados, sinais, alertas, ordens ou custos.**

## Motivação
A269 cobre 28 pares FX, com seis timeframes separados. O Radar já declara `INDEX_UNIVERSE`: DXY, US30, NAS100, SPX500, IBOV, WIN, WDO. A275 **reaproveita exatamente esses sete códigos de apresentação**, em uma visão própria `non_fx_observation` opcional e sem afetar `rows` e `fresh_m15_pairs` do Forex.

`WIN` e `WDO` são **raízes de contratos futuros**, não instrumentos negociáveis com vencimento, série, corretora ou especificação verificada. Os outros códigos são rótulos de índices do Radar, não símbolos de feed/autorização.

## Contrato
- `nonfx_readonly_overlay(evidence=None, now=...)` devolve sete linhas e M5/M15/M30/H1/H4/D1 separados. Sem input, todos ficam `NO_SEPARATE_TIMEFRAME_EVIDENCE`.
- Insumo facultativo `{simbolo: {timeframe: candle_record}}`, com apenas os sete símbolos exatos do Radar; recusa aliases, pares FX, contratos com vencimento embutido e fontes extra. Cada candle usa a validação estrutural A269, com `INPUT_FRESH_CLOSED_<TF>_UNATTESTED` quando declarado recente. Timestamp/candle fornecidos pelo host **não provam origem externa**.
- A função `trader_readonly_observation` e a hidratação residente recebem `non_fx_evidence=None` optativo. Se ausente, resultado anterior permanece idêntico. Se fornecido, acrescenta `non_fx_observation` separado. Falha na hidratação continua limpando a observação.
- Todos os campos de autorização são negativos: `no_orders=True`, `no_alerts=True`, `authorizes_send=False`, `p0_homologated=0`. Sem chamadas a provedores, reamostragem ou cálculo de oportunidade.

## 12 testes
Registro exato, falta de evidências, H1 isolado, sete séries não atestadas, aliases e câmbio recusados, fonte/staleness, WIN/WDO sem vencimento, compatibilidade exata FX28, overlay vazio, hidratação explícita e limpeza, proibição de rede/ordens. CI Ubuntu/Windows inclui A275+A269+A268 e regressões Trader/Guardião de Risco.

## Limites
A275 é estrutura de observação, não um radar de pernadas, reversões, OB/FVG/BOS/CHOCH nem cobertura de mercado atual. Sem feed autenticado, assinatura independente ou seleção de contrato. **HARD NO-GO, seis P0 sem homologação, UNCERTAIN=ZERO_AUTO_RESEND.** Negócios congelada na visão read-only, Investimentos scaffold, Trader prioritário.
