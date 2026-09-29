# AION Core — Handoff Noturno 2026-09-29

## Objetivo operacional

Este handoff existe para reduzir ao mínimo a intervenção humana durante a execução noturna do AION/Núcleo.

O operador deve conseguir iniciar o trabalho no Cursor uma vez e deixar a frente avançar por blocos grandes durante a noite, sem pedir confirmação a cada passo seguro.

## Prioridade absoluta

1. AION
2. Núcleo
3. Segurança, verdade, memória/checkpoint, recovery, workers e autonomia controlada
4. Testes e integração da pilha
5. Somente depois: outras áreas do AtlasQuant

Não desviar para Interface, Radar, Trading, Studio, Academy ou features novas enquanto houver regressão ou hardening pendente no AION Core.

## Base conhecida

Base comum atual:

`chatgpt/aion-checkpoint-write-reconciliation-v1`

HEAD da base:

`4c135073ff59a05dcca07079fa109bd897a65dec`

Draft PR base:

- #337 — AION Core checkpoint write reconciliation V1

Frentes irmãs preparadas sobre a #337:

- #338 — `chatgpt/aion-global-worker-write-reconciliation-v1`
  - Global Worker: CAS/read-after-write, receipt, reconciliation, no automatic retry.
  - Readiness remoto observado: SUCCESS.
- #342 — `chatgpt/aion-global-fencing-release-hardening-v1`
  - Empilhada sobre a #338.
  - Release do lease exige owner + lease token + fencing token.
  - runtime_id global estrito; fence release failure bloqueia persistência final.
- #343 — `chatgpt/aion-global-inflight-idempotency-v1`
  - Empilhada sobre a #342 e é a ponta preferida da cadeia Global Worker.
  - Persiste `inflight_tick` no claim para impedir reexecução após persistência terminal ambígua.
  - Novo tick bloqueia antes do executor quando existe inflight não reconciliado.
- #339 — `chatgpt/aion-worker-lease-hardening-v1`
  - Worker de sessão: corrige NameError em arm_worker, valida runtime_id e max_jobs no boundary correto.
  - Mantém multi_instance_safe=false.
- #340 — `chatgpt/aion-recovery-outcome-hardening-v1`
  - Recovery só declara restored_revision quando save+verify foram realmente confirmados.

Todas devem permanecer Draft até validação integral.

## Regra de execução noturna

Trabalhar de forma autônoma por blocos grandes.

NÃO pedir confirmação para:

- leitura e auditoria;
- criação de branch de trabalho;
- testes locais/offline;
- correção de regressão;
- hardening fail-closed;
- refatoração pequena necessária para testes;
- commits;
- criação/atualização de Draft PR;
- documentação técnica;
- novos testes adversariais offline;
- integração temporária das branches irmãs em uma branch de validação;
- reexecução de testes após correção.

PEDIR confirmação e PARAR antes de:

- merge em main;
- deploy;
- mudança de ruleset/admin;
- uso de segredo real;
- API/serviço pago;
- cobrança;
- publicação externa;
- trading real;
- ativação real de worker global;
- mudança irreversível de runtime;
- exclusão destrutiva;
- alteração que amplie autoridade/permissão.

## Bloco 1 — Integração noturna

Criar uma branch temporária de integração a partir da #337, por exemplo:

`cursor/aion-night-integration-2026-09-29`

Integrar de forma não destrutiva as frentes:

1. #343 (já contém #338 + #342; usar como ponta da cadeia Global Worker)
2. #339
3. #340

Não retargetar nem mergear em main.

Se houver conflito, resolver preservando:

- fail-closed;
- exact boolean;
- no automatic retry;
- receipt não é autoridade;
- write/readback ambíguo exige reconciliation;
- multi_instance_safe continua false até existir prova distribuída real;
- restore só é confirmado após persistência verificada.

## Bloco 2 — Validação obrigatória

Rodar primeiro testes direcionados:

