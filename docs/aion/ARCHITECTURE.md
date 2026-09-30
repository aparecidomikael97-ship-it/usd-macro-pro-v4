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


## BUSINESS bounded pilot governance

`atlasquant_aion_business_pilot_governance.py` defines a readiness-only
first-pilot charter with one client, one workflow, few channels, short duration,
human operators, support ownership, mandatory gates, measurable success criteria
and explicit stop conditions.

Passing every gate can only produce `HUMAN_PILOT_APPROVAL_REQUIRED`. It never
records pilot approval, activates runtime or enables external actions.

ADR-0028 records this bounded first-pilot boundary.


## BUSINESS full stack consolidation V2

`atlasquant_aion_business_stack_consolidation_v2.py` freezes the complete
AION Core + BUSINESS Draft stack from #394 through #412 and validates branch,
SHA, draft/open posture, mergeability and required CI evidence.

The module produces a review-only bundle digest, ordered consolidation preview
and integration rollback plan. It has no GitHub/network execution path and
cannot authorize merge, deploy, pilot or runtime.

ADR-0029 records this administrative separation of technical readiness from
merge authority.

## BUSINESS full-stack consolidation dry-run V2

`atlasquant_aion_business_consolidation_dry_run_v2.py` layers a fail-closed
administrative runbook over the #394–#412 consolidation V2. Frozen evidence alone
produces `AWAITING_LIVE_REVALIDATION`.

A trusted caller must revalidate repository identity, open/Draft posture, SHAs,
bases, mergeability, required/UI checks, BUSINESS runtime OFF and absence of
merge authority. Even then, the maximum automatic state is
`READY_FOR_EXPLICIT_ADMIN_DECISION`.

Each hypothetical step requires pre-step revalidation and a separate explicit
administrative authorization. Post-step CI, runtime posture recheck and previous
main SHA preservation are mandatory before another PR can be considered. This
module cannot merge, rebase, enable auto-merge, deploy, authorize a pilot or
activate runtime.

ADR-0030 records this live-revalidation and stop-condition boundary.

## BUSINESS consolidation decision request V1

`atlasquant_aion_business_consolidation_decision_request.py` creates a
non-executing request envelope for a future human decision. It requires the
dry-run to have reached `READY_FOR_EXPLICIT_ADMIN_DECISION` and binds the
request to the exact repository, candidate SHA, base SHA, frozen bundle digest,
live-evidence reference, reviewer and scope.

The request has its own canonical digest. Any drift in repository, SHA, base,
bundle, evidence reference or scope causes `BINDING_MISMATCH` and requires a
new review. The highest state is `HUMAN_AUTHORIZATION_RECORD_REQUIRED`, which
does not record authorization and cannot merge, deploy, authorize a pilot or
activate runtime.

ADR-0031 records this anti-replay and anti-ambiguity boundary.

## BUSINESS explicit consolidation authorization record V1

`atlasquant_aion_business_consolidation_authorization_record.py` defines the
only accepted shape for a future explicit authorization record. Generic language
such as "ok", "vamos lá" or "pode seguir" is never interpreted as consolidation
authority.

The record must carry the exact decision token
`AUTHORIZE_STACK_CONSOLIDATION_394_412`, the exact request digest, matching
reviewer and scope, an approval timestamp, and explicit acknowledgements that
deploy, pilot and runtime remain separate and that CI/stop-on-drift remain
mandatory.

A valid record reaches `EXPLICIT_AUTHORIZATION_RECORD_VERIFIED`, but still
keeps `merge_execution_authorized=false`. Physical merge execution is a
separate boundary and is not implemented by this module.

ADR-0032 records this explicit anti-ambiguity authorization contract.

## BUSINESS consolidation execution preflight V1

`atlasquant_aion_business_consolidation_execution_preflight.py` is the final
read-only barrier before any physical merge can even be reviewed. It combines
the ready dry-run, exact decision request, explicit authorization record, live
revalidation, stack sequence position, observed/expected main SHA, BUSINESS
runtime OFF and absence of deploy authority.

Completed PRs must form an exact prefix of #394–#412 and the requested target
must be the next PR. Any skipped/reordered PR, SHA drift, stale authorization,
runtime posture change or deploy authority blocks the preflight.

The maximum state is `MERGE_EXECUTION_REVIEW_REQUIRED`; the module keeps
`merge_execution_authorized=false` and performs no GitHub action. After any
future separately executed merge, full CI, UI/mobile validation when applicable,
runtime posture recheck and rollback-SHA preservation are mandatory before the
next preflight.

