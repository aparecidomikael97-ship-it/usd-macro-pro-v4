# AION Intelligence Core

## Visão

O AION é a camada de inteligência e orquestração do AtlasQuant. Ele organiza
capacidades existentes, evidências, memória, especialistas e políticas em uma
experiência simples. Não é uma AGI, não é autoridade autônoma e não transforma
análise em execução.

Princípio: **poderoso por dentro, simples por fora**.

## Inventário reutilizado

O Core evolui a base existente:

- `atlasquant_aion_core.py`: verdade básica, Guardian, custo e missões;
- `atlasquant_aion_cognitive_orchestrator.py`: decomposição, pesquisa e Critic;
- `atlasquant_aion_tool_hub.py`: ferramentas e preflight;
- `atlasquant_aion_fortress.py`: autoridade, autonomia e Proof of Safety;
- `atlasquant_aion_resilience.py`: agent firewall, circuit breaker e safe mode;
- `atlasquant_aion_provider.py`: provider externo fail-closed;
- `atlasquant_aion_dev_fusion.py`: segregação Builder/Reviewer/Breaker;
- `atlasquant_aion_memory.py`: Checkpoint Mestre e persistência;
- `atlasquant_aion_learning.py`: learning signals e promoção humana;
- `atlasquant_aion_observability.py`: eventos auditáveis com redação.

Os novos contratos conectam essas peças; não substituem os módulos de domínio.

## Fluxo central

```text
Interaction
  → AionContext / AionTask
  → Capability Registry
  → Router por metadata + contexto
  → Plano seletivo
  → Specialist Dispatch
  → Critic
  → Validator
  → Truth + Freshness + Safety Gate
  → Resposta / ação apenas proposta
  → memória, observabilidade e learning signal controlados
```

`atlasquant_aion_orchestrator.py` é deliberadamente não executor. Um estado
`READY` significa que o preflight não encontrou bloqueio; não significa que uma
ferramenta foi chamada.

Respostas locais e externas convergem em `ATLASQUANT_AION_RESULT_V1` por
`build_aion_result()`. O envelope preserva `request_id`, `task_id`, capability,
lane do provedor, contagem de evidências e o parecer do Validator/Truth Gate. Uma
resposta sem evidência confirmada permanece `REVISE`; o envelope nunca autoriza
ação externa, escrita automática de memória ou ordem real.

## Capability Registry

`atlasquant_aion_capabilities.py` registra:

- identificador e especialista;
- domínios, descrição e aliases;
- inputs e outputs;
- risco e modo de execução;
- ferramentas permitidas;
- roles permitidas;
- confirmação;
- custo estimado;
- disponibilidade.

O roteamento usa metadata declarada e `domain_hint`. Adicionar capability não
exige editar uma cadeia central de `if/elif`.

Especialistas atuais: Core, Dev, Research, Market, Macro, ICT, Risk, Lab,
Invest, Business, Studio e Admin. Eles compartilham infraestrutura e não ganham
permissões independentes.

## Truth Assessment

`atlasquant_aion_truth.py` preserva:

- `CONFIRMED`, `INFERENCE`, `HYPOTHESIS`, `UNKNOWN`;
- fonte e referência;
- tier da fonte;
- timestamp, TTL, idade, freshness e stale;
- confiança baseada na qualidade da evidência;
- conflito entre fontes.

`CONFIRMED` sem fonte ou timestamp exigido é rebaixado. Dado stale não parece
atual. Valores confirmados conflitantes produzem `CONFLICT`; o AION não escolhe
um silenciosamente. A explicação mostra conclusão operacional, evidências,
conflitos e lacunas, nunca chain-of-thought privado.

## Memória e Checkpoint Mestre

O Checkpoint Mestre v18 inclui `memory_layers`, mantendo compatibilidade com os
checkpoints anteriores e com `persona_memory`.

Camadas:

1. session;
2. working;
3. project;
4. decision;
5. knowledge;
6. user preference;
7. episodic;
8. checkpoint.

Cada entrada contém origem, data, confiança, validade, categoria, versão, tags,
status, `superseded_by`, estado de verdade, persona e referências. Conteúdo
idêntico é deduplicado; atualização preserva o registro anterior como
`SUPERSEDED`. Memória de persona exige correspondência exata para recuperação.
Payload incompatível recupera vazio e registra diagnóstico.

## Developer Engine

`atlasquant_aion_developer_engine.py` estrutura:

