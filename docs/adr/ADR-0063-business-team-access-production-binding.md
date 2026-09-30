# ADR-0063 — Equipe & Acessos só entra em produção com conta individual, MFA forte, registry persistido e revogação verificável

Título: Equipe & Acessos só entra em produção com conta individual, MFA forte, registry persistido e revogação verificável  
Data: 2026-09-30  
Status: ACCEPTED

## Contexto

O RBAC Business já define perfis, tenant scope, strong-auth obrigatório,
permissões do AION e planos de convite/revogação. Faltava a fronteira entre esse
contrato lógico e um futuro identity/session provider real.

## Problema

Sem binding explícito, uma conta compartilhada, MFA fraco, registry não
persistido ou sessão não revogada pode contornar o RBAC mesmo que a lógica
aplicacional esteja correta.

## Alternativas consideradas

1. Tratar o RBAC lógico como suficiente para produção.
2. Permitir provisionamento direto pelo AION.
3. Exigir evidência externa de conta individual, MFA forte, persistência com
   read-back e revogação comprovável antes de revisão administrativa.

## Decisão

Adotar a alternativa 3.

### Conta individual

A evidência precisa:
- casar exatamente com o username do plano de convite;
- apontar provider_ref e account_ref;
- confirmar conta individual;
- confirmar ausência de conta compartilhada;
- confirmar conta ativa;
- conter timestamp.

### MFA forte

Fatores aceitos nesta camada:
- PASSKEY;
- SECURITY_KEY;
- TOTP.

SMS não é tratado como fator forte neste contrato.

### Registry

Persistência exige:
- registry auditado pelo RBAC;
- storage_ref;
- revision sequencial;
- digest anterior;
- read-back verificado;
- digest do read-back igual ao digest canônico do registry.

### Revogação

A conclusão de revogação exige evidência de:
- conta desabilitada;
- sessões revogadas;
- membership inativo no registry;
- read-back do registry.

## Consequências

O AION pode validar evidência de infraestrutura real e preparar revisão
administrativa, mas não ganha autoridade para criar ou remover acesso.

O máximo automático é
`READY_FOR_ADMIN_TEAM_ACCESS_ACTIVATION_REVIEW`.

## Segurança

Esta camada não:
- cria conta;
- envia convite;
- recebe senha;
- habilita MFA;
- grava registry;
- revoga sessão;
- desabilita conta;
- muda perfil;
- amplia tenant scope;
- deploya;
- ativa runtime.

## Compatibilidade

Complementa ADR-0048 e reutiliza
`atlasquant_aion_business_team_access_rbac.py`.

## Rollback/migração

Read-only. Remoção não altera contas, sessões ou registry externos.

## PR/commit relacionado

Draft PR AION BUSINESS Team Access Production Binding V1.

## Supersedes

Nenhum.

## Superseded by

Nenhum.