ADR-0033 records this sequential fail-closed execution boundary.

## BUSINESS execution review packet V1

`atlasquant_aion_business_consolidation_execution_review_packet.py` freezes a
successful execution preflight into a digest-bound dossier for human review. The
packet includes repository identity, target PR/SHA, base SHA, pre-merge main SHA,
rollback reference, request digest, evidence reference, reviewer, post-step
requirements and stop-on-drift posture.

The packet can reach `READY_FOR_HUMAN_EXECUTION_REVIEW` only when all bindings
are coherent. Any target, rollback or packet digest drift produces a binding
mismatch and requires the dossier to be rebuilt.

This module creates no authorization and keeps
`merge_execution_authorized=false`; it performs no GitHub action, deploy,
pilot or runtime activation.

ADR-0034 records this frozen human-review dossier boundary.

## BUSINESS post-merge verification and rollback gate V1

`atlasquant_aion_business_consolidation_post_merge_verification.py` closes the
per-step consolidation safety loop after any future separately authorized merge.
Without real merge evidence it remains `POST_MERGE_EVIDENCE_REQUIRED`.

A completed step must prove the observed main SHA matches the expected merge
result, differs from the pre-merge SHA, preserves the pre-merge SHA as rollback
reference, passes Quality, Release Readiness, Core Security, UI Smoke and Mobile
DOM, and keeps BUSINESS runtime OFF with deploy authority absent.

Only then can it reach `STEP_VERIFIED_FOR_NEXT_PREFLIGHT`, which allows
building the next preflight but does not authorize the next merge. Any drift or
regression yields `ROLLBACK_REVIEW_REQUIRED`. Rollback remains human-reviewed,
non-automatic and non-executing.

ADR-0035 records this post-step verification boundary.

## BUSINESS sequential consolidation progress ledger V1

`atlasquant_aion_business_consolidation_progress_ledger.py` maintains the
offline read-only progression state for verified future merge steps across
#394–#412.

Only `STEP_VERIFIED_FOR_NEXT_PREFLIGHT` receipts can enter the ledger. PRs must
appear in exact canonical order; receipt digests and resulting main SHAs must be
unique; and each step's rollback reference must equal the resulting main SHA of
the previous verified step. The first step is anchored to an externally supplied
root main SHA.

A valid partial prefix yields `READY_FOR_NEXT_PREFLIGHT`. Any skip, duplicate
or broken rollback chain yields `LEDGER_BLOCKED`. After all 19 verified steps,
the maximum state is `CONSOLIDATION_COMPLETE_REVIEW_REQUIRED`; final CI,
UI/mobile, final SHA and runtime posture still require human review and deploy
remains a separate decision.

ADR-0036 records this deterministic progression boundary.


## BUSINESS consolidation completion review

`atlasquant_aion_business_consolidation_completion_review.py` is the final
read-only gate after a complete #394–#412 progress ledger. It revalidates the
final main SHA, all final CI checks, UI/mobile success, BUSINESS runtime OFF and
the requirement that deploy remain a separate decision.

The highest automatic state is `READY_FOR_FINAL_ADMIN_REVIEW`. Technical
closure requires the exact acknowledgement token
`ACKNOWLEDGE_BUSINESS_CONSOLIDATION_COMPLETE`, but even a valid acknowledgement
does not authorize deploy, production release, pilot or runtime.

ADR-0037 records this final consolidation boundary.


## BUSINESS release boundary handoff

`atlasquant_aion_business_release_boundary_handoff.py` separates a technically
acknowledged consolidation from any later deployment or runtime decision.

The handoff binds the final main SHA, technical acknowledgement digest, target
environment, deploy-plan reference, rollback SHA and monitoring-plan reference.
BUSINESS runtime must remain OFF and runtime authority must stay separate.

The highest automatic state is `READY_FOR_SEPARATE_DEPLOY_DECISION`. No deploy
is authorized or executed. ADR-0038 records this boundary.


## BUSINESS deploy verification and runtime boundary

`atlasquant_aion_business_deploy_verification_runtime_boundary.py` defines a
deploy-only authorization record, a non-executing preflight, post-deploy receipt
verification and a separate runtime-decision packet.

A verified deploy must match the authorized SHA and environment, keep BUSINESS
runtime OFF, and pass application health, UI/mobile, observability and rollback
checks. Only then can the state become
`DEPLOY_VERIFIED_RUNTIME_DECISION_SEPARATE`.

