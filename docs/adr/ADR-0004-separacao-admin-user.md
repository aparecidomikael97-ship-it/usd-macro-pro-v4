# ADR-0004 — Separação ADMIN e USER

- Título: Separação ADMIN e USER
- Data: 2026-09-29
- Status: ACCEPTED

## Contexto

O checkpoint de 27/09 restringe o cliente comercial ao AtlasQuant Trade. ARCHITECTURE.md afirma que Admin, Developer e Studio não são expostos a USER e que autorização não mora só na UI.

## Problema

Esconder um menu pode ser confundido com controle de acesso.

## Alternativas consideradas

Separação apenas visual foi rejeitada. A alternativa aceita é autorização no backend, com entitlement distinto de login, perfil e cobrança.

## Decisão

USER não recebe as portas de Investimentos, Negócios ou AION Core. ADMIN acessa as quatro portas. Ocultar navegação não substitui autorização.

## Consequências

A regra está aceita e o contrato de entitlements existe. A experiência completa das quatro portas não está declarada validada.

## Componentes afetados

Entitlements, papéis USER/SALES/ADMIN e a Central do ecossistema.

## Segurança

Pagamento ou cupom não cria acesso. Não há cadastro público que promova USER a ADMIN.

## Compatibilidade

Papéis já registrados permanecem. SALES não vira ADMIN por esta ADR.

## Rollback/migração

Ampliar acesso de USER exige ADR posterior e não a exclusão deste.

## PR/commit relacionado

Nenhum PR deste registro é citado como prova de produção. Evidência por caminho de arquivo, sem SHA de deploy.

## Supersedes

Nenhum.

## Superseded by

Nenhum.
