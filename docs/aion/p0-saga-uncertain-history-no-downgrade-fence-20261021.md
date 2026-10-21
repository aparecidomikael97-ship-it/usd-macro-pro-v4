# AION P0/H0 — Estado incerto NÃO regride para execução (21/10/2026)

**STATUS: LAB/PR Draft · HARD NO-GO · 0/6 P0 homologados · Worker OFF · ZERO_AUTO_RESEND.**

## Falha reproduzida ANTES de qualquer correção

Partindo da PR #1392 (`65379e18134a98450a9d54a895f7119d1febde87`), usei `ExecutionSagaCoordinator` e `ExecutionOutbox` reais, em SQLite descartável. A etapa é marcada `UNCERTAIN` e a Saga `RECONCILIATION_REQUIRED` somente depois de provar que `dispatch_claimed` NEGOU `INDEPENDENT_PRODUCER_NOT_ENROLLED` antes de chamar o adapter. Não houve send real.

Em seguida, um rollback LOCAL simulado da projeção Outbox altera o mesmo `idempotency_key` para `PENDING`, `RETRY` ou `CLAIMED` sem limpar o histórico da Saga. Antes da correção, `sync_forward_outcome` aceitava cada estado, regravava a etapa `ENQUEUED` e regredia a Saga a `RUNNING`. Era possível perder o bloqueio local `RECONCILIATION_REQUIRED` sem qualquer prova de ausência de efeito.

Evidência RED: GitHub Actions [run #39602580850](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39602580850), commit `ce0638ac69e2b222947019b83947acebef41fb40`: **três falhas diretas** `PermissionError not raised` (PENDING/RETRY/CLAIMED). Outros 9 ERROR do módulo legado de Saga foram arrastados pelo discovery `unittest` original; isso foi corrigido alterando apenas o import no teste novo para importar o módulo da fixture em vez de importar sua classe `TestCase` diretamente. Os nove erros são preexistentes, não introduzidos pelo patch.

## Correção produtiva restritiva (sem efeito externo)

Arquivo `atlasquant_aion_execution_saga.py`, função `sync_forward_outcome`, após obter o SQLite `BEGIN IMMEDIATE`, verificar integridade da Saga e validar snapshots sob lock, e **antes** da escrita do estado, evento ou orçamento:

- Se a fonte Outbox apresentar `PENDING`, `RETRY` ou `CLAIMED`, mas a Saga persistir `RECONCILIATION_REQUIRED` ou `PRODUCER_ENROLLMENT_REQUIRED`, negar com `PermissionError("SAGA_UNCERTAIN_HISTORY_REGRESSION_NO_EXTERNAL_FENCE")`.
- Negar igualmente se a própria etapa da Saga estiver em `UNCERTAIN` ou `BLOCKED_PRODUCER`, mesmo com um estado mais amplo da Saga diferente.
- Não aceitar flags de `verified`, aprovações do chamador, `retryable`, reset manual ou assinaturas da própria aplicação para liberar essa transição.
- Não tocar no Outbox produtivo, adaptadores, Worker, configuração de ativação ou fontes externas.

**Limite:** isso impede regressão enquanto a memória/eventos locais da Saga sobre a incerteza sobrevivem. Um rollback que restaure **a base SQLite inteira e a cadeia de eventos juntas** não é detectado independentemente por essa regra. Para homologação P0/H0 ainda se exige custódia monotônica off-host, prova de primeira tentativa/resposta tardia e vínculo com fornecedor confiável.

## Testes novos e cobertura canônica

`test_aion_p0_saga_uncertain_projection_no_regression_lab.py` — **7 novos testes**, usando o mesmo `SQLiteChatStore`, Saga e Outbox reais:
1–3. Saga `RECONCILIATION_REQUIRED` nega regressão para PENDING, RETRY, CLAIMED.
4. Observação repetida de UNCERTAIN não altera a quarentena nem permite nova claim.
5–7. Saga `PRODUCER_ENROLLMENT_REQUIRED` nega regressão para PENDING, RETRY, CLAIMED.

Asserts: estado Saga inalterado, Outbox sem edição pela reconciliação negada, mesmo snapshot de autoridade/custo, `effect_count=0`, adapter `send_calls=0`, próximo passo não enfileirado. Os nomes/casos legados permanecem no mesmo estado histórico; não há skip/xfail/waiver.

O novo arquivo é listado explicitamente na Quality canônica, para não criar outro erro de cobertura. A workflow dedicada Windows+Ubuntu inclui os sete testes novos, as negativas A38/A39 (quatro subcenários), o inventário de 85 casos, a matriz de 32 casos e os controles H0 A79.

## Aceite objetivo e veredito

Exigir **CI dedicated PASS Windows+Ubuntu** e **Quality completa no SHA final**. Comparar 50 FAIL/15 ERROR históricos; o aumento de sete testes no total é **nova proteção**, não redução artificial do baseline.

A correção é uma defesa **local** real, mas **não** torna o núcleo apto a ativar Worker ou executar Saga em ambiente produtivo.

**0/6 P0 homologados · HARD NO-GO · sem merge/deploy/Worker/conta/custo novo.**