No function deploys or activates runtime. ADR-0039 records this boundary.

## BUSINESS runtime activation readiness

atlasquant_aion_business_runtime_activation_readiness.py consumes only the
verified runtime boundary produced after a deploy has been checked. It validates
a bounded scope before a human runtime decision can even be recorded.

Sandbox allows no real tenant. Pilot and bounded production require an explicit
tenant list capped at 10. Monitoring, rollback, privacy, support, finance
guardrails and integration health are mandatory.

The exact token is AUTHORIZE_BUSINESS_RUNTIME_ACTIVATION. Generic confirmations
never authorize runtime. A valid authorization still keeps physical execution
separate, forbids automatic expansion and leaves billing/client actions behind
their own boundaries.

The module performs no runtime activation, traffic switch, deploy or external
action. ADR-0040 records this boundary.

## BUSINESS post-activation verification and expansion boundary

atlasquant_aion_business_post_activation_expansion_boundary.py verifies evidence
from a future bounded runtime activation executed through a separate path. The
observed scope and tenant set must match the authorized execution-review packet
exactly.

Application health, observability, tenant isolation, privacy guardrails,
support readiness, billing guardrail and rollback readiness must all succeed.
A verified receipt reaches RUNTIME_ACTIVATION_VERIFIED_SCOPE_FROZEN.

Success does not authorize growth. Only a separate
EXPLICIT_EXPANSION_DECISION_REQUIRED packet may be produced, with token
AUTHORIZE_BUSINESS_SCOPE_EXPANSION. Automatic expansion, billing and client
actions remain false.

The module performs no activation, expansion, deploy, rollback or external
action. ADR-0041 records this boundary.

## BUSINESS controlled scope expansion readiness

atlasquant_aion_business_expansion_readiness.py validates a proposed growth step
against the scope frozen by ADR-0041. It permits only incremental transitions:
sandbox to pilot, pilot growth, pilot to bounded production, or bounded
production growth within the configured tenant cap.

Existing tenants must be preserved, proposed tenants must be explicit, and the
maximum bounded set is 10. Privacy, support, finance guardrails, integrations,
capacity, monitoring and rollback are revalidated before a decision request can
become ready.

The exact decision token is AUTHORIZE_BUSINESS_SCOPE_EXPANSION. Generic
confirmation never authorizes expansion. Even a valid authorization keeps
physical execution, billing and client actions separate.

The module performs no expansion, runtime change or external action. ADR-0042
records this boundary.

## BUSINESS post-expansion verification and cycle freeze

atlasquant_aion_business_post_expansion_cycle_freeze.py verifies evidence from a
future scope expansion executed through a separate path. The observed scope and
tenant set must match the authorized expansion review packet exactly.

Application health, observability, tenant isolation, privacy, support, capacity,
billing guardrail and rollback readiness must all succeed. A verified receipt
reaches SCOPE_EXPANSION_VERIFIED_AND_FROZEN.

A green cycle does not grant continuing growth. It may only recreate the same
EXPLICIT_EXPANSION_DECISION_REQUIRED boundary consumed by the controlled
preflight from ADR-0042. Automatic expansion, billing and client actions remain
false at every cycle boundary.

The module performs no expansion, runtime change, deploy, rollback or external
action. ADR-0043 records this boundary.

## BUSINESS expansion cycle audit ledger

atlasquant_aion_business_expansion_cycle_audit_ledger.py keeps a pure
administrative, tamper-evident history of verified expansion cycles. Each entry
chains the prior entry digest with the expansion verification digest,
authorization digest, previous scope/tenants and verified scope/tenants.

The ledger must first bind to a verified expansion boundary as its genesis. An unbound ledger can remain an empty administrative template but cannot accept a cycle. This prevents a truncated history from being presented as the complete chain.

The ledger revalidates sequence, anti-replay, transition rules, tenant
preservation, continuity between cycles and the bounded tenant cap. Any drift or
digest mismatch blocks the append.

The ledger performs no expansion, runtime change, deploy, rollback, billing,
publication or external action. ADR-0044 records this boundary.

## BUSINESS tenant capacity and quota guardrail

atlasquant_aion_business_capacity_quota_guardrail.py binds per-tenant usage
limits and cost budgets to the latest integrity-verified expansion ledger state.
The quota tenant set must match the ledger tenant set exactly.

The review requires explicit AI, integration, workflow and storage limits,
explicit cost budgets, expected revenue, an administrator-defined minimum margin
and an administrator-defined capacity reserve. Margin is recalculated after the
reserve is applied.

