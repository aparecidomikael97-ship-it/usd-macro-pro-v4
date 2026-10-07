# AION B2B — Durable Store Extension Offline V1

Status: **implementation on isolated Draft branch / offline-only / no deploy**.

## Implementado

O `DurableExecutionStore` recebeu uma migração aditiva, no mesmo SQLite, com
schema version `2` e quatro tabelas de evidência terminal:

- `execution_scope_bindings`;
- `execution_terminal_finalizations`;
- `execution_audit_seals`;
- `execution_terminal_certificates`.

A tabela `executions` existente permanece intacta como fonte da identidade da
execução.

## APIs adicionadas

- `store_schema_version`;
- `bind_execution_scope_once` / `get_execution_scope`;
- `persist_terminal_finalization_once` / `get_terminal_finalization`;
- `persist_audit_seal_once` / `get_audit_seal`;
- `persist_terminal_certificate_once` / `get_terminal_certificate`;
- `read_terminal_certificate_snapshot`.

## Regras de segurança

- mesmo banco do kernel;
- foreign keys;
- migração transacional;
- append-only;
- replay idempotente para o mesmo registro;
- digest divergente vira conflito;
- scope owner/tenant/workspace é bind único e imutável;
- execução legada sem scope permanece `UNAVAILABLE`;
- cross-tenant/workspace retorna `MISMATCH`;
- finalization exige execução terminal;
- audit seal exige finalization coerente;
- certificate exige scope + finalization + seal coerentes;
- reopen preserva a cadeia;
- todas as leituras continuam `executes_action=False`.

## Limite desta etapa

Esta implementação é exercitada somente em arquivos SQLite temporários de teste.
Não há merge, deploy, migração de banco real, provider, rede, billing, CRM ou
mutação de produção.

O Runtime Reader de produção continua desacoplado até certificação específica
desta implementação.
