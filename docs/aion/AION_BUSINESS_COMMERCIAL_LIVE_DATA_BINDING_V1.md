# AION BUSINESS — Commercial Live Data Binding V1

## Objetivo

Permitir que o pipeline comercial use dados reais vindos de connectors sem
dar poder de escrita ao AION.

## Fontes previstas

- CRM
- Forms
- Email
- Calendar
- Payments
- Analytics

## Source attestation

Antes de aceitar um snapshot, a fonte precisa provar:
- autenticação já verificada;
- escopo somente leitura;
- nenhum write scope;
- nenhuma credencial dentro do payload;
- timestamp da evidência;
- connection reference.

Este módulo não executa autenticação nem OAuth.

## Registro comercial

Cada registro usa referências, não PII bruta:
- tenant_id
- source
- record_ref
- subject_ref
- source_ref
- stage
- contact_permission_state
- observed_at
- estimated_value_brl opcional
- source_confidence_pct opcional

Campos como email, telefone, nome completo, token, API key, senha, cartão e CVV
são rejeitados nesta fronteira.

## Frescor

Snapshot stale é bloqueado. O limite padrão é 24 horas e pode ser configurado
até o máximo bounded do contrato.

## Pipeline observado

O sistema pode mostrar:
- contagem por etapa;
- total de registros;
- quantos estão DO_NOT_CONTACT;
- valor estimado observado quando houver dado de origem.

Esse valor não é forecast nem garantia.

## Autoridade

`pipeline_auto_advance=false`

`contact_authorized=false`

`billing_authorized=false`

`external_write_authorized=false`

O máximo é revisão administrativa da configuração de leitura real.