A green review reaches CAPACITY_QUOTA_REVIEW_READY only. Applying quotas,
billing, runtime changes, expansion and client actions remain separate. ADR-0045
records this boundary.

## BUSINESS quota application authorization boundary

atlasquant_aion_business_quota_application_authorization.py separates a reviewed
capacity plan from any future application of real tenant limits. The exact token
AUTHORIZE_BUSINESS_QUOTA_APPLICATION plus all acknowledgements and an actor are
required to record authorization.

Even then, application remains non-executing until a separate preflight confirms
a change window, monitoring, rollback/restoration, dry-run, support and incident
response readiness. The maximum automatic state is
QUOTA_APPLICATION_EXECUTION_REVIEW_REQUIRED.

The module never applies quotas, changes billing or runtime, expands scope or
calls external systems. ADR-0046 records this boundary.

## AION eight logical roles

The AION remains one central nucleus. ADR-0047 defines eight logical roles
activated on demand rather than eight independent always-on AI systems:

1. Core / Orchestrator.
2. Architect / Strategist.
3. Guardian / Auditor.
4. Executor / Operator.
5. Memory / Knowledge.
6. FinOps.
7. Observability / Reliability.
8. Customer Success / Commercial.

Roles may share models and infrastructure to reduce cost. Specialist roles do
not receive independent authority for critical actions. RBAC, tenant isolation,
human approval boundaries and fail-closed execution remain authoritative.

The latest master-checkpoint reconciliation is discovered through
`docs/continuidade/checkpoint_mestre_latest.json` and validated read-only by
`atlasquant_aion_checkpoint_latest.py`.

## BUSINESS team access / RBAC

atlasquant_aion_business_team_access_rbac.py extends the existing AtlasQuant
identity/session layer with Business memberships, fixed profiles, explicit
tenant scope and strong-auth enforcement.

The layer does not create a parallel identity system. It binds the authenticated
username to a Business membership and makes the AION consume the same
permission decision as the interface. Cross-tenant access and automatic
permission escalation remain false. Critical actions keep their independent
approval gates.

ADR-0048 records this boundary.

## BUSINESS Capacity & Scale Manager

atlasquant_aion_business_capacity_scale_manager.py turns the Business capacity
plan into a read-only customer-admission ceiling. It validates the exact quota
review digest and combines tenant costs, shared platform cost, the currently
approved budget cap, support capacity, infrastructure headroom, tenant health
and projected margin.

The initial planning cap is R$200/month. The manager may report a
`safe_additional_tenants` value, but it never accepts a customer or increases
budget automatically. Customer admission remains a separate explicit decision.

ADR-0049 records this boundary.

## FinOps Budget Governor & Treasury

atlasquant_aion_finops_budget_governor.py governs the initial R$200/month
ecosystem planning cap and separates the economic roles of Business, Trader and
Investments.

Business is the primary initial funding source for the ecosystem. Trader profit
is retained in the Trader bucket and the initial policy caps Trader allocation
at 30% of total ecosystem capital. Investments remain focused on long-term
patrimony. Trade targets are planning inputs only and never become guarantees or
expected-return claims.

The module is read-only: no spending, transfer, billing change, trade or budget
increase is executed.

ADR-0050 records this boundary.

## AION Core master-checkpoint bootstrap

`atlasquant_aion_core_master_checkpoint_bootstrap.py` validates the canonical
latest Checkpoint Mestre pointer before converting a bounded snapshot into
stable AION Core evidence. The runtime bridge preserves existing runtime
evidence and appends the validated master-checkpoint context.

Invalid or tampered checkpoint state fails closed and contributes no evidence.
No parallel memory store, network call or operational authority is introduced.

ADR-0051 records this boundary.

## AION deterministic eight-role router

`atlasquant_aion_eight_role_router.py` sits above the existing domain routers.
Domain routing decides where the task belongs; the logical-role router decides
which internal AION roles should review it.

The Orchestrator is always present and at most three additional roles are
selected, keeping each task bounded to four logical roles. The router validates
the eight official role IDs against the latest master-checkpoint snapshot before
routing. Critical intents force strong review metadata but never grant physical
execution or wider authority.

ADR-0052 records this boundary.

## BUSINESS B2B recurring revenue offer

`atlasquant_aion_business_b2b_revenue_offer.py` composes the existing Business
diagnostic, proposal, capacity, privacy, SLA, onboarding, integration and
financial layers into one initial recurring B2B offer.

