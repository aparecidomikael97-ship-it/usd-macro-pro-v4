# AION BUSINESS Commercial Acquisition & Client Journey Demo V1

Schema: `ATLASQUANT_AION_BUSINESS_COMMERCIAL_ACQUISITION_DEMO_V1`

## Objetivo

Fechar o trâmite comercial completo em modo demo:

**encontrar empresas → divulgar → captar lead → qualificar → diagnosticar → propor → revisar contrato → onboarding → Portal do Cliente.**

## Onde buscar empresas

Canais iniciais:

- site / landing page;
- conteúdo em redes sociais;
- indicações;
- prospecção local;
- parceiros;
- eventos e comunidades.

A versão demo apenas organiza os canais. Não raspa contatos e não dispara mensagem.

## Site / Landing Page

A página deve explicar:

1. o problema;
2. como funciona;
3. o que o cliente recebe;
4. o Radar / Portal;
5. perguntas frequentes;
6. CTA para **Solicitar diagnóstico**.

O site não promete aumento de vendas ou lucro.

## Qualificação

O lead é avaliado por:

- aderência do problema;
- urgência;
- aderência a receita recorrente;
- acesso ao decisor;
- prontidão dos dados.

Qualificação nunca envia contato automaticamente.

## Abordagem

O sistema pode gerar um rascunho, mas:

- `sent=false`;
- revisão humana obrigatória;
- `DO_NOT_CONTACT` bloqueia o fluxo;
- permissão/opt-in precisa ser respeitado no runtime futuro.

## Contrato

Fluxo:

diagnóstico → proposta draft → revisão de escopo → revisão LGPD/privacidade →
SLA → condições comerciais → assinatura → cobrança → onboarding.

Nesta versão:

- assinatura não ocorre;
- invoice não é emitida;
- pagamento não é coletado;
- Portal do Cliente fica `TO_PROVISION_AFTER_APPROVED_ONBOARDING`.

## Conteúdo

O plano editorial pode conter:

- educativo;
- demo;
- FAQ;
- problema/solução;
- case study somente quando verificado.

Todo conteúdo nasce em DRAFT e exige aprovação antes de publicação.

## Segurança

Nada é enviado, publicado, assinado, cobrado ou provisionado automaticamente.
