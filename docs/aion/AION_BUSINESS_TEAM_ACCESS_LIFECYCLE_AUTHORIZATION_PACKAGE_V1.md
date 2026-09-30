# AION BUSINESS — Equipe & Acessos · Lifecycle Authorization Package V1

## Objetivo

Prender a autorização explícita ao plano materializado exato.

## Entrada

1. materialization JSON no estado:

    READY_FOR_ADMIN_TEAM_ACCESS_SANDBOX_LIFECYCLE_PLAN_REVIEW

2. authorization record preenchido a partir de:

    lifecycle-materialized-authorization-record.template.json

## Validação local

    python validate_team_access_lifecycle_authorization_package.py <materialization.json> <authorization-record.json> --output <authorization-package.json>

## Binding

O package verifica:
- materialization digest;
- plan digest;
- baseline digest;
- baseline acceptance record digest;
- operator session id;
- authorization record digest;
- administrador e timestamp.

## Downstream

Ledger e Step Gate rejeitam autorização sem materialization binding e package
digest íntegro.

## Estado máximo

EXPLICIT_SANDBOX_LIFECYCLE_AUTHORIZATION_RECORD_VERIFIED

Nenhum step é executado pelo CLI ou por esta camada.
