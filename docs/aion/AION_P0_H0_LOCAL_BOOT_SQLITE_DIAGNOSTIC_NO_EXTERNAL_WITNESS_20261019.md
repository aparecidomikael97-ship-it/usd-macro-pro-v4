# AION P0 H0 — Diagnóstico real de SQLite no boot, **SEM testemunha externa**

19/10/2026 | **Somente LAB e leitura de um SQLite local real**. Estado operacional: **0/6 P0 homologados, HARD NO-GO, Worker OFF, ZERO_AUTO_RESEND**, sem merge/deploy/fornecedor/custo.

## Escopo executável da entrega

`atlasquant_aion_p0_h0_sqlite_startup_observer_lab.py` fornece:
- `observe_h0_sqlite_first_effect_lab(database_path, _caller_witness_claim=None)`, diagnóstico em SQLite temporário ou indicado explicitamente; utiliza URI `mode=ro`, `PRAGMA query_only=ON`, `quick_check(1)`, `sqlite_schema`, contagens agregadas de estados da tabela `action_outbox`.
- Relatório local sem nome de clientes, owner, tenant, autorização, conteúdo ou telefone. Saída `state=BLOCKED`, `blocker=INDEPENDENT_H0_WITNESS_NOT_ENROLLED`; `first_attempt_cleared=false`, `worker_arming_allowed=false`, `automatic_retry_allowed=false`, `external_highwater_compared=false`, `local_rollback_ruled_out=false` **para QUALQUER estado da base ou alegação do chamador**.
- Interface de linha de comando: `python -B atlasquant_aion_p0_h0_sqlite_startup_observer_lab.py CAMINHO_DO_SQLITE`. Imprime JSON e sai com **código 2, nunca 0** (para não ser confundido com READY em pipelines). O comando não executa módulo de envio, fornecedor, Worker ou operação real.
- Difere de `activation_readiness_snapshot` (Global Worker) que já é `BLOCKED` por `INDEPENDENT_SOURCE_WITNESS_NOT_ENROLLED`. Este observador analisa estados de um arquivo SQLite concreto sob `H0`. **Não está conectado ao boot, Worker ou Outbox produtivos**; não substitui o gate de produtor atual.

### Teste mais revelador

Um banco temporário contém uma intenção `PENDING`, com backup SQLite; o teste escreve um `UNCERTAIN` fictício e verifica essa versão, fecha conexão, **restaura o backup com `shutil.copyfile` intencionalmente contornando a API oficial** e reabre `PENDING`. O diagnóstico antes/depois fica **BLOCKED** em ambos. Quando o backup antigo não carrega o marcador `UNCERTAIN`, a leitura local não tem como provar que esse evento se perdeu. **Não afirmar que rollback foi detectado** (`local_rollback_detected=false`) nem que foi descartado (`local_rollback_ruled_out=false`). O código original A118 ainda não executa `adapter.send` sem produtor independente matriculado.

## O que deve existir antes de qualquer liberação futura

1. **Custodiante autenticamente externo:** armazenamento monotônico mantido em domínio operacional e credenciais diferentes do PC, VM/backup, GitHub LAB e agente Executor. Não aceitar um JSON ou `verified=true` do mesmo chamador, nem SHA gerado pelo próprio AION como prova de custódia.
2. **Identidade e escopo:** chave pública autenticada e rotacionável do custodiador, tenant, workspace, recurso, intenção imutável, owner realmente inscrito, idempotency key local, epoch, sequence, digest de decisão/estado e nonce consumido e atestado uma única vez. Identidade/conta do prestador deve ser verificada fora da entrada do caller.
3. **Semântica linearizável:** comparação e troca monotônica por intento antes da primeira ação externa, gravação durável *externa* do marcador `ATTEMPT_STARTED` ou terminal `NO_EFFECT_FENCED` com prova do fornecedor, resposta assinada e verificação de escopo. Timeout do custodiador significa **UNKNOWN**, nunca retry. Conexão e relógio locais não são fonte de verdade independente.
4. **Reinício / rollback:** ao abrir o SQLite, qualquer ausência/falha/epoch antiga/replay/fork/nonce duplicado/conflito/revogação ou diferença de high-water bloqueia novos primeiros efeitos. O observador atual é diagnóstico: precisa futuramente ser inserido em guard de primeira intenção e no caminho real de startup, depois de matrícula autenticada.
5. **Primeiro efeito externo:** Twilio Messaging API não oferece token idempotente de CREATE; busca por número/SID/time range não comprova ausência. Independent high-water local/externo NÃO equivale a um recibo assinado de produtor ou prova terminal de no-effect. Worker, reenvio e fila continuam bloqueados até garantir ambos.
6. **Validação antes de GO:** testes de poder físico/reboot Windows, SQLite WAL + crash, duas instâncias, restore de volume/VM, concorrência CAS, provas cripto e custódia externas, Security/Quality canônicas e auditoria externa independente; sem custo/conta/integracao real sem aprovação.

## Limites e riscos metodológicos

- O método não pode indicar sucesso, nem recebe um backend autenticado. Um objecto Python de forma hostil em `_caller_witness_claim` é intencionalmente ignorado, não avaliado.
- A leitura SQLite `mode=ro` não altera o banco por SQL, mas SQLite em WAL pode depender de/gerenciar arquivos auxiliares de journaling; não prometer ausência absoluta de alterações do sistema de arquivos.
- A base pode ser trocada DEPOIS da leitura (TOCTOU). Não há pinagem externa de conteúdo, proteção da integridade do executável, startup obrigatório nem isolamento de namespaces/hosts.
- Contagens e estados são **observações não autenticadas**, inclusive quando `quick_check=ok`; um adversário pode adulterar DB e continuar estruturalmente coerente.
- Uma aprovação de produto ou P0 de segurança não pode ser baseada nesta bateria isolada. Não usar `PASS` como sinônimo de TRUST/GO.

**Decisão:** manter o hard stop global e pedir seleção/autorização de custodiante independente apenas quando requisitos e orçamento forem avaliados. Até lá, pode-se expandir simulações, mas a lacuna P0 de antirollback **não pode ser honestamente fechada**.
