# Checkpoint Mestre — Reconciliação incremental 30/09/2026

Gate: `CHECKPOINT_MESTRE_INCREMENTAL_2026_09_30`

Este documento **complementa e não substitui**:
- `docs/continuidade/CHECKPOINT_MESTRE_RECONCILIACAO_2026-09-29.md`;
- `docs/continuidade/CHECKPOINT_MESTRE_ATLASQUANT_2026-09-22.md`.

Regra de precedência: decisões explicitamente registradas aqui em 30/09/2026
prevalecem sobre requisitos anteriores quando houver conflito direto. Histórico
antigo permanece preservado. Este checkpoint não declara produção atualizada,
não autoriza merge/deploy/runtime e não converte requisito em implementação.

O manifesto verificável desta camada está em
`docs/continuidade/checkpoint_mestre_reconciliation_2026-09-30.json`.
O ponteiro mais recente fica em
`docs/continuidade/checkpoint_mestre_latest.json`.

## 1. Regra operacional do projeto

Mikael autoriza o desenvolvimento proativo de lacunas, melhorias e proteções
necessárias ao ecossistema, sem exigir que ele lembre de cada requisito.
Ações irreversíveis, produção, deploy, merge, pagamentos, cobrança, publicação
relevante, alteração crítica de runtime, trading real e demais fronteiras de
alto impacto continuam dependendo dos gates e aprovações explícitas definidos
pelo projeto.

## 2. Modelo econômico inicial

Enquanto o ecossistema ainda não gerar lucro relevante, o teto mensal planejado
para operação do AION é de **até R$200**.

Prioridades dentro desse teto:
1. integridade e proteção de dados;
2. backup automático e cópia separada;
3. versionamento, auditoria e rollback;
4. modo econômico obrigatório;
5. modelo local ou recurso barato quando suficiente;
6. API paga somente quando agregar valor;
7. alerta e bloqueio antes de ultrapassar orçamento;
8. crescimento financiado progressivamente pela receita dos clientes.

R$200 é teto de planejamento inicial, não promessa de que qualquer volume de
uso caberá nele.

Estado do Budget Governor / FinOps: **IMPLEMENTADO / EM VALIDAÇÃO** em
`atlasquant_aion_finops_budget_governor.py`, ADR-0050 e testes associados.

Estado do ledger de custos reais: **IMPLEMENTADO / EM VALIDAÇÃO** em
`atlasquant_aion_finops_live_cost_ledger.py`, ADR-0058 e testes associados.
Custos entram somente por fonte atestada read-only e formam uma hash-chain
append-only verificável; persistência física e pagamento continuam separados.

Estado do versionamento/reconciliação: **IMPLEMENTADO / EM VALIDAÇÃO** em
`atlasquant_aion_finops_ledger_persistence_reconciliation.py`, ADR-0059 e
testes associados. Versões do ledger formam uma cadeia de manifestos e faturas
read-only podem ser reconciliadas contra o ledger sem autorizar pagamento.

Estado do binding de capacidade com métricas reais: **IMPLEMENTADO / EM VALIDAÇÃO**
em `atlasquant_aion_business_capacity_live_metrics_binding.py`, ADR-0061 e
testes associados. FinOps, suporte, infraestrutura e incidentes entram somente
como evidência read-only atestada e recente antes de alimentar o Capacity & Scale
Manager existente.

Estado do binding de produção de Equipe & Acessos: **IMPLEMENTADO / EM VALIDAÇÃO**
em `atlasquant_aion_business_team_access_production_binding.py`, ADR-0063 e
testes associados. Conta individual, MFA forte, registry persistido com read-back
e revogação comprovável passam a ser requisitos explícitos; o AION não executa
essas mutações.

Estado do sandbox E2E de Equipe & Acessos: **IMPLEMENTADO / EM VALIDAÇÃO** em
`atlasquant_aion_business_team_access_sandbox_e2e.py`, ADR-0064 e testes
associados. A stack de referência de sandbox fica Keycloak + OIDC,
PostgreSQL e adapter Keycloak Admin REST. O máximo automático é
`READY_FOR_ADMIN_TEAM_ACCESS_SANDBOX_EXIT_REVIEW`; secrets, chamadas reais,
produção, deploy e runtime continuam fora desta camada.

