# AION Negócios — Commercial Portfolio V1

Visão administrativa multiempresa, **read-only**, construída sobre o Commercial Golden Path V1.

## Objetivo

O portfólio ajuda o administrador a enxergar rapidamente:

- em que etapa cada empresa está;
- quais empresas estão bloqueadas ou com gaps de linhagem;
- pacote comercial resumido;
- estado de assinatura/serviço;
- sinal de pagamento/inadimplência;
- estado de valor/ROI;
- saúde do cliente;
- pressão de capacidade/quota;
- qual empresa merece atenção humana primeiro.

Ele é um painel de decisão humana. Não é executor.

## Identidade mínima

Cada empresa entra apenas com um company_ref opaco.

O portfólio não precisa de nome da empresa, nome do contato, telefone, e-mail, endereço, tenant id, dados bancários, valor de cobrança ou dados brutos do cliente.

## Golden Path

O portfólio recebe um Golden Path já validado por empresa e mantém estado da jornada, etapa atual, próxima ação humana, quantidade de gaps de linhagem e digest de evidência da jornada.

A fila continua priorizando a severidade da jornada: BLOCKED, READY_WITH_GAPS, READY e EMPTY. Dentro da mesma classe, sinais administrativos de risco sobem primeiro.

## Resumo administrativo seguro

O campo opcional admin_summary aceita somente: package, subscription_state, payment_state, value_state, observed_roi_pct, health_state, health_score, capacity_utilization_pct e source_evidence_digest.

Qualquer campo extra faz o item falhar fechado. Isso impede que PII, valor de cobrança ou objetos brutos sejam empurrados para o portfólio.

### Pacote

Vocabulário: ESSENCIAL, PROFISSIONAL, COMPLETO; UNASSIGNED quando ainda não há pacote validado.

### Assinatura / ciclo de vida

Vocabulário alinhado ao portal: ACTIVE, PENDING, PAUSED, CANCELLED, NOT_APPLICABLE e UNKNOWN quando o resumo ainda não existe.

### Pagamento / inadimplência

O portfólio guarda apenas PAID, DUE, OVERDUE, NOT_APPLICABLE ou UNKNOWN e deriva CLEAR, DUE, OVERDUE, NOT_APPLICABLE ou UNKNOWN.

Nenhum amount_due_brl, link de pagamento, cartão, conta bancária ou detalhe financeiro bruto é aceito.

### Valor / ROI

Estados aceitos: STRONG_VALUE, VALUE_CONFIRMED, VALUE_AT_RISK, LOW_VALUE e UNKNOWN. observed_roi_pct pode ser mostrado apenas como número agregado já validado pela origem.

### Saúde

Estados alinhados ao ciclo recorrente seguro: HEALTHY, REMEDIATION, CAPACITY_HOLD, INCIDENT_REVIEW e UNKNOWN. health_score, quando presente, precisa estar entre 0 e 100.

### Capacidade

O portfólio recebe apenas capacity_utilization_pct entre 0 e 100 e deriva: abaixo de 70% = NORMAL; de 70% a menos de 90% = WATCH; 90% ou mais = PRESSURE; sem evidência = UNKNOWN.

Isso é somente um sinal de atenção. Não aumenta quota automaticamente.

## Fila de atenção humana

Dentro da mesma prioridade de jornada, o portfólio aumenta a atenção para pagamento vencido, pressão de capacidade, incidente, baixo valor, valor em risco, remediação, assinatura pausada e pagamento a vencer.

Nenhum desses sinais executa contato, cobrança ou mudança de contrato.

## Contagens administrativas

A saída consolida, sem PII: state_counts, stage_counts, package_counts, subscription_counts, payment_counts, value_state_counts, health_state_counts, capacity_state_counts, delinquency_counts e admin_summary_coverage_count.

## Proveniência

Quando admin_summary é informado, source_evidence_digest é obrigatório e deve ser SHA-256 canônico no formato sha256:<64 hex>.

O portfólio não declara uma informação administrativa como válida sem evidência resumida vinculada.

## Limites

- máximo de 200 empresas por portfólio;
- fila de atenção limitada a 50;
- somente company_ref opaco;
- sem cross-tenant data;
- sem dados brutos;
- sem ações automáticas.

## Privacidade e autoridade

O resultado mantém explicitamente read_only=true, company_ref_only=true, admin_summary_only=true, tenant_identity_exposed=false, contact_data_exposed=false, raw_customer_data_exposed=false, raw_payment_data_exposed=false, payment_amount_exposed=false, banking_data_exposed=false, crm_write=false, automatic_outreach=false, automatic_followup=false, automatic_stage_change=false, automatic_billing=false, automatic_activation=false, automatic_package_change=false, automatic_quota_change=false, production_mutation=false, grants_authority=false e executes_action=false.

## O que este V1 não faz

Não executa CRM, outreach, follow-up, cobrança, alteração de pacote, aumento de quota, ativação, contrato, deploy, merge ou Global Worker.

É um painel administrativo de decisão humana, não um executor.