The first productized offer is AION Atendimento & Automação Comercial, using an
implementation fee plus monthly recurring revenue. Pricing is not invented by
the system: caller-supplied verified costs and an administrator-defined minimum
margin produce a mathematical sustainability floor. Capacity must exist before
the offer can reach admin sales review.

The commercial pipeline is sequential through qualification, diagnostic,
proposal, contract, onboarding, delivery, customer health and renewal/expansion.
No stage is physically advanced by this layer.

ADR-0053 records this boundary.

## BUSINESS first pilot & pricing review

`atlasquant_aion_business_first_pilot_pricing_review.py` bridges the
productized B2B offer and the existing Pilot Governance layer.

It scores only explicit administrative fit inputs, requires an administrator
fit floor, blocks DO_NOT_CONTACT candidates, and validates that the proposed
pilot price stays above the offer's sustainable floor while preserving minimum
margin and implementation contribution.

The maximum automatic state is
`READY_FOR_ADMIN_FIRST_PILOT_REVIEW`. Candidate selection, price approval,
contact, proposal sending, contract, billing, tenant admission and runtime
remain outside this layer.

ADR-0054 records this boundary.

## AION Backup & Recovery policy

`atlasquant_aion_backup_recovery_policy.py` unifies source archive, checkpoint
version history and a distinct secondary-copy requirement under one read-only
governance layer.

The source-backup workflow now verifies its SHA256, tests ZIP extraction and
checks critical continuity files before upload. Runtime checkpoint history stays
separate from source backup. RPO/RTO are administrator-defined planning targets,
not invented SLAs.

Restore remains human-reviewed and non-automatic. Production restore is outside
this layer; recovery drills are limited to local/sandbox/staging planning.

ADR-0055 records this boundary.

## AION Independence CLT Index

`atlasquant_aion_independence_index.py` provides a private-input planning
index for evaluating whether the ecosystem has enough non-Trade income
consistency, reserve, recurring revenue and client diversification to justify a
human transition review.

Personal financial values are runtime inputs and are not hardcoded in the
repository by this module. The score is not a probability and the module never
recommends leaving employment. Essential expenses depending on Trade blocks the
transition-review gate.

ADR-0056 records this boundary.

## BUSINESS commercial live data binding

`atlasquant_aion_business_commercial_live_data_binding.py` provides a
read-only boundary for externally attested commercial records from CRM, forms,
email, calendar, payments and analytics.

Only pseudonymous references, canonical pipeline stage, permission state and
fresh source evidence are accepted. Raw contact PII, credentials, stale records
and duplicate source records are rejected. The resulting pipeline is an
observed state only and cannot auto-advance or write back to external systems.

The maximum automatic state is
`READY_FOR_ADMIN_LIVE_READ_BINDING_REVIEW`.

ADR-0057 records this boundary.

## AION FinOps live cost ledger

`atlasquant_aion_finops_live_cost_ledger.py` accepts externally attested
read-only cost observations and converts them into a deterministic append-only
hash chain.

Direct costs require a tenant; shared costs cannot name one. The verified
ledger can feed the existing Budget Governor and produce an administrator-driven
tenant cost allocation view. Any retroactive change breaks digest verification.

Provider connectors, physical persistence, payments, plan changes and pricing
actions remain outside this module.

ADR-0058 records this boundary.

## AION FinOps ledger persistence & invoice reconciliation

`atlasquant_aion_finops_ledger_persistence_reconciliation.py` adds a
version-manifest chain above the verified live-cost ledger. Each manifest binds
its version number to the previous manifest digest, storage reference, creator,
timestamp and exact ledger identity.

The version chain rejects gaps, reorder, replay and digest tampering. Invoice
reconciliation requires a read-only attested invoice, matching provider/period,
a verified ledger and a total inside a bounded tolerance.

Physical storage writes, provider calls, invoice payment, subscription changes
and price changes remain outside this module.

ADR-0059 records this boundary.

## BUSINESS Revenue Opportunity Engine

`atlasquant_aion_business_revenue_opportunity_engine.py` prioritizes service
opportunities using explicit administrator-supplied economics and operational
inputs.

The engine blocks opportunities that exceed startup budget, miss minimum margin,
lack positive monthly contribution or have no capacity. Only eligible rows are
scored using margin, time-to-cash proxy, repeatability, evidence readiness,
startup efficiency, support efficiency and implementation efficiency.

The score is a planning comparator, not a probability or sales forecast. No
market prices are embedded and no sale, spend or contact is executed.

ADR-0060 records this boundary.

