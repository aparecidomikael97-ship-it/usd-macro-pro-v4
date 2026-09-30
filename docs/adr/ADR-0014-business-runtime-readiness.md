# ADR-0014 — Runtime do AION Business exige gate separado da certificação

- Título: Runtime do AION Business exige gate separado da certificação
- Data: 2026-09-30
- Status: ACCEPTED

## Contexto

O AION Business Expert foi certificado em evidência ligada a SHA e fingerprint.
A certificação prova os gates de produto, segurança, CI e revisão humana, mas não
deve conceder autoridade operacional automaticamente.

## Problema

Misturar `CERTIFIED` com runtime ligado aumentaria o impacto de qualquer erro e
permitiria que uma aprovação de certificação fosse interpretada como autorização
para contato, cobrança, publicação ou outras ações externas.

## Decisão

Criar uma camada específica de runtime readiness. O primeiro nível possível é
somente `SANDBOX_READY`, com ações `read`, `analyze` e `draft`.

Para chegar ao sandbox, o sistema exige certificação válida ligada ao mesmo SHA
e fingerprint, isolamento, rede externa desligada, pagamentos/publicação/deploy/
trading real desligados, auditoria, rollback e kill switch.

Depois disso pode ser criado um pacote `RUNTIME_APPROVAL_REQUIRED`, que ainda
mantém `runtime_activation_approved=false`.

## Consequências

Certificação não vira execução por acidente. O Business Expert pode ser testado
em ambiente controlado antes de qualquer futura ativação operacional.

## Segurança

Nenhum estado deste ADR autoriza runtime produtivo, contato externo, contrato,
pagamento, publicação, gasto, deploy, merge ou trading real.

## Compatibilidade

ADR-0012 define escopo/certificação e ADR-0013 define proveniência externa e
revisão humana. Este ADR atua depois deles e não altera seus gates.

## Rollback

O módulo é read-only e não persiste runtime. Sua retirada não exige migração de
dados nem restauração de efeitos externos.

## Supersedes

Nenhum.

## Superseded by

Nenhum.
