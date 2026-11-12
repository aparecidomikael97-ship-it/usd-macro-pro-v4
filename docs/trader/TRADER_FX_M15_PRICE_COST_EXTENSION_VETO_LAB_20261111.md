# AtlasQuant Trader — filtro M15 de custo de cotação e movimento já realizado — 11/11/2026

**Estado: LAB, sem dados de mercado reais, sem leitura de conta, sem conexão MT5, sem sinais, sem ordem, sem gasto ou deploy.** Código e testes estão na PR #1851 em rascunho.

## Lacuna corrigida

O motor de macro tem filtros de notícias, regime e dependência de causas. A camada de OHLC M15 antiga verifica histórico e formato, mas **spread de candle não é cotação bid/ask no instante da decisão** e tampouco prova que existia liquidez executável. Um viés macro pode estar bem fundamentado e, mesmo assim, a entrada estar cara ou atrasada. O bloqueio deve ser anterior a qualquer tentativa de mostrar confiança operacional.

Arquivos novos:
- `atlasquant_trader_fx_m15_price_cost_veto_lab.py`
- `test_atlasquant_trader_fx_m15_price_cost_veto_lab.py`

**Regras do contrato de pesquisa (não calibradas):**
1. Somente um dos **28 pares FX canônicos** e direção hipotética `ALTA`/`BAIXA`. Não reutilizar sem adaptação para ouro, índices EUA, WIN/WDO ou contratos de corretoras diferentes.
2. Exige **21 velas M15 fechadas e consecutivas**, com abertura e fechamento em grade UTC, OHLC plausível, tick volume positivo, recebimento antes da decisão, um mesmo identificador de hash alegado para o lote; rejeita lacunas e registros futuros.
3. Exige **cotação bid e ask separada**, com hash alegado, instrumento igual ao par, observada até 90 segundos antes do corte, recebida até 20 segundos depois da observação e **antes** do horário decisório. Sem cotação atual, sem passar.
4. Calcula para fins de pesquisa: custo de spread em bps sobre midpoint; custo de spread relativamente à mediana de true range das 14 velas M15 anteriores; extensão de preço no sentido pesquisado desde a referência de cerca de 1 hora; choque de true range da última vela.
5. Hipóteses iniciais de veto: spread acima de **8 bps**, ou spread acima de **15% da faixa de referência**, ou movimento favorável já realizado acima de **2,5 vezes a faixa de referência**, ou choque da última vela acima de **3 vezes a faixa de referência**. Esses limiares são **apenas para testes sintéticos**, NÃO devem ser usados em produção sem estimativa por par, regime, horário e custos executáveis. O mesmo valor em bps pode ser inadequado entre pares.
6. Mesmo sem veto, saída `LAB_PRICE_COST_CONTEXT_NOT_VETOED_UNATTESTED`, `operational_bias=AGUARDAR`, `trade_authorized=false`, `publishable=false`, `calibrated_direction_probability=null`. Não prova independência, lucro, acerto, liquidez, origem da corretora nem preço realmente negociável.
7. Cotação falsa, recebimento após decisão, preço cruzado/zero spread, erro de SHA, gap de M15, barra incompleta, escala errada ou falta de quote => bloqueio.

**Validação:** 20 testes unitários sintéticos aprovados localmente; execução incluída na CI do GitHub em Python 3.11 e 3.12. Casos: quote válida, spread elevado absoluto/relativo, extensão longa/curta, movimento oposto, choque, dados antigos, atraso de captura, citações futuras, bad bid/ask, falta de vela, lacuna, volume zero, hash divergente, OHLC malformado, instrumento errado e clocks inválidos. A suíte usa SOMENTE preços inventados para testar lógica, não reproduz acerto de trade nem atualiza o Radar.

## Como integrar ao Precision Gate sem multiplicar indicadores

A próxima implementação deverá ser um **orquestrador fail-closed** que combina, no horário da decisão, módulos existentes: (A) macro bilateral e coerência D1/W1; (B) origem compartilhada de evidências `fx_evidence_dependency_gate_lab`; (C) calendário e notícia por par; (D) regime `market_regime_veto_lab`; e (E) **preflight M15 preço/custo**. Cada condição deve retornar `AGUARDAR: motivo` quando ausente ou reprovada; não converter o número de módulos aprovados em probabilidade. Um laboratório pode declarar candidato documental, mas não publicar até evidência prospectiva.

**Dados ainda necessários para uso sério:** captura *bid/ask* legítima e reproduzível, spread/latência intraday por par, especificações do broker, distinção entre preço indicativo e executável, comissão/slippage/swap, fuso e sessões, desempenho por horário/volatilidade e custos, e amostras de decisões registradas antecipadamente. O MT5 do usuário pode estar desligado, e o módulo não acessa essa máquina. Não contratar fonte paga nem instalar integração por conta própria.

## Métricas para demonstrar que isso realmente ajuda

Fazer avaliação A/B fora da amostra de (1) macro sem este filtro e (2) macro + veto, preservando **todas as oportunidades originalmente elegíveis**: quantidade total, percentuais de AGUARDAR, taxa direcional nos candidatos, custo líquido hipotético com hipóteses verificadas, atraso e estabilidade por par e regime. **Aumentar taxa de acerto selecionando apenas 1 ou 2 casos não é prova suficiente de robustez**; avaliar cobertura e intervalo de incerteza também.

**Status oficial:** GO-LAB, NO-GO alertas/integração, HARD NO-GO ordens reais. PR #1851 continua draft, sem merge/deploy. Foco permanece em vieses Forex D1/W1 com M15 apenas como filtro auxiliar de contexto, não como scanner ICT.