Estado do sandbox físico de Equipe & Acessos: **IMPLEMENTADO / EM VALIDAÇÃO**
em `atlasquant_aion_business_team_access_physical_sandbox.py`, bundle
`deploy/sandbox/team-access/`, ADR-0065 e testes associados. O ambiente fica
localhost-only, usa Keycloak 26.7.5 + PostgreSQL 18.6, mantém secrets fora do Git
e exige `-Apply` explícito para iniciar containers. Nenhum container foi
iniciado por esta camada.

Estado da evidência baseline do sandbox de Equipe & Acessos:
**IMPLEMENTADO / EM VALIDAÇÃO** em
`atlasquant_aion_business_team_access_sandbox_evidence.py`, ADR-0066 e testes
associados. A coleta é read-only, sanitizada e local; observa serviços, OIDC,
schema do registry e hashes dos artefatos sem incluir secrets. O máximo é
`READY_FOR_ADMIN_TEAM_ACCESS_SANDBOX_LIFECYCLE_TEST_REVIEW`.

Estado do plano de lifecycle do sandbox de Equipe & Acessos:
**IMPLEMENTADO / EM VALIDAÇÃO** em
`atlasquant_aion_business_team_access_sandbox_lifecycle_plan.py`, ADR-0067 e
testes associados. O plano define dez etapas manuais, exige baseline válido,
username sandbox, tenant explícito e MFA forte. O máximo é
`READY_FOR_ADMIN_TEAM_ACCESS_SANDBOX_LIFECYCLE_EXECUTION_DECISION`; nenhuma
mutação é executada ou autorizada automaticamente.

Estado da autorização formal do lifecycle sandbox:
**IMPLEMENTADO / EM VALIDAÇÃO** em
`atlasquant_aion_business_team_access_sandbox_lifecycle_authorization.py`,
ADR-0068 e testes associados. O registro futuro deve estar preso ao plan digest
e baseline digest exatos, com token e acknowledgements completos. Nenhuma
autorização real foi registrada neste bloco e o executor permanece OFF.

Estado do ledger auditável do lifecycle sandbox:
**IMPLEMENTADO / EM VALIDAÇÃO** em
`atlasquant_aion_business_team_access_sandbox_lifecycle_evidence_ledger.py`,
ADR-0069 e testes associados. O ledger aceita recibos sanitizados em cadeia
SHA-256, exige ordem 1→10, recalcula a integridade de cada receipt e rejeita
drift, duplicação ou quebra de cadeia. Nenhum step real foi executado.

Estado do step gate do lifecycle sandbox:
**IMPLEMENTADO / EM VALIDAÇÃO** em
`atlasquant_aion_business_team_access_sandbox_lifecycle_step_gate.py`,
ADR-0070 e testes associados. Cada etapa exige preflight fresco, target igual ao
next expected, baseline sem drift, saúde/OIDC/registry válidos, secrets locais,
produção ausente e cleanup pronto. O gate não executa nem faz append automático.

Estado do Windows Operator Kit de Equipe & Acessos:
**IMPLEMENTADO / EM VALIDAÇÃO** em
`atlasquant_aion_business_team_access_windows_operator_kit.py`, scripts
PowerShell locais, ADR-0071 e testes associados. Geração de secrets e start são
PLAN ONLY por padrão; gravação do env exige `-Apply`, start exige
`-ApplyStart` e baseline exige `-CollectBaseline` adicional. Nenhuma ação
real no PC foi executada por esta camada no GitHub.

Estado do binding de oportunidades com economia real: **IMPLEMENTADO / EM VALIDAÇÃO**
em `atlasquant_aion_business_revenue_live_economics_binding.py`, ADR-0062 e
testes associados. Custo mensal passa a vir do ledger FinOps verificado e
capacidade passa a vir do Capacity Manager real; preço e venda continuam
decisões administrativas separadas.

## 2.1 Prioridade entre Negócios, Trader e Investimentos

Direção aprovada:

1. Núcleo + AION + interface continuam sendo concluídos sem interrupção.
2. Depois desse fechamento estrutural, **Negócios recebe a maior prioridade** por
   ser a principal frente de geração inicial de caixa.
3. Trader e Investimentos continuam evoluindo em paralelo, com menor alocação
   de esforço enquanto Negócios é profissionalizado.
