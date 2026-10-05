# AION B2B Demo Sandbox Read Model V1

Status: **staging / Admin read-only / synthetic only**.

## Objetivo

Projetar o resultado governado do Demo/Sandbox na interface Negócios -> Sandbox
sem carregar autoridade de criação e sem expor identidade do cliente ou detalhes
sensíveis de infraestrutura.

## Fonte aceita

A projeção aceita somente:

- ATLASQUANT_AION_B2B_DEMO_SANDBOX_V1;
- state = REVIEWABLE;
- decision = SANDBOX_REVIEW_CANDIDATE;
- dataset_class = SYNTHETIC;
- sem blockers;
- revisão humana obrigatória;
- todos os campos de autoridade e execução em false.

## Exibido no Admin

A interface pode mostrar:

- sandbox ID;
- service tenant de referência;
- pacote;
- classe de dados sintética;
- duração limitada;
- quantidade de registros sintéticos;
- sessões concorrentes;
- status de revisão.

## Oculto por design

A projeção não publica:

- customer_id;
- identidade de outros clientes;
- evidence refs;
- detalhes de credenciais;
- secrets;
- provider;
- dados reais;
- controles de criação;
- controles de quota;
- controles de provisionamento;
- controles de cobrança;
- controles de contato.

## Verdade visual

A tela deve declarar:

DEMO / SANDBOX · SOMENTE LEITURA · DADOS SINTÉTICOS · SEM INTEGRAÇÃO LIVE

e manter o status global:

EXECUÇÃO = BLOQUEADA.

## Fronteira

Sempre:

- read_only = true;
- synthetic_only = true;
- customer_identity_exposed = false;
- evidence_internals_exposed = false;
- credential_details_exposed = false;
- provider_details_exposed = false;
- sandbox_creation_control_exposed = false;
- tenant_creation_control_exposed = false;
- quota_control_exposed = false;
- provisioning_control_exposed = false;
- billing_control_exposed = false;
- customer_contact_control_exposed = false;
- grants_authority = false;
- executes_action = false.

Esse read model não cria sandbox e não é autorização para implantação real.
