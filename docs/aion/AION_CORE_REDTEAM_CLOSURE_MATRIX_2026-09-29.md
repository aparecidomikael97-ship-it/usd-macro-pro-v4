# AION Core — Red-Team Closure Matrix — 2026-09-29

Status desta matriz: **reconciliação técnica da auditoria Codex com a ponta consolidada #359**.

Esta página não é uma certificação de maturidade, não autoriza merge/deploy e não transforma ausência de reprodução em prova absoluta de segurança. Ela registra quais defeitos concretos da auditoria antiga estão agora cobertos pelo código/testes da ponta consolidada e quais decisões operacionais continuam humanas.

Ponta analisada no momento desta atualização: `chatgpt/aion-resource-bounds-residual-v2`.

## Matriz RT01–RT20

| Finding | Estado atual | Evidência técnica atual |
|---|---|---|
| RT01 retry consumido | CLOSED_IN_CODE | Durable Tasks preserva idempotência/retry consumido; regressões existentes mantidas. |
| RT02 capability/permission resselada | CLOSED_IN_CODE | Critical Review revalida capability/permissions contra trusted context; fingerprint não é autoridade. |
| RT03 mesmo agente em Prime/Shadow/Sentinel | CLOSED_IN_CODE | `adjudicate_critical_task` bloqueia `REVIEWER_INDEPENDENCE`; regressão cobre principal único. |
| RT04 review cross-tenant/workspace | CLOSED_IN_CODE | Review exige binding de tenant/workspace + task_ref + plan_version; mismatch bloqueia. |
| RT05 refs inventadas | CLOSED_IN_CODE | Evidence/approval refs permanecem UNVERIFIED sem verifier e precisam de binding exato. |
| RT06 sensitive textual | CLOSED_IN_CODE | Somente bool exato é aceito; tipo ambíguo gera `SENSITIVE_TYPE_INVALID` e fail-closed. |
| RT07 approval textual no checkpoint writer | CLOSED_IN_CODE | Sink de Checkpoint exige `approved is True`; regressões bloqueiam strings/números antes do transporte. |
| RT08 strings false em provider/router | CLOSED_IN_CODE | Router e Provider exigem flags booleanas exatas antes de rota/transport. |
| RT09 custo inválido vira zero | CLOSED_IN_CODE | Custo inválido/ausente permanece UNKNOWN/BLOCKED; zero só é aceito como número zero explícito. |
| RT10 segredo em repr | CLOSED_IN_CODE | `RuntimeConfig.token` e `ProviderConfig.api_key` estão ocultos/redigidos em representação. |
| RT11 truth_record textual | CLOSED_IN_CODE | Truth flags exigem bool; tipos inválidos produzem UNKNOWN. |
| RT12 developer human_approved textual | CLOSED_IN_CODE | `developer_step_allowed` exige `human_approved is True`. |
| RT13 versão/nonce/schema | CLOSED_IN_CODE | versão exata + nonce obrigatório + schema esperado; #359 adiciona closed schema e bloqueio `UNKNOWN_FIELDS`. |
| RT14 Recovery confia em rótulo | CLOSED_IN_CODE | Integridade é recomputada; revision histórico é relido, digests são comparados e bytes revalidados alimentam restore. |
| RT15 segredo em mensagem | CLOSED_IN_CODE | Conteúdo/refs passam por redação/detecção antes do envelope; segredo detectado bloqueia. |
| RT16 entitlement false textual | CLOSED_IN_CODE | Approval/evidence exigem bool exato; estado confirmado é rebaixado sem aprovação/evidência válida. |
| RT17 expiry inválida | CLOSED_IN_CODE | Parse inválido é distinguido de ausência e gera `INVALID_EXPIRY`. |
| RT18 release confirmed textual | CLOSED_IN_CODE | `confirmed is True` + verifier de refs; sem verifier não chega a HUMAN_REVIEW_READY. |
| RT19 Memory/Recovery dependia de Negócios | CLOSED_IN_CODE_FOR_ORIGINAL_DEFECT | Business/Studio/Promotions possuem adapters lazy/fail-closed para Core vazio. Entitlements permanece propositalmente no Tenant Core por ser fronteira de autorização. |
| RT20 supply chain variável | CLOSED_IN_CODE / OPERATIONAL_RULESET_NOT_VERIFIED | requirements/tooling/actions/workflows foram pinados e SBOM retido. Required checks/ruleset operacional continua decisão humana/admin e não foi alterado automaticamente. |

## Hardening adicional posterior à auditoria

A #359 também contém hardening que não existia no snapshot auditado:

- Action Receipts tratados como evidência, nunca autoridade;
- write/readback reconciliation para Checkpoint e Global Worker;
- CAS + fencing token + lease owner/token/fence em Global Worker;
- inflight work-intent e reconciliação explícita, sem retry automático ambíguo;
- Recovery outcome truth: restore só é confirmado com save + verify CONFIRMED;
- strict Base64/JSON histórico, duplicate-key rejection, SHA histórico completo;
- resource bounds em Operations, Continuity, Learning, Business, Studio, Promotions, Entitlements, Tenant/Session Memory, Live Event Journal, Wisdom, Digital Twin, Dev Fusion, Release Confidence, Evaluation Lab, Tool Hub e Model Registry;
- Worker Runtime declara explicitamente `multi_instance_safe=false` e `concurrency_scope=CALLER_CHECKPOINT_ONLY`;
- Critical Review usa revisão limitada e closed message schema.

## O que continua NÃO certificado

Mesmo com os defeitos reproduzidos acima fechados no código, continuam fora de uma certificação automática:

- regras administrativas/required checks do GitHub;
- concorrência distribuída real em múltiplas instâncias;
- 24/7 real sem heartbeats persistidos;
- restore real em ambiente de produção;
- RPO/RTO operacional;
- provider pago/externo real;
- deploy real;
- trading real;
- segurança absoluta contra todo estado ou payload possível.

Esses itens exigem ambiente/autoridade humana apropriados. AION deve continuar declarando UNKNOWN/BLOCKED quando a prova não existe.

## Regra de integração

Para o turno atual, usar **#359 como ponta única consolidada do AION/Núcleo**. PRs antigas marcadas como superseded não devem ser reintegradas separadamente.

A interface cockpit permanece em trilha separada (#358) e não pode alterar autoridade, Memory, Recovery ou workers enquanto a validação do Core estiver em andamento.
