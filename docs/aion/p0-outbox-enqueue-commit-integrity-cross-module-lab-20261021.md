# AION P0 — revisão cruzada: commit atômico de Outbox + Saga sob adulteração SQLite

**21/10/2026 · LAB / PR Draft · HARD NO-GO, Worker OFF, ZERO_AUTO_RESEND · 0/6 P0 homologados.**

## Cadeia realmente revisada

Conferidas via GitHub as PRs Draft empilhadas #1385, #1394, #1395, #1396, #1397, #1398, #1399, #1400 e #1401: todas continuavam OPEN/Draft/merged=false e cada base LAB correspondia à branch anterior. O novo branch nasce do HEAD `619acc08d4738584381d9d16a1421d3ebc0a06c2` de #1401, que inclui os fixes anteriores no mesmo código sem merge em main.

## Falha real entre os módulos

`ExecutionOutbox.enqueue()` grava `action_decisions` e `action_outbox` com `BEGIN IMMEDIATE` ou `SAVEPOINT aion_outbox_enqueue` quando chamado pela Saga. Antes desta correção:

- Na inserção de uma **nova** intenção, o método dava `COMMIT` ou `RELEASE SAVEPOINT` **antes** de fazer `get(idempotency_key)`.
- Após #1400, `get()` marca uma decisão adulterada `local_integrity=MISMATCH` e `decision={}`, em vez de entregar payload/autoridade; mas `enqueue()` devolvia `enqueue_state=ENQUEUED` **mesmo com essa quarentena**.
- Sob chamada de `ExecutionSagaCoordinator.enqueue_next`, o código da #1398 revalida o estado local da Saga, porém não verifica diretamente `local_integrity` da nova linha do Outbox. A Saga podia assim concluir seu estágio `ENQUEUED` com decisão forjada por um gatilho SQLite `AFTER INSERT`.
- O mesmo gatilho podia mudar a linha de Outbox para `CLAIMED/CONFIRMED`, inflar tentativas, definir marcador de despacho ou inserir `action_effects` falso antes de `COMMIT`, sem que `enqueue()` reprovasse o resultado.
- No caminho idempotente de duplicata, o `get()` também ocorria depois do término da transação/SAVEPOINT. A correção preserva o bloqueio existente de documento em quarentena e o transfere **para antes** do encerramento da transação.

**Modelo de ameaça:** gatilho ou corrupção local com capacidade de editar SQLite dentro da mesma transação. Não é prova de exploração remota nem de que algum efeito foi enviado a fornecedor. A correção bloqueia o estágio local comprometido, não torna hashes de SQLite prova independente.

### Prova RED-first

Arquivo `tests/test_aion_p0_outbox_enqueue_commit_integrity_lab.py` com 15 cenários, SQLiteChatStore/ExecutionOutbox/ExecutionSagaCoordinator/CumulativeAuthorityBudget reais em SQLite descartável. Gatilhos SQL adulteram JSON de decisão, `authorization_ref`, deadline, `state`, `attempts`, lease, `dispatch_started_at` e `action_effects` durante a inserção. Testa também chamada sob `BEGIN IMMEDIATE` de terceiro, enfileiramento íntegro standalone e Saga com plano/eventos íntegros.

**RED sem patch:** [workflow #39632989529](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39632989529), commit `3c2d7d92b7a9afd58852f85331be3b29a38d5367`, **12 FAIL dos 15 no Ubuntu**, indicando que os INSERTs corrompidos ou a Saga concluíam onde deviam falhar.

## Correção mínima e transacional

Em `atlasquant_aion_execution_outbox.py`:

1. Após os dois INSERTs mas ainda **antes de COMMIT/SAVEPOINT RELEASE**, `get()` lê a nova linha. Exige `local_integrity=MATCH`, documento de decisão idêntico ao material calculado originalmente e estágio inaugural exatamente `PENDING`, `attempts=0`, leases/efeito/despacho/erro vazios.
2. Consulta específica `action_effects` para a chave exige inexistência de qualquer recibo local já criado pela inserção (um efeito real não se comprova com registro local, e antes do claim nenhum registro deveria existir).
3. Qualquer divergência => `PermissionError("OUTBOX_ENQUEUE_LOCAL_INTEGRITY_MISMATCH")` e rollback integral, inclusive do INSERT de Outbox e de decisão. Se a Saga é o chamador, usa `ROLLBACK TO SAVEPOINT`, e a Saga faz rollback da transação externa. Se for standalone, `ROLLBACK` na própria transação.
4. No caminho de duplicata idempotente, a checagem `local_integrity=MATCH` passa a acontecer **antes** de terminar a transação/SAVEPOINT (mantendo `OUTBOX_LOCAL_DECISION_INTEGRITY_MISMATCH` como razão existente).
5. Enqueue íntegro e atualização posterior permitida por gates locais continuam iguais. Não altera/admite `dispatch_claimed`, `_confirm`, `reconcile`, Worker ou fornecedor.

## Segurança, testes e critérios de saída

Executar **15 novos + 207 regressões LAB** (integridade de lease, quarentena, transação pai, Saga CAS, isolamento tenant, SQLite recovery e H0 A79) em **Windows e Ubuntu = 222 testes por SO, 444 execuções** quando concluídos. Rodar Quality canônica de 588 módulos/6.895 testes e Security A74 365 sem skips/waivers, e comparar os nomes completos FAIL/ERROR com baseline #1401 (51 FAIL e 34 ERROR). Se alguma execução vier RED, NÃO contabilizar como correção homologada.

**Limite essencial:** esta garantia é de atomicidade e consistência de **um SQLite local**. Ela não detecta rollback de todos os domínios, não prova a identidade HUMAN_OWNER, custódia de nonce externa, readback head latest, recibo causal de produtor ou `NO_EFFECT_FENCED`. `ZERO_AUTO_RESEND` permanece incondicional. Sem merge, deploy, Worker, API externa ou gasto adicional.
