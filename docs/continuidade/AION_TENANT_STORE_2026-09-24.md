# AtlasQuant — AION pessoal — contrato de persistência por tenant — 2026-09-24

## Objetivo

Preparar a persistência futura da memória do **Meu AION** sem realizar nenhuma escrita externa nesta fase.

O contrato existe para impedir quatro classes de erro:

- salvar memória do cliente na branch de código;
- misturar memória de dois assinantes;
- sobrescrever uma versão mais nova silenciosamente;
- salvar sem entitlement confirmado e aprovação explícita.

## Estado desta fase

**Não há I/O de rede neste módulo.**

Ele somente prepara e valida planos de leitura/escrita.

Campos de verdade:

- `network_io_implemented=false`
- `automatic_write=false`
- `automatic_overwrite=false`

## Destino

Cada usuário elegível recebe um target:

`branch = atlasquant-runtime` (ou outra branch de runtime válida)

`path = dados/aion/tenants/<tenant-id>/checkpoint.json`

Branches de código como `main` e `atlasquant-dev` são recusadas.

## Requisitos para leitura

O plano de leitura só fica permitido quando:

1. sessão USER/SALES autenticada é válida;
2. namespace do tenant é válido;
3. entitlement `AION_PERSONAL` está efetivo e confirmado;
4. branch de runtime é segura.

Mesmo permitido, o contrato retorna:

`executes_read=false`

A conexão real será outra etapa.

## Requisitos para escrita

Além das condições da leitura, é obrigatório:

`approved=true`

Sem aprovação explícita:

`EXPLICIT_WRITE_APPROVAL_REQUIRED`

Mesmo com aprovação:

`executes_write=false`

Ou seja, nesta fase é apenas um plano de escrita validado.

Se o payload recebido trouxer um `tenant_id` diferente da sessão:

`FOREIGN_TENANT_MEMORY_REJECTED`

O sistema não converte silenciosamente essa memória em memória do usuário atual.

## Concorrência

Toda integração futura deverá usar revisão/sha esperado.

Se:

`expected_revision != current_revision`

o resultado é:

`REVISION_CONFLICT`

`requires_reload=true`

`automatic_overwrite=false`

O AION nunca deve sobrescrever memória nova silenciosamente.

## Memória estrangeira

Se um payload carregado tiver `tenant_id` diferente da sessão:

`FOREIGN_TENANT_MEMORY_REJECTED`

Não há merge, fallback ou tentativa de reaproveitamento.

## Limite

Memória pessoal normalizada possui limite de:

`256000 bytes`

Payload maior é bloqueado antes de qualquer futura chamada externa.

## Separação

O contrato não altera:

- cadastro de contas;
- papel USER/SALES/ADMIN;
- cobrança;
- promoção;
- entitlement;
- trading;
- memória ADMIN;
- documentos privados do projeto.

## Próxima etapa futura

Depois de validação deste contrato:

1. criar um conector de runtime que use exatamente esse target;
2. aplicar `expected_revision` no write real;
3. exigir confirmação explícita no fluxo de persistência;
4. registrar auditoria de save/reload;
5. testar revogação do entitlement;
6. só então ligar o shell visual do Meu AION.

## Regra da verdade

- contrato de persistência: IMPLEMENTADO EM CÓDIGO;
- escrita externa: NÃO IMPLEMENTADA;
- leitura externa: NÃO IMPLEMENTADA;
- memória pessoal em produção: NÃO CONFIRMADA;
- sobrescrita automática: BLOQUEADA;
- cross-tenant: BLOQUEADO;
- branch de código para memória: BLOQUEADA;
- trading real: BLOQUEADO.
