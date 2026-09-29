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
- #346 — `chatgpt/aion-global-inflight-reconciliation-assessor-v1`
  - Empilhada sobre #345 e é a ponta preferida atual da cadeia Global Worker.
  - Contém #338 + #342 + #343 + #345.
  - Cruza inflight + work intent + receipts em diagnóstico read-only para a manhã.
  - Nunca limpa, reexecuta ou autoriza retry automaticamente.
- #347 — `chatgpt/aion-global-inflight-resolution-ceremony-v1`
  - Empilhada sobre #346 e é a ponta preferida atual da cadeia Global Worker.
  - Contém #338 + #342 + #343 + #345 + #346.
  - Adiciona resolução staging-only para casos comprovadamente claros, sempre com aprovação explícita.
  - Ambiguous/partial/inconsistent/unsafe continuam bloqueados.
- #348 — `chatgpt/aion-core-resource-bounds-v1`
  - Empilhada sobre #347 e é a ponta preferida atual do AION/Núcleo.
  - Contém a cadeia Global Worker até #347.
  - Fecha materialização não limitada em Durable Tasks / Observability / Knowledge Graph.
  - Mantém os mesmos limites e preserva a semântica de dados recentes.
- #349 — `chatgpt/aion-memory-optional-business-adapter-v1`
  - Empilhada sobre #348 e é a ponta preferida atual do AION/Núcleo.
  - Contém toda a cadeia anterior até #348.
  - Memory/Recovery continuam operacionais com seção Business vazia mesmo sem o módulo Negócios.
  - Business real sem adapter fica UNKNOWN/write_safe=false; nenhum dado é apagado silenciosamente.
- #350 — `chatgpt/aion-tenant-write-gate-hardening-v1`
  - Empilhada sobre #349 e é a ponta preferida atual do AION/Núcleo.
  - Contém toda a cadeia anterior até #349.
  - Tenant Store exige `approved is True` e rejeita memória de tenant estrangeiro mesmo com aprovação exata.
  - O store permanece planning-only, sem network/write automático.
- #352 — `chatgpt/aion-supply-chain-residual-hardening-v1`
  - Empilhada sobre #350 e é a ponta preferida atual do AION/Núcleo.
  - Contém toda a cadeia anterior até #350.
  - Fecha installs Python soltos nos workflows residuais; Actions continuam pinadas por SHA.
  - Adiciona contrato automático de pinning no Security Gate e Quality Suite.
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

1. #352 (já contém a cadeia até #350 e o hardening de supply chain; usar como ponta AION/Núcleo)
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

Preferir o runner noturno único, local/offline e de custo zero:

```bash
python tools/aion_night_validation.py --full --report aion-night-validation-report.json
```

Ele executa, sem parar na primeira falha:

- suíte crítica de Memory / Global Worker / Worker Runtime / Recovery / Background Executor;
- suítes adversariais reais: Security Adversarial, Hardening, Post Audit, Chaos Recovery, Core Independence e Global Worker Readiness;
- `python -m unittest discover`;
- `python -m compileall -q .`;
- `git diff --check`;
- relatório JSON consolidado para diagnóstico/correção.

O runner não instala dependências, não usa rede, não chama provider, não faz deploy, merge, publicação, runtime mutation ou trading.

Para diagnóstico rápido durante uma correção, pode usar:

```bash
python tools/aion_night_validation.py --quick --report aion-night-validation-quick.json
```

Antes de encerrar o turno, sempre voltar ao modo `--full`.

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

> Continue o AION/Núcleo a partir de `docs/aion/AION_NIGHT_RUN_HANDOFF_2026-09-29.md`. Execute o plano noturno inteiro por blocos grandes, sem me pedir confirmação entre etapas seguras. Prioridade absoluta AION + Núcleo. Integre as Drafts #352, #339 e #340 sobre a #337 numa branch temporária, rode `python tools/aion_night_validation.py --full --report aion-night-validation-report.json`, corrija regressões e continue os hardenings listados no handoff enquanto forem seguros. Custo zero por padrão. Não fazer merge em main, deploy, serviço pago, segredo real, publicação, ativação real de worker ou trading. Em caso de falha, diagnostique, corrija, teste e continue. Pare somente nos stop conditions descritos no handoff e deixe relatório final da manhã.

## Achados já revalidados antes do próximo hardening

- RT04 review binding já coberto na ponta atual: tenant/workspace/task/plan divergentes bloqueiam com regressão específica.
- Session Memory / Specialist Session são projeções por chamada e não mantêm cache global mutável de memória pessoal.
- Tenant Store usa path credential-bound por tenant; a fronteira de aprovação textual foi endurecida na #350.