4. Trader permanece em backtest, testes, validação e gestão de risco enquanto o
   capital é formado.
5. Investimentos mantém função de construção e preservação patrimonial.

Política financeira inicial:
- receita líquida de Negócios pode financiar todo o ecossistema;
- lucro líquido do Trader permanece no bucket Trader;
- alocação inicial máxima ao Trader: 30% do capital total do ecossistema;
- metas de lucro do Trader são **metas de planejamento**, nunca promessa,
  garantia ou retorno esperado;
- nenhuma movimentação de capital é automática.

## 2.2 Índice de Independência CLT

Estado: **IMPLEMENTADO / EM VALIDAÇÃO** em
`atlasquant_aion_independence_index.py`, ADR-0056 e testes associados.

O índice usa somente entradas privadas de runtime e não grava renda pessoal no
repositório. Ele acompanha:
- renda não-Trade do ecossistema ao longo de vários meses;
- faixa de segurança definida administrativamente;
- reserva financeira;
- receita recorrente;
- concentração de clientes;
- dependência do Trade para despesas essenciais.

O score é planejamento, não probabilidade. Mesmo em
`TRANSITION_REVIEW_ZONE`, a decisão permanece humana e
`employment_exit_recommended=false`.

## 3. Monetização Business

A prioridade de geração de caixa passa a ser **serviço B2B de Atendimento &
Automação Comercial com AION**, com implantação enxuta, mensalidade recorrente,
custo medido e margem por cliente.

Primeiro produto comercial a validar:
- atendimento;
- organização/captura de leads;
- follow-up;
- agendamento;
- automações comerciais;
- relatórios simples de resultado;
- onboarding controlado.

**Dropshipping sai das prioridades atuais.** Só volta a ser avaliado se Mikael
pedir explicitamente no futuro.

Regra de crescimento: primeiro validar serviço e formar caixa; depois usar
receita para ampliar infraestrutura, IA, voz, vídeo, integrações e capacidade.

Estado da produto inicial: **IMPLEMENTADO / EM VALIDAÇÃO** em
`atlasquant_aion_business_b2b_revenue_offer.py`, ADR-0053 e testes associados.

A oferta prioritária é **AION Atendimento & Automação Comercial**, com
implantação + mensalidade recorrente. O AION calcula margem e piso sustentável
a partir de custos informados/validados e da margem mínima definida pelo
administrador; preço de mercado não é inventado automaticamente.

Estado do motor Oportunidades de Receita: **IMPLEMENTADO / EM VALIDAÇÃO** em
`atlasquant_aion_business_revenue_opportunity_engine.py`, ADR-0060 e testes
associados. O motor bloqueia oportunidades inviáveis antes do ranking e usa
score comparativo que não é probabilidade nem previsão de venda.

Estado da seleção/preço do primeiro piloto: **IMPLEMENTADO / EM VALIDAÇÃO** em
`atlasquant_aion_business_first_pilot_pricing_review.py`, ADR-0054 e testes
associados. O máximo automático é `READY_FOR_ADMIN_FIRST_PILOT_REVIEW`.

Estado do binding comercial read-only: **IMPLEMENTADO / EM VALIDAÇÃO** em
`atlasquant_aion_business_commercial_live_data_binding.py`, ADR-0057 e testes
associados. A camada aceita somente dados externos atestados e recentes, sem PII
bruta/segredos, e produz estado observado sem escrever de volta no CRM ou canais.

## 4. Equipe & Acessos

Estado da primeira camada: **IMPLEMENTADO / EM VALIDAÇÃO** em
`atlasquant_aion_business_team_access_rbac.py`, ADR-0048 e testes associados.

A área Business deve ter acesso individual por funcionário:
- convite e conta próprios;
- RBAC/perfis;
- escopo por cliente/tenant;
- autenticação forte/2FA quando disponível;
- suspensão e revogação;
- trilha de auditoria;
- princípio do menor privilégio;
- AION obedecendo exatamente às mesmas permissões da interface e dos dados.

Login administrativo de Mikael não deve ser compartilhado com funcionários.

## 5. Capacidade & Escala

Estado da primeira camada: **IMPLEMENTADO / EM VALIDAÇÃO** em
`atlasquant_aion_business_capacity_scale_manager.py`, ADR-0049 e testes associados.