```text
REQUEST → PLAN → IMPLEMENT → TEST → REVIEW → RELEASE
```

O workflow exige ordem de fases, evidências, reviewer diferente do builder,
Critic adversarial independente, testes, rollback e documentação. A
autocorreção registra erro, hipótese, causa e evidências e para após três
tentativas. Definition of Done termina em `HUMAN_RELEASE_REVIEW`, nunca merge ou
deploy automático.

O Dev Fusion existente continua responsável pelos gates de Digital Twin,
Breaker e Evaluation Lab.

## Segurança e permissões

- autorização é aplicada na lógica, não somente na UI;
- Admin/Developer/Studio não são expostos a USER;
- Business aceita SALES/ADMIN;
- leitura de mercado/pesquisa pode ser usada por USER sem executar ações;
- ferramenta/capability desconhecida falha fechada;
- custo positivo exige política e aprovação;
- conteúdo externo é evidência, nunca autoridade;
- logs removem padrões de senha, token, chave e Bearer;
- `AION_EXTERNAL_ACTIONS_ENABLED` e `REAL_TRADING_ENABLED` são imutáveis em
  `False` nesta versão;
- real trading continua bloqueado mesmo com role, flag e aprovação.

## Observabilidade

Eventos correlacionam `request_id`, `task_id`, domínio, capability, ferramenta,
duração, resultado, risco, aprovação, fallback e confiança. Payloads de
requisição e credenciais não são registrados.

## Performance e fallback

O plano seleciona apenas capabilities relevantes. Especialista ou ferramenta
indisponível produz `DEGRADED_SAFE` e fallback local read-only que só resume
evidência existente. Providers externos permanecem opcionais, lazy e
desligados sem configuração, orçamento e aprovação.

## Interface

A Central AION mostra:

- AION ONLINE e gates ativos;
- memória em camadas;
- especialista/capability selecionada;
- estado de verdade;
- decisão e bloqueios;
- plano técnico apenas no modo Completo.

O modo Essencial usa o mesmo Core, mas reduz detalhes. A integração preserva o
redesign atual. A prévia também mostra a leitura local do especialista
selecionado.

## Leitura local dos especialistas

`read_specialist_evidence()` reutiliza funções puras já existentes. Ela descreve
somente o que a consulta local contém:

- contrato do universo Forex e fila sem pacote persistido;
- briefing macro sem linhas de entrada;
- matriz ICT/SMC sem evidência registrada, com PPR bloqueado;
- postura de risco quando a integridade não foi comprovada;
- evidência remota de laboratório não carregada, sem ler credencial;
- comparador de investimentos e catálogo de negócios vazios;
- providers de conteúdo não configurados;
- workflow de desenvolvimento incompleto e sem merge/deploy;
- plano de pesquisa não executado;
- inbox administrativa sem checkpoint;
- Guardian negando `real_trade` mesmo com aprovação.

`answer_truth` permanece `UNKNOWN`. Um contrato de código confirmado não vira
resposta da pergunta, cotação, recomendação ou ordem.

## Snapshot de sessão já carregado

`build_specialist_session_snapshot()` aceita somente evidência que o chamador
já tem em memória: scanner persistido, Radar, briefing macro, calendário da
sessão, pesquisa já carregada, backtest registrado, checkpoint administrativo
e estado local de Studio, Negócios ou Investimentos.

A leitura não busca web, feed, calendário remoto, GitHub, banco, API de mercado
nem modelo externo. Cada especialista distingue entrada ausente, presente porém
stale, conflitante ou válida. Snapshot ausente mantém `answer_truth=UNKNOWN`.
Dado stale não vira fato atual. Conflito permanece explícito, sem lado escolhido.

A Central mostra origem (`SESSION`, `CHECKPOINT`, `PERSISTED_SCANNER`,
`RESEARCH_EVIDENCE` ou equivalente), `observed_at`, freshness, `truth_state`,
conflicts e `answers_user_question`. O Guardian continua dono de `real_trade`.

## Limites atuais

- o Core planeja e valida; não é executor universal;
- a leitura local não consulta feed, calendário ao vivo nem store remoto;
- pesquisa web e modelos externos continuam condicionados a providers;
- métricas administrativas externas continuam desconhecidas sem integração;
- memória runtime só pode ser declarada persistida após confirmação do store;
- publicação, cobrança, merge, deploy, secrets e trading real permanecem fora
  da autonomia do AION.

## Specialist Router e certificação de domínio

