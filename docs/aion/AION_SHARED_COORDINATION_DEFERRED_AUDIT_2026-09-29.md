# AION/Núcleo — Shared Coordination Deferred Audit — 2026-09-29

Status: **DEFERRED_FUTURE_CAPABILITY — NÃO É BLOQUEIO DO CANDIDATO ATUAL**.

## Frente auditada

PR legada Cursor **#286 — AION: shared coordination gate with atomic CAS and fencing**.

Ela contém uma arquitetura que **não está presente como módulo dedicado** na ponta consolidada #359:

- `atlasquant_aion_shared_coordination.py`;
- contrato provider-neutral `SharedCoordinationAdapter`;
- capabilities explícitas para shared store;
- probe real e bounded de CAS;
- monotonic versions;
- atomic monotonic fencing token;
- TTL;
- atomic delete;
- global kill-switch namespace;
- receipt do probe com expiração/binding de adapter.

## O que #359 já possui

A #359 já implementa no Global Worker:

- estado persistido no runtime checkpoint;
- conditional write/CAS por SHA;
- lease owner/token;
- fencing counter/token persistido;
- release exigindo owner + lease token + fencing token;
- inflight work intent;
- fail-closed reconciliation;
- sem automatic retry em outcome ambíguo;
- kill switch persistido;
- staged/persisted arming;
- autorização delegada limitada;
- sem trading real, deploy, merge, publicação, pagamento ou provider externo automático.

A trilha de Worker Runtime de sessão também declara explicitamente:

- `multi_instance_safe=false`;
- `concurrency_scope=CALLER_CHECKPOINT_ONLY`;
- `continuous_24x7_confirmed=false`.

## Diferença real

A #359 **não possui** um adapter independente de shared coordination nem um probe de backend que prove, em ambiente real, propriedades como:

- CAS compartilhado entre múltiplas instâncias independentes;
- fencing token monotônico fornecido por backend externo;
- TTL/delete atômico comprovados pelo backend;
- kill-switch namespace global separado;
- capacidade operacional multi-instância certificada.

Isso não é tratado como regressão atual porque o projeto **não deve afirmar multi-instance safety nem 24/7 real sem essa prova**.

## Decisão de engenharia

**Não integrar #286 por cherry-pick/merge.**

Motivos:

1. a branch #286 divergiu profundamente da ponta atual;
2. ela carrega dezenas de commits de uma pilha antiga;
3. grande parte da funcionalidade intermediária já foi substituída por implementações posteriores;
4. integrar a branch inteira arriscaria reintroduzir contratos antigos no candidato verde;
5. o candidato #359 está congelado/validado e não deve ser alterado sem nova evidência concreta.

## Caminho futuro correto

Se AtlasQuant/AION chegar ao ponto de exigir **múltiplas instâncias realmente simultâneas** ou um worker externo 24/7:

1. criar uma branch nova a partir da #359/main atual;
2. portar somente o contrato/provider-neutral de shared coordination e o probe;
3. manter custo zero por padrão;
4. nenhum backend pago sem aprovação explícita;
5. executar probe real apenas com confirmação ADMIN;
6. exigir evidence receipt fresco e bindado ao adapter;
7. manter `multi_instance_safe_confirmed=false` até a prova passar;
8. rodar novamente Quality, Security Gate, Worker Readiness e adversarial tests.

## Estado atual

- #286: **LEGACY / DEFERRED / DO NOT AUTO-INTEGRATE**.
- #359: permanece candidato autoritativo congelado.
- Nenhuma alteração de código foi feita por causa desta auditoria.
