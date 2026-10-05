# AION B2B — Owner Renewal Action Execution Preflight V1

Status: **staging / eligibility only / no command / no execution**.

## Objetivo

Criar o último gate puro antes de uma futura cerimônia de execução da ação
comercial recorrente.

O gate exige simultaneamente:

- autorização do proprietário persistida e atestada;
- decisão persistida = AUTHORIZE_BUSINESS_ACTION;
- checkpoint writer criptograficamente atestado;
- preflight original de autorização intacto;
- fotografia operacional nova, com no máximo 120 segundos.

## Fotografia operacional obrigatória

O ambiente precisa comprovar:

- isolamento do tenant;
- contrato fresco e com o mesmo digest;
- saúde do serviço fresca;
- SLA fresco;
- FinOps fresco;
- capacidade fresca;
- suporte fresco;
- rollback/reversão pronto;
- receipts de auditoria;
- chave de idempotência;
- lock exclusivo da ação;
- projeção customer-safe pronta;
- kill switch pronto;
- dry-run aprovado;
- nenhum incidente de segurança ou privacidade;
- nenhum scope breach;
- nenhum provider/rollback degradado;
- nenhum conflito contratual;
- nenhuma disputa de cobrança não resolvida;
- capacidade reservada dentro da disponível;
- infraestrutura projetada dentro do teto global de R$200;
- pelo menos oito referências de evidência;
- digests explícitos dos parâmetros da ação, saúde, SLA, FinOps, capacidade,
  suporte, segurança e projeção customer-safe.

## Pré-condições por ação

Renovação, renovação com mudanças, não renovação, remediação, rescope de
capacidade, repricing, remediação de incidente, pausa e encerramento possuem
pré-condições próprias e independentes.

## Resultado máximo

`READY_FOR_BUSINESS_ACTION_EXECUTION_CEREMONY`.

Mesmo nesse estado:

- business_action_execution_ceremony_eligible=true;
- human_execution_confirmation_required=true;
- execution_request_issued=false;
- owner_execution_signature_verified=false;
- execution_command_generated=false;
- execution_command_executed=false;
- business_action_authorized=false;
- todas as autoridades comerciais e operacionais continuam false.

Portanto, o preflight não executa nada. Ele apenas permite preparar uma futura
cerimônia final, que deverá assinar o action-parameters digest e o
execution-preflight digest exatos.