O Business precisa de um **Gestor de Capacidade & Escala** ligado a:
- Central Financeira;
- quotas por tenant;
- custos de IA e integrações;
- saúde do cliente;
- suporte;
- infraestrutura;
- margem.

A fase inicial permanece limitada e controlada. O sistema deve medir capacidade
antes de admitir novos clientes e impedir que crescimento comprometa
estabilidade, suporte ou margem.

## 6. Independência do ChatGPT

O AION deve funcionar sem depender da assinatura do ChatGPT.
ChatGPT pode continuar como apoio externo opcional de arquitetura, auditoria,
pesquisa e evolução, mas não como requisito para o runtime do AION.

O objetivo futuro é permitir cooperação técnica AION ↔ ferramentas externas por
interfaces autorizadas, mantendo o administrador no controle.

## 7. Arquitetura multiagente interna

O desenho aprovado é **um AION central com oito papéis lógicos especializados**,
não oito IAs caras e independentes.

1. **AION Núcleo / Orquestrador** — coordena tarefas, políticas e agentes.
2. **Arquiteto / Estrategista** — pesquisa tecnologias, propõe evolução,
   redução de custo e melhorias.
3. **Guardião / Auditor** — segurança, permissões, compliance, risco, rollback.
4. **Executor / Operador** — realiza tarefas e integrações já autorizadas.
5. **Memória / Conhecimento** — consolida decisões, histórico, documentação e
   contexto.
6. **FinOps** — controla orçamento, custo por tenant, margem e consumo de APIs.
7. **Observabilidade / Confiabilidade** — saúde, incidentes, degradação,
   backups, recuperação e SLO/SLA.
8. **Sucesso do Cliente / Comercial** — onboarding, uso, satisfação, retenção,
   expansão e oportunidades de receita.

Esses papéis podem compartilhar modelo e infraestrutura e devem ser ativados
sob demanda para reduzir custo. Agentes especializados não ganham permissão
independente para ações críticas.

Estado do roteador dos oito papéis: **IMPLEMENTADO / EM VALIDAÇÃO** em
`atlasquant_aion_eight_role_router.py`, integrado ao runtime bridge e à visão
administrativa. O roteador mantém o Orquestrador e seleciona no máximo três
papéis adicionais por tarefa; roteamento não concede autoridade operacional.

## 7.1 Backup & Recovery

Estado da política: **IMPLEMENTADO / EM VALIDAÇÃO** em
`atlasquant_aion_backup_recovery_policy.py`, ADR-0055 e workflow de source
backup endurecido.

Regras:
- source ZIP com SHA256 verificado;
- teste de extração antes do upload;
- arquivos críticos de continuidade conferidos;
- checkpoint/runtime versionado separadamente;
- cópia secundária distinta obrigatória para conjunto completo;
- RPO/RTO definidos pelo administrador;
- restore automático proibido;
- produção fora do restore drill desta camada.

## 7.2 Global Worker · bloqueio operacional observado

Em 2026-09-30, o gate `AION Global Worker Activation Readiness` bloqueou
corretamente a stack porque o último scheduled pulse saudável observado era de
2026-09-29T10:22:38Z, acima da janela máxima de 5400 segundos.

Estado:
- código/Quality não é a causa do bloqueio;
- `SCHEDULED_PULSE_NOT_HEALTHY` permanece fail-closed;
- feature flag continua sem alteração;
- worker não foi armado;
- runtime não foi modificado;
- nenhum gate deve ser enfraquecido apenas para tornar o CI verde;
- qualquer reativação/ação de runtime continua exigindo autorização separada.

## 8. Checkpoint Mestre como memória oficial

O AION deve conhecer:
- decisões aprovadas;
- itens implementados;
- itens em validação;
- lacunas;
- pendências;
- decisões substituídas;
- fronteiras que exigem aprovação humana.

O Checkpoint Mestre é a fonte oficial de continuidade. Não criar memória
paralela conflitante. O ponteiro `checkpoint_mestre_latest.json` identifica a
camada incremental mais nova sem apagar as anteriores.

Estado da integração com o Core: **IMPLEMENTADO / EM VALIDAÇÃO** em
`atlasquant_aion_core_master_checkpoint_bootstrap.py`. O runtime bridge
incorpora o snapshot validado como evidência read-only; checkpoint inválido ou
adulterado falha fechado e não injeta contexto.

