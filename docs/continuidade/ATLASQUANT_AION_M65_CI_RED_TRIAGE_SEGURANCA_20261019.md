# AtlasQuant / AION — M65: auditoria de CI oficial e migração segura de testes legados

**Data:** 2026-10-19. **Escopo:** GO-LAB de auditoria sobre CI já executada; NO-GO integração; HARD NO-GO operação. **0/6 P0 homologados.** Não houve execução nova de testes do produto, PR, merge, deploy, Worker ou despesa no M65.

## Referência fixada

Repositório `aparecidomikael97-ship-it/usd-macro-pro-v4`; A118 no [PR Draft #1326](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/pull/1326), HEAD `c62fab663c6349d7320f7843c8d09587c514426b`, aberto e não mesclado conforme verificação desta rodada. Computador remoto Windows OFFLINE.

**Esta é uma auditoria de logs da CI REAL do GitHub executada em 2026-10-16, não um novo resultado de teste.**

- [Workflow dirigido A118 (run 38919546556)](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/38919546556): **39/39 PASS Windows** (job `117035599561`) e **39/39 PASS Ubuntu** (job `117035600009`).
- [Workflow Quality/Security (run 38919546692)](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/38919546692): **Security 365 PASS** (job `117035599859`); **Quality 6562 testes, 50 FAIL + 34 ERROR**, job `117035600199`. Os resultados Quality permanecem abertos: NÃO renomear, filtrar, xfail nem desabilitar casos.

## Taxonomia dos 34 ERROR — verificada no traceback de cada caso

| Erro registrado no log do job Quality | Contagem | Interpretação limitada |
|---|---:|---|
| `PermissionError: INDEPENDENT_PRODUCER_NOT_ENROLLED` | 23 | Bloqueio na fronteira do produtor não matriculado. Só um produtor de confiança demonstrado pode mudar o contrato. |
| `PermissionError: INDEPENDENT_PRODUCER_RECEIPT_NOT_ENROLLED` | 8 | Fronteira de recibos independentes ainda sem autoridade inscrita. |
| `PermissionError: INDEPENDENT_PRODUCER_NO_EFFECT_FENCE_NOT_ENROLLED` | 1 | Prova independente de ausência de efeito não matriculada. |
| `KeyError: 'plan'` | 2 | Testes legados acessam uma chave não fornecida quando a emissão do plano é deliberadamente negada. |
| **TOTAL** | **34** | 32 erros de fronteira sem produtor independente; 2 incompatibilidades de expectativas de testes com a negação atual. |

**50 FAIL:** 50 comparações/asserções nos cenários Worker/Global Worker/reativação/LIVE foram registradas como FAIL; várias esperam estados positivos (`ARMED_WORKER`, `CONFIRMED`, `ACTIVATION_PLAN_READY`, etc.) onde o código atual responde `BLOCKED`. **Não declarar todos com mesma causa sem inspeção individual.** Não existem `sqlite3.OperationalError` nos 34 ERROR **desta execução específica**; isso não prova que outras falhas de SQLite anteriores estejam resolvidas.

## Os três resultados históricos originais de reativação

Fonte A118 fixada: `test_atlasquant_aion_global_worker_reactivation_gate.py`, blob Git SHA-1 `6c66e11b4c29b2bef1ff277a0c47740cdb0bf220`.

1. `test_activation_plan_binds_green_post_incident_gate`, linha ~439: **FAIL** — espera `ACTIVATION_PLAN_READY`, recebe `BLOCKED`.
2. `test_final_activation_execution_requires_fresh_gate`, linha ~469: **ERROR**, `KeyError: 'plan'`.
3. `test_execution_validation_rejects_reopened_gate`, linha ~517: **ERROR**, `KeyError: 'plan'`.

Causa demonstrada pelo produto: `atlasquant_aion_global_worker_activation.py:365–463`, blob `df43bb4371c784396069f4ede51205b0aa19cc0a`. Depois da verificação de estruturas e gate, `prepare_global_worker_activation_plan` termina retornando `status=BLOCKED`, `reason=INDEPENDENT_ACTIVATION_AUTHORITY_NOT_ENROLLED`, `feature_flag_modified=False`, `global_worker_executed=False`, **sem chave `plan`**. O teste legado pressupõe emissão positiva cuja autorização independente não existe. Tornar o teste verde fabricando plano, titular ou assinatura seria uma regressão grave de segurança.

### Prova negativa adicional a desenvolver no LAB — NÃO EXECUTADA

Em branch de teste isolada, sem tocar nos três legados:
- **N-M65-01:** a mesma fixture de runtime armado/readiness/flag/gate do teste legado chama `prepare_global_worker_activation_plan`; confirmar `BLOCKED`, `INDEPENDENT_ACTIVATION_AUTHORITY_NOT_ENROLLED`, ausência de `plan`/`approval`, nenhum efeito ou flag. Confirmar a razão exata — se a fixture não atingir o bloqueio final, diagnosticar o guard anterior e não forçar o resultado.
- **N-M65-02:** após observar um incidente reaberto, validar o novo gate **sem depender de obter approval autêntico impossível**; afirmar negação diante de evidência atual adversa, mas **sem construir autorização falsa nem aceitar um gate obsoleto**. Se as assinaturas atuais não permitem provar isso, registrar RED de contrato e a dependência de fonte durável de OPEN (M53/M54).
- **N-M65-03:** tentativa explícita de usar `plan` sintético, ticket auto-hasheado, ou approval caller-supplied deve ser negada pelo guard externo (nunca gerar Worker ou alteração da flag).
- **N-M65-04:** sempre separar status diagnósticos `READY` do direito de ativação; a existência de zero fechamentos não prova ausência de incidentes OPEN (M53/M54).

**Sem autorização para migrar os testes oficiais.** Só considerar uma eventual migração quando existir contrato revisado que preserve toda a cobertura adversarial original. Não remover as três falhas antigas, não impor `xfail` e não ajustar expectativas positivas como forma de forçar CI verde.

## Decisão e dependências

A auditoria distingue **incompatibilidade da suíte legada** de **autorização externa inexistente**, e identifica duas `KeyError` concretas para priorizar no LAB de regressão negativa. A correção do A118 **não pode** ser permitir `ACTIVATION_PLAN_READY` sem F1/T1/F2. Primeiro validar negativa de plano, gate reaberto e zero efeitos, preservar os RED históricos e obter revisão independente para qualquer proposta de integração.

**P0 não fechado.** Mantidos Worker OFF, ZERO_AUTO_RESEND, HARD NO-GO, Quality 50 FAIL/34 ERROR, três REDs de reativação, sem merge/deploy/CI nova/gasto. Próximo objetivo único: testes N-M65-01/02 em cópia de A118 com fonte oficial pinada, sob ferramenta de execução segura quando disponível; se não houver atestação independente para caminhos positivos, não simular GO.
