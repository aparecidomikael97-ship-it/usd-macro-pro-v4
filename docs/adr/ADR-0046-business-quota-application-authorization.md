# ADR-0046 — Aplicação de quotas exige autorização explícita e preflight separado

- Título: Aplicação de quotas exige autorização explícita e preflight separado
- Data: 2026-09-30
- Status: ACCEPTED

## Contexto

ADR-0045 produz uma revisão de capacidade e quotas vinculada ao ledger íntegro.

## Problema

Uma revisão verde não pode ser confundida com permissão para aplicar limites reais
nos tenants. Também é necessário vincular qualquer autorização ao digest exato
do plano revisado e manter cobrança separada.

## Decisão

Criar uma fronteira administrativa com:

1. token exato AUTHORIZE_BUSINESS_QUOTA_APPLICATION;
2. acknowledgements obrigatórios;
3. ator explícito;
4. vínculo ao capacity_review_digest e ao conjunto exato de tenants;
5. janela de mudança;
6. plano de monitoramento;
7. plano de rollback/restauração;
8. dry-run verificado;
9. suporte e resposta a incidentes prontos;
10. revisão de execução ainda separada da autorização.

O estado máximo automático é QUOTA_APPLICATION_EXECUTION_REVIEW_REQUIRED.

## Consequências

Mesmo uma autorização válida não aplica quotas. Billing, expansão e ações com
clientes continuam fronteiras separadas.

## Segurança

O módulo não aplica limites, não altera billing, runtime, tenants, tráfego,
deploy, integrações ou sistemas externos.

## Rollback

Read-only/administrativo; sem efeito externo a compensar.
