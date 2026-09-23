# AtlasQuant — Teoria de Dow

Status: **DECISÃO DE PRODUTO APROVADA**

A Teoria de Dow entra no AtlasQuant como **camada de contexto, direção e
confirmação**, e não como setup isolado de entrada.

## Uso aprovado

- tendência primária: estrutura de **Weekly + Daily**;
- tendência secundária: estrutura de **H4 + H1**;
- execução/timing: continua com **ICT/SMC + gatilhos + Gate Chain + Risk**;
- confirmação entre mercados/ativos relacionados: evidência adicional quando
  houver relação definida e dados válidos;
- volume: evidência de confirmação apenas quando houver dado de volume válido e
  adequado ao mercado analisado;
- divergência ou dado ausente deve aparecer explicitamente como WAIT/insuficiente,
  nunca ser preenchido por suposição.

## Integração com ICT/SMC

Fluxo conceitual:

**Dow (contexto/tendência) → ICT/SMC (liquidez/estrutura/zona) → Trigger →
Gate Chain → Risk → autorização**

Dow não substitui BOS/MSS/CHOCH, FVG, Order Block, liquidez, AMD ou os filtros
macroeconômicos. A função é ajudar a responder: **qual é a tendência estrutural
maior e a correção/estrutura secundária está alinhada?**

## Segurança e mensuração

- Dow não gera ordem;
- Dow não transforma score em probabilidade;
- Dow não aumenta win rate declarado sem evidência;
- Dow não ignora News Shield, Data Health, System Health, Gate ou Risk;
- a contribuição de Dow para ranking/qualidade só poderá receber peso depois de
  backtest/Paper/ablação demonstrar valor incremental sem lookahead;
- até essa validação, entra como contexto observável e auditável.

Esta decisão permanece fixa até alteração explícita do escopo.
