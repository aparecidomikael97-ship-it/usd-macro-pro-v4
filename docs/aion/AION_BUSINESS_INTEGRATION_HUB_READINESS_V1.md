# AION BUSINESS Integration Hub Readiness V1

Schema: `ATLASQUANT_AION_BUSINESS_INTEGRATION_HUB_READINESS_V1`

## Objetivo

Organizar, antes de qualquer conexão real, o Hub de Integrações da aba Negócios.

Integrações previstas:

- WhatsApp Business;
- e-mail;
- formulários;
- calendário;
- CRM;
- pagamentos;
- redes sociais;
- analytics.

## Princípio

**Least privilege.**

Ter uma integração configurada não significa ter autorização para enviar,
publicar, cobrar, excluir ou administrar contas.

## Estados

- NOT_CONFIGURED
- CONFIGURED_DEMO
- READY_FOR_AUTH_REVIEW
- HEALTHY_READ_ONLY_DEMO
- DEGRADED_DEMO
- BLOCKED

## Escopos

O Hub diferencia:

- READ_ONLY
- DRAFT_ONLY
- FUTURE_APPROVAL_REQUIRED
- PROHIBITED_IN_DEMO

Exemplos:

- WhatsApp: ler entrada e preparar rascunho; envio requer aprovação futura.
- E-mail: ler e rascunhar; envio requer aprovação futura.
- Pagamentos: leitura de status pode ser futura; charge/refund são proibidos no demo.
- Redes sociais: métricas e draft; publicação requer aprovação futura.

## Credenciais

O demo aplica:

`NO_RAW_SECRETS_IN_DEMO`

Portanto:

- não pede senha/token/chave real;
- não registra segredo em log;
- não salva segredo em checkpoint;
- não salva segredo em UI/session state;
- produção futura exige secret store dedicado, rotação e menor privilégio.

## Saúde

O Hub pode representar saúde read-only usando evidência de check, frescor e
estado de configuração. Nesta versão nenhum probe real de fornecedor ocorre.

## Pedido de conexão

O máximo permitido é um packet:

`AUTH_REVIEW_REQUIRED`

Esse packet:

- não executa OAuth;
- não armazena credencial;
- não concede write scope;
- não liga runtime.

## Segurança

Nenhuma conexão externa real existe nesta versão.
