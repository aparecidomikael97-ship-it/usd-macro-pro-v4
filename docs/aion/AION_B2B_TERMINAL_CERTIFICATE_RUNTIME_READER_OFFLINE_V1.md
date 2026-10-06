# AION B2B — Terminal Certificate Runtime Reader Offline V1

Status: **offline-only / read-only / fail-closed / Draft**.

## Objetivo

Conectar o Runtime Reader ao `DurableExecutionStore` já estendido, sem provider,
rede, banco paralelo ou autoridade operacional.

O leitor recebe uma instância já autorizada do store e não recebe caminho de
arquivo/banco.

## Estados

- `VERIFIED`
- `MISMATCH`
- `UNAVAILABLE`
- `STALE`

## Freshness

O caller fornece `observed_at` e uma política `max_age_seconds`.

- evidência dentro da janela: VERIFIED;
- idade acima da janela: STALE;
- relógio regressivo ou política inválida: MISMATCH.

## Escopo

Owner, tenant e workspace precisam bater exatamente.

Não existe fallback cross-tenant ou cross-workspace.

Execução legada sem scope retorna UNAVAILABLE.

## Projeção segura

O resultado expõe apenas identidade de escopo e digests/evidências já
persistidas. Não expõe payload bruto, segredo, token, private key nem resposta
bruta de provider.

## Autoridade

VERIFIED significa somente **evidência verificada e fresca**.

Não autoriza execução, retry, reopen, reconciliação, rollback, compensação,
efeito externo, billing, CRM, provisionamento ou deploy.

## Limite

Esta camada só opera com SQLite temporário nos testes e com o store passado pelo
caller. Não existe integração com banco de produção nesta etapa.
