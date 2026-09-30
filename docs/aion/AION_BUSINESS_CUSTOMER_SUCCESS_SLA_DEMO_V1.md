# AION BUSINESS Customer Success + SLA Demo V1

Schema: `ATLASQUANT_AION_BUSINESS_CUSTOMER_SUCCESS_SLA_DEMO_V1`

## Objetivo

Ensinar e demonstrar o acompanhamento após a implantação: saúde do cliente,
adoção, suporte, SLA, renovação e expansão.

## Health Score

O demo calcula um health score apenas com sinais fictícios informados na sessão:

- uso do serviço;
- progresso dos objetivos;
- satisfação;
- atividade recente;
- chamados/incidentes;
- onboarding;
- revisão mensal;
- estado comercial fictício;
- proximidade da renovação.

O score não representa cliente real.

## Customer Success

Quando a saúde está ruim, o sistema prioriza:

- adoção;
- resolução de incidentes;
- revisão de objetivos;
- conclusão de onboarding;
- feedback;
- acompanhamento.

Upsell não vem antes da saúde.

## SLA / Suporte

O demo possui prioridades P1–P4 e metas de resposta didáticas.

Chamados são somente simulados. Nenhum ticket é enviado para sistema externo.

## Renovação

Entrar na janela de renovação produz apenas `REVIEW_REQUIRED`.

Renovação nunca é automática e não é autorizada pelo demo.

## Expansão

Oportunidade de expansão só aparece para revisão humana quando o exercício mostra
cliente saudável, bom uso, progresso de objetivos e satisfação.

Mesmo assim, `automatic_upsell=false`.

## Segurança

O módulo:

- não contata cliente;
- não abre ticket real;
- não renova contrato;
- não cobra;
- não publica;
- não faz deploy;
- não ativa runtime.
