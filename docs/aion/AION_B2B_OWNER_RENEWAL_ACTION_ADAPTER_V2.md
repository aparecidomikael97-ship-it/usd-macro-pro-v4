# AION B2B — Adapter V2 reconciliado com Command Plan V2

Status: **Draft / sintético / offline / zero execução real**.

Esta camada preserva integralmente a entrega verde da Draft PR #874 e adiciona
uma ponte hardenizada para o Command Plan V2 do Red Team.

## Mudança principal

A API pública V2 não recebe `trusted_scope`.

O scope vem do registro de execução persistido e é reconstruído pelo Command
Plan V2. O adapter, dry-run e receipt V2 só aceitam essa cadeia reconstruída.

O binding V2 inclui também:

- `execution_request_digest`;
- `command_plan_digest` V2;
- provenance `PERSISTED_EXECUTION_RECORD`;
- provenance `DERIVED_FROM_ACTION_FAMILY`.

## O que continua igual ao V1 do Codex

- ambiente exclusivamente sintético;
- adapter class offline;
- FinOps máximo de R$200/mês;
- rollback apenas de staging pré-execução;
- dry-run sem provider;
- receipts exclusivamente sintéticos;
- zero endpoint/token/credential/payload;
- zero cobrança;
- zero contato;
- zero CRM;
- zero provisionamento;
- zero deploy;
- zero mutação de produção;
- zero comando executável.

## Compatibilidade

O V1 permanece preservado e testável como evidência da entrega original.

A cadeia V2 rejeita um command plan V1. O futuro contrato de executor deve
consumir somente o Adapter V2 reconciliado, nunca o V1 diretamente.

Estado máximo:

`READY_FOR_CONTROLLED_ACTION_ADAPTER_DRY_RUN`

seguido por:

`DRY_RUN_READY`

e, para receipt sintético:

`SYNTHETIC_RECEIPT_VALIDATED`.

Nenhum desses estados é autorização de execução.

## Hardening final G1/G2/G3/G5

Base auditada #876: `39891ca36753d34a521bb1ba13771926e6f8689a`.

G1: o V2 define `FINOPS_CAP_CENTS = 20000` próprio e valida ambientes e snapshots
por funções V2. Somente `type(cost) is int`, na faixa inclusiva 0..20000.
Bool, float, string, None, negativos e 20001 bloqueiam. Mudanças na constante ou
no validador FinOps do V1 não mudam a política V2. Nenhuma cobrança é realizada.

G2: `safe_input_v2` aplica limites do clone JSON existente e, antes de producers,
hashing, lookups ou regex semânticos, exige string exata em identidade, digest,
schema, enum e referência; dict exato/schema fechado em scope e binding.
Integers são permitidos somente nas posições declaradas do contrato (FinOps,
revision de staging/checkpoint, versão de chave e timeout). Não há coerção de
bool/int para string. Isso vale para command, adapter, snapshots, dry-run e receipt.

G3: são proibidas chaves de transporte/material `api_base`, `webhook`, `callback`,
`invoke`, `transport`, `provider_config`, `connection`, `secret_ref`, inclusive
aninhadas. A allowlist de campos/schemas e o rebuild canônico continuam a defesa
principal; campos extras inocentes também bloqueiam nos artefatos fechados.
Não são criados endpoints, configuração de provider, secrets ou referências
operacionais para um executor.

G5: os quatro módulos V1 são marcados **LEGACY / NON-EXECUTABLE** por docstring,
sem mudança funcional ou remoção de testes. Servem a evidência histórica e a
compatibilidade. Nenhum futuro executor poderá consumi-los. O contrato futuro
schema-only declara explicitamente os schemas command/adapter/dry-run/receipt V2
e `legacy_v1_allowed=False`. Os validadores V2 rejeitam artefatos V1. Não foi
criado executor ou uma nova autoridade de execução.

Receipt: permanece exclusivamente sintético; `execution_request_digest` integra
o binding e o owner-intent reference digest. Troca, inclusive rehash, bloqueia.
`actual_receipt_generated`, `execution_verified`, `provider_identity_authenticated`
e `writer_identity_authenticated` permanecem false também no resultado bloqueado.
Digest é binding, não assinatura; resultados upstream continuam inputs do host
confiável, não claims arbitrários de cliente. A camada não reautentica upstream,
não cria receipt real, não persiste replay/idempotência e não prova rollback real.

Testes focais: `test_atlasquant_aion_b2b_v2_final_hardening.py`. A reprodução antes
do patch registrou 67 falhas/41 passes; não eram 67 execuções indevidas, mas gaps
de guard/preprocessamento/declaratividade comprovados com spies e assertions.
Depois: 119 casos focais + 26 V2 originais + 244 V1 originais = 389 passes,
12 subtests. Todos os testes antigos intactos. Instrumentação cobre filesystem
read/write/rename/replace/delete, sockets, subprocess, checkpoint append e criação
de journal/nonce stores, com zero tentativas durante toda a cadeia nova.
Imports, fixtures e ferramentas de Git/CI não fazem parte do runtime offline.

Gates: dedicado V2, Quality e B2B readiness incluem a suíte focal; anchors foram
confirmados únicos. Requirements/pins de crypto preservados. Resultados Linux
no head final e links dos dois Drafts serão registrados no relatório de entrega.

**merge=false; deploy=false; provider_call=false; network_effect=false;
billing=false; customer_contact=false; crm_write=false;
production_mutation=false; executable_command=false.**