## 9. Estado técnico da stack Business neste checkpoint

A sequência recente de Draft PRs de governança Business foi construída com
fronteiras fail-closed:
- #427 — bounded runtime activation readiness;
- #428 — post-activation verification and expansion boundary;
- #429 — controlled scope expansion readiness;
- #430 — post-expansion verification and cycle freeze;
- #431 — expansion cycle audit ledger;
- #433 — tenant capacity and quota guardrail;
- #434 — quota application authorization boundary.

Essas PRs permanecem Draft neste checkpoint. CI verde é evidência técnica, não
autorização de merge, deploy, runtime, cobrança, aplicação de quotas ou
expansão.

## 10. Próximos blocos obrigatórios

PENDENTE / APROVADO:
- executar manualmente o sandbox físico isolado já preparado, configurar secrets somente no arquivo local ignorado pelo Git, validar OIDC/containers e então executar o E2E real contra Keycloak + PostgreSQL + adapter de revogação;
- configurar connectors reais de suporte/infra/incidentes e validar métricas do primeiro ambiente piloto;
- definir RPO/RTO, cópia secundária real e executar restore drill não produtivo da política Backup & Recovery;
- configurar connectors reais de custo/fatura e writer físico do storage versionado com read-back verification;
- segmento/candidato reais + custos reais + preço comercial real + revisão jurídica/comercial do primeiro piloto;
- configuração física dos connectors read-only, OAuth/secret store e mapeamento de schema dos providers reais;
- validação operacional do bootstrap do Checkpoint Mestre em ambientes empacotados/deployados;
- validação do roteador dos oito papéis em runtime/deploy empacotado;
- PDF atualizado da aba Negócios para visão do administrador.

## Decisões novas de 30/09

