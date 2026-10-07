# AION B2B — Terminal Certificate Runtime Reader Offline V1

Status: **offline-only / read-only / fail-closed / Draft**.

## Objetivo

Conectar o Runtime Reader ao certificado terminal persistido sem permitir que o
reader conheça ou consulte diretamente o `DurableExecutionStore`.

A separação fica explícita:

1. o adapter físico
   `DurableTerminalCertificateReadModelSource` recebe uma instância já
   autorizada do store;
2. esse adapter produz somente uma projeção lógica segura/read-only;
3. o Runtime Reader consome exclusivamente a interface
   `read_terminal_certificate_projection(...)`.

Assim, o store permanece a fonte física de verdade e o Terminal Certificate
Read Model permanece a fonte lógica do reader.

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

## Fronteira lógica obrigatória

O Runtime Reader não importa `DurableExecutionStore`, não chama
`read_terminal_certificate_snapshot` e rejeita um store passado diretamente.

Somente uma fonte que exponha
`read_terminal_certificate_projection(...)` pode alimentar o reader.

O adapter físico é read-only, não abre um banco novo e não cria sidecar/segunda
verdade.

## Projeção segura

O resultado expõe apenas identidade de escopo e digests/evidências já
persistidas. Não expõe payload bruto, segredo, token, private key nem resposta
bruta de provider.

## Autoridade

VERIFIED significa somente **evidência verificada e fresca**.

Não autoriza execução, retry, reopen, reconciliação, rollback, compensação,
efeito externo, billing, CRM, provisionamento ou deploy.

## Limite

Esta camada só opera com SQLite temporário nos testes e com um store já
autorizado injetado no adapter físico. Não existe integração com banco de
produção nesta etapa.
