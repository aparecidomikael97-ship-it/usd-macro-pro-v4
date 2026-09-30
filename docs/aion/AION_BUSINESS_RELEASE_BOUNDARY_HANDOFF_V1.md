# AION BUSINESS Release Boundary Handoff V1

Schema: `ATLASQUANT_AION_BUSINESS_RELEASE_BOUNDARY_HANDOFF_V1`

## Objetivo

Preparar o dossiê que separa três fatos:

1. consolidação técnica reconhecida;
2. decisão de deploy;
3. decisão de ativação de runtime.

Nenhum deles implica automaticamente o seguinte.

## Pré-condição

O handoff só pode avançar quando existir um acknowledgement técnico válido:

`TECHNICAL_CONSOLIDATION_ACKNOWLEDGED`

## Itens obrigatórios

- acknowledgement técnico válido;
- SHA final da main;
- digest do acknowledgement;
- ambiente alvo;
- referência do plano de deploy;
- SHA de rollback;
- referência do plano de monitoramento;
- BUSINESS runtime OFF antes do deploy;
- decisão de runtime explicitamente separada.

## Estado máximo

`READY_FOR_SEPARATE_DEPLOY_DECISION`

Esse estado não autoriza e não executa deploy.

## Decisão futura de deploy

O request usa token explícito:

`AUTHORIZE_BUSINESS_DEPLOY_ONLY`

Acknowledgements obrigatórios incluem:

- deploy não ativa runtime;
- runtime permanece OFF após deploy;
- ativação de runtime exige nova decisão explícita;
- rollback está disponível;
- monitoramento está disponível;
- nenhuma ação com cliente real é implícita.

## Segurança

Mesmo com handoff pronto:

- deploy autorizado = false;
- deploy executado = false;
- runtime autorizado = false;
- runtime ativado = false;
- cliente real autorizado = false.

Este módulo não executa GitHub, deploy, rollback, publicação ou runtime.