O AION continua sendo um núcleo. Trader, Business e Investments selecionam,
respectivamente, AION Trader Expert, AION Business Expert e AION Investment
Expert. `AION/CORE` seleciona o AION completo. O contrato está em
`atlasquant_aion_specialist_router.py`. Esse roteador não executa ferramenta
e não transforma `BUSINESS_FUTURE`, `TRADER_FUTURE` ou `INVESTMENTS_FUTURE`
em capability disponível.

Domínio desconhecido permanece `UNKNOWN` / `DENIED_SAFE`. Domínio ambíguo pede
clarificação. Especialista ausente fica `DEGRADED_SAFE`, sem fallback silencioso.
Um perfil pode estar registrado e `NOT_CERTIFIED`. Até a certificação, a
autoridade de runtime não aumenta. O Core coordena e não herda trade, pagamento,
publicação ou deploy.

Memória com domínio não atravessa outro domínio sozinha. Leitura cruzada exige
o perfil `AION_CORE` e o domínio de origem em `explicit_domains`, e não promove
`UNKNOWN`, `STALE`, `CONFLICT` ou `INCOMPLETE`. Pai sem roles, tools ou scopes
não concede a metadata do perfil. Scope efetivo só existe na interseção de
allowlist do perfil, autoridade do pai, guardião e runtime; `*` não abre
acesso. A postura read-only de observabilidade, release, rollback e auditoria
está em `atlasquant_aion_core_posture.py`. A certificação desses especialistas é
`ATLASQUANT_AION_SPECIALIST_CERTIFICATION_V1`, descrita em
`docs/aion/AION_SPECIALIST_CERTIFICATION_V1.md`. Ela é distinta da certificação
de skill/plugin. `CERTIFIED` exige prova verificada, fingerprint do corpo e
`human_review_approved` com o booleano `True`. Certificar não ativa o especialista.

ADR-0001, ADR-0005 e ADR-0010 continuam sendo as decisões. Este bloco fecha o
contrato que ADR-0010 deixou pendente de implementação; não substitui esses
registros.

## Architecture Decision Records

Decisões estruturais do Núcleo ficam em `docs/adr/`. O índice é
`docs/adr/README.md`. ADR, nesse registry, significa Architecture Decision
Record. Average Daily Range e American Depositary Receipts não são arquivos
desse diretório. Um ADR substituído não é apagado.

A reconciliação do Checkpoint Mestre de `2026-09-15` a `2026-09-29` está em
`docs/continuidade/CHECKPOINT_MESTRE_RECONCILIACAO_2026-09-29.md`. Ela
complementa `docs/continuidade/CHECKPOINT_MESTRE_ATLASQUANT_2026-09-22.md` e
não o apaga. O gate documental é
`CHECKPOINT_MESTRE_RECONCILIATION_2026_09_15_TO_2026_09_29`.


## Validação do Núcleo e prontidão do BUSINESS

`atlasquant_aion_core_validation.py` adiciona uma camada read-only entre
hardening e certificação. Ela não consulta produção por conta própria e não
transforma presença de código em prova de deploy.

A identidade de produção só fica verificada quando o chamador fornece um SHA
observado do ambiente e a comparação com o SHA esperado resulta em match em alvo
não local. O Checkpoint Mestre só pode retornar `VALIDADO` quando integridade,
digest, identidade de produção, drill de rollback em sandbox, referências de
evidência e aprovação humana booleana exata estiverem presentes.

O drill de rollback deste estágio restaura somente uma cópia em memória e
confere digest canônico. Ele prova a mecânica do restore sem gravar o runtime.
O BUSINESS pode chegar a `READY_FOR_CERTIFICATION_REVIEW` quando oferta,
escopo, demo, treinamento, portal, LGPD, margem, suporte, aprovação humana e
pacote de prova estiverem evidenciados. Esse estado permanece abaixo de
`CERTIFIED`; runtime, pagamento, publicação e demais ações externas continuam
desligados.

ADR-0011 registra essa separação entre validação do Núcleo, prontidão de produto
e certificação formal do especialista.


## BUSINESS certification package

`atlasquant_aion_business_certification_package.py` liga o escopo atual de
Negócios ao Specialist Certification Gate sem ativar runtime. O escopo primário
são Automação B2B/Agentes de IA, Micro-SaaS AION, Serviços de IA, Revenue Ops /
Captação e Produtos Digitais próprios.

