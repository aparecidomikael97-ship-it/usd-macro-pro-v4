# ADR-0008 — Trading real permanece fail-closed

- Título: Trading real permanece fail-closed
- Data: 2026-09-29
- Status: ACCEPTED

## Contexto

ARCHITECTURE.md torna REAL_TRADING_ENABLED imutável em falso nesta versão e mantém o Guardian como dono de real_trade. A escada laboratório → público continua obrigatória.

## Problema

Papel ADMIN, flag verdadeira na chamada ou aprovação local poderiam ser coeridos para ordem real.

## Alternativas consideradas

Liberar trading por configuração solta foi rejeitado. A alternativa aceita é fail-closed até a escada e a revisão humana.

## Decisão

Trading real permanece desligado. A flag não é ligada por valor truthy. Aprovação não vira ordem.

## Consequências

O bloqueio de flag está implementado e em validação. A escada completa de promoção continua pendente. Nenhuma ordem real é autorizada por este ADR.

## Componentes afetados

atlasquant_aion_capabilities.py; Guardian; Safety Core.

## Segurança

Candle, score ou Top 10 não autorizam execução. NÃO OPERAR continua sendo resultado válido.

## Compatibilidade

Paper, shadow e laboratório não passam a significar conta real.

## Rollback/migração

Ligar trading real no futuro exige ADR novo, escada cumprida e aprovação humana. Este registro permanece como histórico do bloqueio.

## PR/commit relacionado

Evidência em atlasquant_aion_capabilities.py e test_atlasquant_aion_capabilities.py. Sem execução de mercado.

## Supersedes

Nenhum.

## Superseded by

Nenhum.