| ID | Estado | Título |
| --- | --- | --- |
| D-2026-09-30-PROACTIVE-GAPS | APROVADO / PENDENTE | Identificar proativamente lacunas necessárias |
| D-2026-09-30-COST-CAP-200 | IMPLEMENTADO / EM VALIDAÇÃO | Teto inicial de planejamento de R$200/mês |
| D-2026-09-30-DATA-INTEGRITY-FIRST | APROVADO / PENDENTE | Integridade e recuperação antes de potência |
| D-2026-09-30-B2B-SERVICE-FIRST | IMPLEMENTADO / EM VALIDAÇÃO | Monetização inicial por serviço B2B com AION |
| D-2026-09-30-DROPSHIPPING-OUT | DESCARTADO | Dropshipping fora das prioridades atuais |
| D-2026-09-30-TEAM-RBAC | IMPLEMENTADO / EM VALIDAÇÃO | Equipe & Acessos individualizados |
| D-2026-09-30-CAPACITY-SCALE-MANAGER | IMPLEMENTADO / EM VALIDAÇÃO | Gestor de Capacidade & Escala |
| D-2026-09-30-AION-INDEPENDENT-CHATGPT | APROVADO / PENDENTE | AION funciona sem depender do ChatGPT |
| D-2026-09-30-CHATGPT-OPTIONAL-ARCHITECT | APROVADO / PENDENTE | ChatGPT como apoio externo opcional |
| D-2026-09-30-EIGHT-LOGICAL-ROLES | IMPLEMENTADO / EM VALIDAÇÃO | Oito papéis lógicos internos do AION |
| D-2026-09-30-CHECKPOINT-LATEST-POINTER | IMPLEMENTADO / EM VALIDAÇÃO | Ponteiro explícito para checkpoint mais recente |
| D-2026-09-30-ECOSYSTEM-PRIORITY-BUSINESS | APROVADO / PENDENTE | Negócios vira prioridade principal após Núcleo/AION/interface |
| D-2026-09-30-TREASURY-BUCKETS | IMPLEMENTADO / EM VALIDAÇÃO | Tesouraria separada entre Negócios, Trader e Investimentos |
| D-2026-09-30-TRADER-INITIAL-CAP-30 | IMPLEMENTADO / EM VALIDAÇÃO | Limite inicial de 30% do capital total para Trader |
| D-2026-09-30-TRADE-TARGET-NOT-GUARANTEE | IMPLEMENTADO / EM VALIDAÇÃO | Meta de Trade não é promessa de retorno |
| D-2026-09-30-CORE-CHECKPOINT-BOOTSTRAP | IMPLEMENTADO / EM VALIDAÇÃO | Core carrega o Checkpoint Mestre validado no bootstrap |
| D-2026-09-30-COMMERCIAL-PIPELINE-END-TO-END | IMPLEMENTADO / EM VALIDAÇÃO | Pipeline B2B sequencial até saúde e renovação |
| D-2026-09-30-FIRST-PILOT-PRICING-REVIEW | IMPLEMENTADO / EM VALIDAÇÃO | Primeiro piloto exige fit, preço sustentável e Pilot Governance |
| D-2026-09-30-BACKUP-RECOVERY-POLICY | IMPLEMENTADO / EM VALIDAÇÃO | Backup em camadas, integridade e restore não automático |
| D-2026-09-30-INDEPENDENCE-CLT-INDEX | IMPLEMENTADO / EM VALIDAÇÃO | Índice privado para revisão futura de independência do emprego |
| D-2026-09-30-COMMERCIAL-LIVE-READ-BINDING | IMPLEMENTADO / EM VALIDAÇÃO | Pipeline comercial consome somente dados reais atestados em leitura |
| D-2026-09-30-FINOPS-LIVE-COST-LEDGER | IMPLEMENTADO / EM VALIDAÇÃO | Custos reais entram read-only e formam ledger hash-chained |
| D-2026-09-30-FINOPS-PERSISTENCE-RECONCILIATION | IMPLEMENTADO / EM VALIDAÇÃO | Versões do ledger são encadeadas e faturas reconciliadas sem pagamento |
| D-2026-09-30-REVENUE-OPPORTUNITY-ENGINE | IMPLEMENTADO / EM VALIDAÇÃO | Oportunidades de receita passam por gates econômicos antes do ranking |
| D-2026-09-30-CAPACITY-LIVE-METRICS | IMPLEMENTADO / EM VALIDAÇÃO | Capacity Manager recebe FinOps, suporte, infra e incidentes atestados |
| D-2026-09-30-REVENUE-LIVE-ECONOMICS | IMPLEMENTADO / EM VALIDAÇÃO | Oportunidades usam custo FinOps e capacidade real antes do ranking |
| D-2026-09-30-TEAM-ACCESS-PRODUCTION-BINDING | IMPLEMENTADO / EM VALIDAÇÃO | Conta individual, MFA forte, registry read-back e revogação viram gates de produção |
| D-2026-09-30-TEAM-ACCESS-SANDBOX-E2E | IMPLEMENTADO / EM VALIDAÇÃO | Keycloak + OIDC, PostgreSQL e revogação via adapter formam o sandbox E2E |
| D-2026-09-30-TEAM-ACCESS-PHYSICAL-SANDBOX | IMPLEMENTADO / EM VALIDAÇÃO | Sandbox local reproduzível, localhost-only e com partida manual explícita |
| D-2026-09-30-TEAM-ACCESS-SANDBOX-EVIDENCE | IMPLEMENTADO / EM VALIDAÇÃO | Baseline local sanitizado prepara revisão antes do lifecycle manual |
| D-2026-09-30-TEAM-ACCESS-SANDBOX-LIFECYCLE-PLAN | IMPLEMENTADO / EM VALIDAÇÃO | Lifecycle sandbox vira plano de dez etapas com decisão explícita separada |
| D-2026-09-30-TEAM-ACCESS-SANDBOX-LIFECYCLE-AUTHORIZATION | IMPLEMENTADO / EM VALIDAÇÃO | Registro formal futuro fica preso ao plano/baseline e não habilita executor |
| D-2026-09-30-TEAM-ACCESS-SANDBOX-LIFECYCLE-LEDGER | IMPLEMENTADO / EM VALIDAÇÃO | Evidências por step ficam em ledger hash-chain sanitizado e sequencial |
| D-2026-09-30-TEAM-ACCESS-SANDBOX-LIFECYCLE-STEP-GATE | IMPLEMENTADO / EM VALIDAÇÃO | Cada step recebe preflight e pós-review próprios antes de qualquer avanço |
| D-2026-09-30-TEAM-ACCESS-WINDOWS-OPERATOR-KIT | IMPLEMENTADO / EM VALIDAÇÃO | Fluxo Windows local ganha bootstrap, readiness, start e baseline com switches explícitos |