A oferta inicial gerenciada pode usar o nome provisório AION Presença &
Conversão. O modelo preferido é pacote fechado com implantação e recorrência,
sem promessa de resultado. Diagnóstico, Radar do Negócio, Portal do Cliente,
onboarding, SLA, Saúde do Cliente, margem, LGPD, auditoria, integrações,
Demo/Sandbox, quotas e treinamento do administrador fazem parte do readiness.

Código histórico de marketplace pode permanecer por compatibilidade, mas
dropshipping, afiliados, Shopee, Mercado Livre, TikTok Shop como motor principal
e e-commerce genérico não pertencem ao escopo primário atual.

O fluxo é `NOT_READY → READY_FOR_CERTIFICATION_REVIEW → TESTED → CERTIFIED`.
`TESTED` exige atestação de CI ligada por SHA, refs e fingerprint.
`CERTIFIED` exige também revisão humana booleana exata. Nenhum estado ativa
runtime, contato externo, contrato, pagamento, publicação, gasto, merge, deploy
ou trading real. ADR-0012 registra essa decisão.


## BUSINESS external attestation and formal review

`atlasquant_aion_business_external_attestation.py` is the read-only bridge
between the BUSINESS certification package and independently sourced GitHub
Actions evidence. It requires the exact repository and SHA plus successful runs
for Quality tests, AION Core Security Gate and AtlasQuant - Release Readiness.

The certification package also requires a formal human-review record bound to
the same SHA and technical fingerprint. A bare boolean approval no longer
certifies BUSINESS. Both CI provenance and human-review provenance fail closed
when the trusted verifier is absent, malformed or disagrees.

These gates do not activate runtime and do not authorize contact, contracts,
payments, publication, spend, merge, deploy or real trading. ADR-0013 records
the decision.


## BUSINESS runtime readiness

`atlasquant_aion_business_runtime_readiness.py` separates certification from
runtime authority. A certified BUSINESS specialist may become
`SANDBOX_READY` only when SHA/fingerprint binding, isolation, external-network
disablement, audit, rollback and kill-switch gates all pass.

The sandbox plan is limited to `read`, `analyze` and `draft`. External
contact, contracts, payment, publication, spend, deploy and real trading remain
denied. A generated runtime approval packet remains
`RUNTIME_APPROVAL_REQUIRED` with `runtime_activation_approved=false`.

ADR-0014 records that certification can never implicitly activate runtime.


## BUSINESS sandbox harness

`atlasquant_aion_business_sandbox_harness.py` executes deterministic
simulation-only BUSINESS cases after the runtime-readiness layer reports
`SANDBOX_READY`.

Initial cases are FAQ draft, lead qualification, follow-up draft and Business
Radar. Sessions are bound to tenant/workspace/actor/session, batches are bounded
and unknown or external actions fail closed.

The harness has no provider/network path and never sends, charges, publishes,
deploys or activates runtime. ADR-0015 records this simulation boundary.


## BUSINESS demo experience

`atlasquant_aion_business_demo.py` maps the approved Business scope into a
read-only, mobile-responsive experience: Atrair, Atender, Converter, Reter,
packages, commercial journey, client portal concepts, admin training and a
fixture-only Business Radar.

The Central Principal renders this demo for the ADMIN Business surface and the
AION Business workspace renders the same demo before historical tools. Legacy
marketplace tooling remains compatibility-only and is explicitly labeled.

The demo does not activate runtime or execute external actions. ADR-0016 records
the presentation boundary.


## BUSINESS guided administrator training

`atlasquant_aion_business_training.py` provides an offline, fixture-only
training layer for the BUSINESS administrator. It teaches problem discovery,
diagnosis, Radar reading, package fit, delivery explanation, objections and a
simulated sales conversation.

The AION Business workspace renders the training as a session-only lab. No
training completion grants operational authority. Unknown objections fail safe
by instructing the administrator not to invent an answer.

ADR-0017 records that administrator training precedes real BUSINESS use.


## BUSINESS diagnostic and proposal simulator

`atlasquant_aion_business_proposal_simulator.py` converts explicit demo inputs
into a four-pillar diagnostic, a simple client Radar, a preliminary package fit
and a professional proposal draft.

The simulator marks inputs as `DEMO_USER_INPUT`, never claims real client
verification and keeps commercial pricing at `A DEFINIR APÓS ESCOPO`.

The AION Business workspace renders one result stage at a time to preserve the
mobile navigation contract. No generated proposal can be sent, signed, charged
or used to activate runtime. ADR-0018 records this boundary.