```bash
python -m unittest test_atlasquant_aion_memory.py
python -m unittest test_atlasquant_aion_global_worker.py
python -m unittest test_atlasquant_aion_worker_runtime.py
python -m unittest test_atlasquant_aion_recovery.py
python -m unittest test_atlasquant_aion_background_executor.py
```

Depois:

```bash
python tools/aion_redteam_runner.py
python -m unittest discover
python -m compileall -q .
git diff --check
```

Se existir falha:

1. diagnosticar;
2. corrigir somente a causa;
3. criar teste de regressão quando apropriado;
4. rerodar o teste direcionado;
5. rerodar a suíte relevante;
6. continuar sem pedir autorização.

Não esconder falha por skip, expectedFailure novo ou relaxamento de assert sem justificativa técnica explícita.

## Bloco 3 — Próximos hardenings do Núcleo

Depois de a integração ficar verde, avançar nesta ordem:

1. Concorrência e fencing do Global Worker.
2. Recovery operacional e estados ambíguos de persistência.
3. Garantia de idempotência entre lease/receipt/retry.
4. Partial checkpoint writes e reconciliação.
5. Resource bounds: payload, fan-out, depth, retries, history e filas.
6. Isolamento tenant/workspace/cache.
7. RT19 residual: dependências opcionais do Core.
8. Supply-chain/reproducibilidade somente onde ainda houver GAP real.
9. Novos red-team tests para qualquer boundary corrigido.

Antes de criar mecanismo novo, procurar implementação equivalente existente e reutilizar.

## Política de custo noturno

CUSTO ZERO por padrão.

Não usar:

- OpenAI/Anthropic/provider pago;
- TTS/video pago;
- marketplace;
- API externa cobrada;
- cloud extra paga;
- trading/broker;
- serviço premium.

Pode usar local/offline e CI já disponível no repositório.

Se um teste depender de serviço externo, mockar quando o objetivo for contrato interno. Não fingir que mock prova produção.

## Política de autonomia

O Cursor pode continuar de um bloco seguro para o seguinte sem esperar resposta humana.

Fluxo esperado:

`inspect -> test -> diagnose -> fix -> regression test -> retest -> commit -> Draft PR -> next safe block`

Não parar apenas porque um bloco foi concluído.

Parar somente quando:

- precisa autorização humana;
- precisa segredo/credencial;
- precisa serviço pago;
- exige deploy/produção;
- exige merge em main;
- encontrou decisão arquitetural irreversível com duas opções equivalentes;
- ambiente externo impede validação e não há alternativa offline segura.

## Critério de verdade

Nunca afirmar:

- teste verde sem execução;
- persistência confirmada sem readback;
- restore concluído sem verified=true;
- worker global ativo sem evidência;
- multi-instance safe sem mecanismo distribuído validado;
- 24x7 sem runtime contínuo observado;
- produção/deploy sem prova.

UNKNOWN é preferível a uma conclusão inventada.

## Entrega da manhã

Ao terminar ou atingir um stop condition, deixar um único relatório curto com:

- branch final;
- HEAD SHA;
- Draft PR final;
- branches/PRs integradas;
- testes rodados e resultados;
- falhas corrigidas;
- itens ainda BLOCKED/UNKNOWN;
- próximo passo exato;
- confirmação explícita: merge/deploy/trading/paid provider = NÃO.

## Prompt único para colar no Cursor

Copie somente o bloco abaixo:

> Continue o AION/Núcleo a partir de `docs/aion/AION_NIGHT_RUN_HANDOFF_2026-09-29.md`. Execute o plano noturno inteiro por blocos grandes, sem me pedir confirmação entre etapas seguras. Prioridade absoluta AION + Núcleo. Integre as Drafts #343, #339 e #340 sobre a #337 numa branch temporária, valide, corrija regressões, rode red-team + suíte completa e continue os hardenings listados no handoff enquanto forem seguros. Custo zero por padrão. Não fazer merge em main, deploy, serviço pago, segredo real, publicação, ativação real de worker ou trading. Em caso de falha, diagnostique, corrija, teste e continue. Pare somente nos stop conditions descritos no handoff e deixe relatório final da manhã.
