# AION Negócios — Commercial Golden Path V1

## Objetivo

Unificar a leitura comercial do AION Negócios sem criar uma nova autoridade de execução.

O sistema já possuía contratos separados para:

- RevOps;
- diagnóstico;
- qualificação / Pilot Readiness;
- proposta;
- planejamento do piloto;
- governança de ativação;
- valor/ROI do piloto;
- serviço gerenciado;
- portal do cliente;
- acompanhamento recorrente.

O Golden Path V1 apenas projeta esses contratos em uma única jornada operacional.

## Jornada canônica

1. Funil / RevOps
2. Diagnóstico
3. Qualificação
4. Proposta
5. Planejamento do piloto
6. Ativação do piloto
7. Valor do piloto
8. Serviço recorrente
9. Portal do cliente
10. Acompanhamento recorrente

A jornada não “move” o cliente automaticamente. Ela só lê evidência já produzida por contratos governados.

## Estados

Cada estágio pode aparecer como:

- NOT_STARTED
- FUNNEL_VISIBLE
- WAITING_HUMAN_SCORING
- WAITING_OWNER_REVIEW
- WAITING_HUMAN_REVIEW
- WAITING_OWNER_APPROVAL
- WAITING_HUMAN_EXECUTION_CONFIRMATION
- WAITING_OWNER_VALUE_REVIEW
- WAITING_OWNER_ACTIVATION
- ACTIVE_MONITORING
- CUSTOMER_SAFE_RECURRING_VIEW
- BLOCKED

O agregado geral usa:

- EMPTY
- READY
- READY_WITH_GAPS
- BLOCKED

## Regra de verdade

Evidência downstream sem etapas anteriores não é inventada nem escondida.

Exemplo: uma proposta válida sem diagnóstico carregado aparece como progresso disponível, mas o modelo marca `READY_WITH_GAPS` e lista as lacunas de linhagem.

Scope divergente, schema inválido, estado incompatível ou flag automática perigosa produzem `BLOCKED`.

## Próxima ação humana

O painel pode recomendar apenas o próximo **tipo de revisão humana**, por exemplo:

- REALIZAR_SCORE_HUMANO
- REVISAR_E_DECIDIR_PILOTO
- REVISAR_PROPOSTA_E_ESCOPO
- DECIDIR_ATIVACAO_DO_PILOTO
- CONFIRMAR_EXECUCAO_DO_PILOTO
- REVISAR_VALOR_ROI_E_RETENCAO
- DECIDIR_ATIVACAO_DO_SERVICO
- ACOMPANHAR_SLA_ROI_SAUDE_E_QUOTAS

Isso não é autorização e não executa a ação.

## Segurança

O Golden Path mantém explicitamente:

- read_only=true
- grants_authority=false
- executes_action=false
- crm_write=false
- automatic_outreach=false
- automatic_followup=false
- automatic_stage_change=false
- automatic_owner_assignment=false
- automatic_pricing=false
- automatic_proposal=false
- automatic_contract=false
- automatic_billing=false
- automatic_provisioning=false
- automatic_activation=false
- automatic_deploy=false
- provider_called=false
- production_mutation=false

Qualquer artefato que chegue com flag `automatic_*=true` é bloqueado na projeção.

## UI

Quando o read model é injetado em `atlasquant_b2b_commercial_golden_path`, a home de Negócios mostra:

- estágio atual;
- próxima ação humana;
- dez etapas;
- gaps de evidência quando existirem;
- aviso explícito de que o painel não envia, cobra, assina, ativa nem altera CRM.

Sem read model, a home continua funcionando como antes.

## Escopo desta entrega

Design/read-model/UI em Draft.

Não autoriza:

- contato externo;
- CRM write;
- proposta enviada;
- preço vinculante;
- contrato;
- cobrança;
- provisionamento;
- piloto;
- deploy;
- merge;
- Core Freeze;
- Global Worker.