## BUSINESS client portal demo

`atlasquant_aion_business_client_portal_demo.py` turns the diagnostic/proposal
demo state into the future client-facing shell: overview, Radar, action plan,
results, support and history.

The portal is intentionally simple. Technical routing, security gates,
fingerprints and runtime controls remain internal. The Results section begins in
`NO_REAL_RESULTS` and cannot fabricate metrics before trusted post-implementation
evidence exists.

The AION Business workspace renders one portal section at a time to keep mobile
navigation stable. ADR-0019 records this presentation and truth boundary.


## BUSINESS onboarding and implementation demo

`atlasquant_aion_business_onboarding_demo.py` models the post-proposal delivery
path as Scope → Data/Access → Integrations → Sandbox → Validation → Assisted
Delivery.

The access plan is least-privilege and carries placeholders only; no secret or
credential value is accepted or persisted. The flow can complete a demo and
produce `LIVE_REVIEW_REQUIRED`, but never authorizes or activates runtime.

The AION Business workspace renders one onboarding phase at a time for mobile
stability. ADR-0020 records this sandbox-first boundary.


## BUSINESS customer success and SLA demo

`atlasquant_aion_business_customer_success_demo.py` models post-implementation
client health, support/SLA, success planning, renewal readiness and expansion
review using demo-only signals.

Health and value delivery precede upsell. Expansion can only become
`EXPANSION_REVIEW_AVAILABLE` for a healthy demo customer and remains subject to
human review; automatic upsell is always disabled.

Renewal is likewise review-only and tickets never leave the demo. ADR-0021
records this retention-before-expansion boundary.


## BUSINESS client finance and capacity demo

`atlasquant_aion_business_client_finance_demo.py` separates per-client
implementation revenue, recurring revenue, cost stack, monthly contribution,
margin and capacity utilization.

Revenue is never treated as profit. AI, integrations, support, tools, taxes,
refunds and other costs are explicit. Request and support quotas surface
capacity pressure before it harms margin or service quality.

Commercial review is advisory only: no automatic repricing, charging or money
movement is possible. ADR-0022 records this financial truth boundary.


## BUSINESS trend and opportunity intelligence

`atlasquant_aion_business_trend_intelligence.py` evaluates business
opportunities from explicit evidence, using freshness, confidence, recurring
revenue fit, margin potential, delivery complexity and support load.

The same module provides a controlled improvement review using hypothesis,
before/after metrics and minimum sample size. Improvement evidence can become
eligible for human promotion review but never auto-deploys or changes runtime.

Continuous monitoring is an explicit future goal, while the current collector
runtime remains OFF. ADR-0023 records this evidence-first evolution boundary.


## BUSINESS commercial acquisition and client journey

`atlasquant_aion_business_commercial_acquisition_demo.py` models the
pre-client commercial path: acquisition channels, landing-page messaging,
prospect qualification, outreach draft, contract handoff, content plan and demo
funnel.

The site CTA is diagnosis-first. Outreach is never sent automatically and
`DO_NOT_CONTACT` blocks it. Contracts, invoices, payments and client portal
provisioning remain future reviewed actions.

ADR-0024 records this diagnostic-first commercial boundary.


## BUSINESS integration hub readiness

`atlasquant_aion_business_integration_hub.py` models WhatsApp Business,
email, forms, calendar, CRM, payments, social media and analytics before any
real provider connection exists.

Scopes are least-privilege and split into read-only, draft-only, future approval
required and prohibited-in-demo. The Hub never stores raw secrets and cannot
perform OAuth, send, publish, charge, refund or grant write authority.

ADR-0025 records this secret-free readiness boundary.


## BUSINESS privacy and audit governance

`atlasquant_aion_business_privacy_audit.py` defines purpose limitation,
retention, consent evidence, default-deny role access, data-subject request
review, audit events, configuration versioning and rollback preparation.

The module contains no real personal data and cannot execute export, deletion,
external writes or production rollback. Audit records document actions and
approvals but never grant authority.

ADR-0026 records this privacy/audit boundary.


## BUSINESS master readiness panel

`atlasquant_aion_business_master_readiness.py` aggregates Business into three
authority layers: DEMO, PILOT and LIVE.

DEMO gates describe product readiness only. Pilot gates require separate
operational review. Live gates require separate runtime/provider/credential
evidence. No layer automatically grants the next layer and even complete Live
gates remain review-only in this module.

ADR-0027 records this authority separation.
