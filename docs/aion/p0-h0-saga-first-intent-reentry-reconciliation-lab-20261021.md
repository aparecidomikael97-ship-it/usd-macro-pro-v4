# AION P0/H0 — Saga não pode promover uma primeira tentativa Outbox existente a novo estágio

**Data:** 21/10/2026. **PR Draft LAB; Worker OFF, HARD NO-GO, ZERO_AUTO_RESEND, 0/6 P0 homologados.**

## Defeito descoberto na revisão cruzada do stack Draft

As PRs #1385→#1402 implementaram recuperação, consistência local de leitura, integridade de enfileiramento e rollback transacional. Porém um cenário de **divergência entre o estado da Saga e o Outbox** permanecia:

1. `ExecutionSagaCoordinator.enqueue_next()` encontra sua Saga e primeira etapa ainda `PLANNED/PENDING`.
2. Antes dessa chamada, um registro da **mesma primeira intenção** já está persistido no Outbox (por exemplo, devido a restauração parcial, código anterior não atômico ou corrupção local). Ele pode estar `PENDING`, `CLAIMED`, `RETRY`, `UNCERTAIN`, `SENT`, `CONFIRMED`, `REVOKED`, `BLOCKED_PRODUCER`, `BLOCKED_REAPPROVAL` ou `FAILED`, sem qualquer recibo externo confiável.
3. Como `Outbox.enqueue()` calcula a mesma chave com os mesmos atributos, ele devolve corretamente `enqueue_state=IDEMPOTENT` e o estado local da intenção anterior. Isso é apropriado para **consulta de duplicata**, não significa `NO_EFFECT_FENCED`.
4. A Saga, porém, ignorava `enqueue_state`, marcava sua etapa `ENQUEUED` e seu estado `RUNNING`, gravava um evento de estágio e devolvia sucesso. O SQLite podia permanecer internamente coerente, embora a etapa restabelecida tivesse histórico anterior, possivelmente incerto ou já despachado.

**Não há demonstração de reenvio real nem de execução por fornecedor:** Worker permanece desligado e o adaptador externo não pode operar sem matrícula independente. Mas aceitar o mesmo primeiro histórico externo para reiniciar a Saga é uma violação local do contrato H0; nunca é correto tratar IDEMPOTENT como uma primeira operação nova.

## Evidência RED-first

`tests/test_aion_p0_h0_saga_existing_first_intent_reentry_lab.py`: 14 cenários com `SQLiteChatStore`, `ExecutionOutbox`, `ExecutionSagaCoordinator` e `CumulativeAuthorityBudget` reais, com mesmo escopo e mesma conexão SQLite descartável. Cria Saga com primeira etapa PENDING e, antes de chamar `enqueue_next`, persiste no Outbox a mesma primeira intenção com parâmetros, escopo e digest idênticos; em seguida varia seu estado local.

No commit anterior ao patch `8bedc1e5cbf7a46b35149cc79d4e7058e232ab2f`, [CI #39634396834](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39634396834) demonstrou **11 FAIL em 14 testes Ubuntu**, todos relativos à ausência de recusa para primeira intenção já existente, incluindo `UNCERTAIN`, `SENT` e `CONFIRMED`. Os casos de sucesso normal, lookup idempotente direto no Outbox e negação da segunda chamada à Saga permaneceram.

## Correção de código real, sem relaxamento da autoridade

Em `atlasquant_aion_execution_saga.py`, **imediatamente após** o retorno de `self.outbox.enqueue`, porém **antes** de qualquer `UPDATE` de etapa, leitura/registro de eventos ou commit:

- Exigir `enqueue_state=ENQUEUED` como estágio verdadeiramente novo (nunca `IDEMPOTENT`).
- Exigir `state=PENDING`, `local_integrity=MATCH`, `attempts=0`, sem `dispatch_started_at` e sem `effect_ref`.
- Se alguma condição falhar, `PermissionError("SAGA_FIRST_INTENT_REENTRY_REQUIRES_RECONCILIATION")` e rollback da transação externa já aberta por `Saga.enqueue_next`. Nenhuma etapa é promovida e nenhuma evidência de ausência é inferida.
- `ExecutionOutbox.enqueue` **continua podendo responder IDEMPOTENT para consultas legítimas**. A correção é na fronteira de admissão da Saga e não modifica o contrato público geral de idempotência.
- A lógica do plano/evento/cadeia continua local e não fornece prova de produtor, efeito ou autorização HUMAN_OWNER.

## Invariantes e limitações

- Testar que `UNCERTAIN`/ `SENT` persistidos não autorizam novo estágio e que, diante de uma duplicata `PENDING` mesmo limpa, a primeira operação **não é considerada nova**.
- O rollback preserva integralmente tanto a Saga como o registro original do Outbox, sem criar uma segunda intenção ou incrementar tentativas.
- Nenhum PASS de laboratório identifica se o fornecedor externo executou uma primeira operação, nem atesta `NO_EFFECT_FENCED`, nonce independente, atestado de versão/latest head, autenticidade Ed25519 independente, custódia fora do host ou recuperação após rollback físico.
- A CI dedicada executa **14 novos + 222 regressões já existentes** por SO: 236 por sistema operacional, 472 execuções Windows+Ubuntu se todas PASS. Quality canônica de 588 módulos/6.895 testes e Security A74 365 serão reexecutadas no HEAD final **sem alterar seleção, critérios, skips ou waivers**; a referência anterior era **51 FAIL/34 ERROR**.
- Não mesclar, não implantar, não ativar Worker, não criar contas/credenciais de fornecedor e não gerar novas despesas. O status permanece **HARD NO-GO, 0/6 P0 homologados**.
