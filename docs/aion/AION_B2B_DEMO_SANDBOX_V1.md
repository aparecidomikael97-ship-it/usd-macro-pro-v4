# AION B2B Demo / Sandbox V1

## Objetivo

Criar uma fronteira de demonstração segura entre a cadeia comercial B2B e qualquer futura implantação real.

O módulo `atlasquant_aion_b2b_demo_sandbox.py` é **puramente offline e determinístico**. Ele avalia um pacote de demonstração sintética e, no máximo, produz um candidato para revisão humana.

## Pré-condição

A entrada precisa vir de uma admissão multiempresa limpa:

- `schema = ATLASQUANT_AION_B2B_MULTI_COMPANY_ADMISSION_V1`;
- `state = REVIEWABLE`;
- `decision = TENANT_ADMISSION_REVIEW_CANDIDATE`;
- sem blockers/review reasons;
- todos os campos de autoridade/mutação permanecem `false`.

Isso **não** significa que o tenant foi criado. Significa apenas que a proposta comercial/capacidade chegou a um ponto revisável.

## Contrato do sandbox

O pedido deve:

- estar no mesmo owner/tenant/workspace;
- usar um `sandbox_id` válido;
- manter o mesmo customer, service tenant e package da admissão;
- declarar `dataset_class = SYNTHETIC`;
- declarar explicitamente:
  - sem dados reais do cliente;
  - sem segredo de produção;
  - sem integração live;
  - sem canal outbound;
  - sem provider externo;
- respeitar limites de duração, registros sintéticos e sessões concorrentes;
- apontar para um roteiro de demo revisado;
- carregar evidências suficientes.

## Política

A política é scope-bound e precisa estar `VERIFIED`.

Ela define:

- duração máxima do sandbox;
- quantidade máxima de registros sintéticos;
- sessões concorrentes máximas;
- obrigação de dados sintéticos;
- proibição de credenciais de produção;
- proibição de integrações live;
- proibição de canais outbound.

Os próprios limites da política são bounded para impedir que um arquivo de política vire um bypass.

## Estados

### REVIEWABLE

Máximo positivo:

`SANDBOX_REVIEW_CANDIDATE`

Esse estado exige revisão humana e **não concede autoridade de criação**.

### BLOCKED

Qualquer quebra de escopo, evidência, política, limite ou isolamento falha fechado.

## Fronteira de segurança

Sempre permanecem `false`:

- `sandbox_creation_authorized`;
- `tenant_creation_authorized`;
- `quota_change_authorized`;
- `credential_use_authorized`;
- `live_integration_authorized`;
- `customer_data_use_authorized`;
- `outbound_contact_authorized`;
- `billing_authorized`;
- `automatic_sandbox_creation`;
- `automatic_tenant_creation`;
- `automatic_quota_change`;
- `automatic_billing`;
- `automatic_provisioning`;
- `automatic_customer_contact`;
- `automatic_deploy`;
- `crm_write`;
- `provider_called`;
- `production_mutation`;
- `executes_action`.

## Não implementado / não autorizado

Este bloco não:

- cria infraestrutura;
- cria tenant;
- altera quota;
- copia dados reais;
- usa chaves/secrets de produção;
- conecta WhatsApp/e-mail/CRM;
- chama TTS/LLM/provider externo;
- provisiona;
- cobra;
- publica;
- faz deploy;
- ativa piloto;
- altera produção.

## Papel na cadeia B2B

`Value Realization -> Multi-Company Admission -> Demo/Sandbox Review Candidate -> HUMAN_OWNER`

Uma futura implementação real de sandbox deverá ficar em outra fronteira, com aprovação explícita, provider/infra próprios e evidência de isolamento. Este V1 não cruza essa linha.
