# AION BUSINESS Sandbox Harness V1

Schema: `ATLASQUANT_AION_BUSINESS_SANDBOX_HARNESS_V1`

## Objetivo

Exercitar o comportamento do Business Expert em ambiente puramente simulado,
sem transformar sandbox em runtime produtivo.

## Casos suportados

- `FAQ_DRAFT`: rascunho de resposta usando somente fatos aprovados no fixture;
- `LEAD_QUALIFICATION`: qualificação determinística de lead;
- `FOLLOWUP_DRAFT`: rascunho de follow-up que nunca é enviado;
- `BUSINESS_RADAR`: leitura simples de gargalos de atendimento/vendas.

## Requisitos de sessão

A sessão só abre quando recebe um posture `SANDBOX_READY` válido, com:

- runtime desligado;
- produção não autorizada;
- tenant, workspace, actor e session identificados.

Cada sessão recebe digest próprio para evitar mistura silenciosa de contexto.

## Limites

Máximo de 20 casos por lote. Casos desconhecidos falham fechados.

Ações proibidas incluem contato externo, contrato, pagamento/cobrança, gasto,
publicação, deploy, trading real e movimentação de dinheiro.

## Sem efeitos externos

O harness:

- não chama provider;
- não usa rede;
- não escreve externamente;
- não ativa runtime;
- não envia mensagens;
- não cobra;
- não publica;
- não faz deploy;
- não opera trading real.

Ele serve para teste, demonstração interna e treinamento antes de qualquer gate
operacional futuro.
