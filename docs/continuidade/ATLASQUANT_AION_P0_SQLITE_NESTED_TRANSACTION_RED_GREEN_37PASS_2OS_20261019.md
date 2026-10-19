# AtlasQuant / AION — P0 SQLite: transação aninhada recusa explícita RED→GREEN (19/10/2026)

**Classificação:** CORREÇÃO PONTUAL DE COMPATIBILIDADE EM LAB. **Não** homologar os dois P0 SQLite nem qualquer outro P0. Estado inalterado: **0/6 P0 homologados; HARD NO-GO; Worker OFF; ZERO_AUTO_RESEND; sem merge/deploy/gastos.**

## Origem e impacto
No A118 original, `ExecutionOutbox.release_expired_claims()` chamava `BEGIN IMMEDIATE` diretamente. Quando um chamador Saga/host detinha transação ou SAVEPOINT ativo na MESMA conexão SQLite, `release_expired_claims()` e, indiretamente, `claim_next()` falhavam com a mensagem genérica `sqlite3.OperationalError: cannot start a transaction within a transaction`.

**Pormenor importante:** no código original esse `BEGIN IMMEDIATE` fica ANTES do bloco `try/except` que poderia executar `rollback()`. Portanto a auditoria NÃO demonstrou que esse erro genérico desfazia a transação do chamador. Não alegar perda de transação como defeito pré-correção. O defeito documentado é **incompatibilidade e ausência de negação explícita tipada**.

## Alteração mínima
- Branch isolada `lab/aion-p0-sqlite-nested-tx-safe-denial-20261019` derivada do laboratório de 30 casos `5c7544bff377884ba015da9cd8db1b3fc25e6a0a`.
- Nova matriz de 7 casos `test_aion_p0_sqlite_nested_transaction_denial_lab.py`, commit `e2859da075adfa683bcce86c13a4e8b33381fd07`. Os 7 contratos foram escritos antes do patch.
- GitHub workflow `.github/workflows/aion-p0-sqlite-parent-transaction-lab.yml`, commit inicial `20470b830ca7736c668a2e660d9142946e684edb`; atualização de checkout `c810cf5749bdd5613e81efbc4b9c296322fee1d8` para obter o ancestral A118 em checkout `fetch-depth:30` (a primeira CI falhou antes dos testes porque checkout superficial não continha o ancestral).
- **RED real:** [Actions #39314063834](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39314063834), Ubuntu job `118270838901`: **5 ERROR entre 7 testes**, todos `sqlite3.OperationalError: cannot start a transaction within a transaction`; 2 passaram. Esse RED testa falha de contrato de diagnóstico, **não** demonstra rollback de transação externa.
- **Patch:** commit `7e7f3fad85ceab3274510958897948d7afd9f2f1` altera somente `atlasquant_aion_execution_outbox.py` na branch LAB, introduzindo no início de `release_expired_claims()`:
  ```python
  if self.db.in_transaction:
      raise RuntimeError("OUTBOX_NESTED_TRANSACTION_UNSUPPORTED")
  ```
  Esse guard executa **antes** de `BEGIN IMMEDIATE`, sem escrita, `commit`, `rollback` ou emissão de autoridade. `claim_next()` reutiliza o guard porque chama `release_expired_claims()` antes de abrir sua transação própria.
- Ajuste de expectativas **apenas no teste novo** `test_aion_p0_original_sqlite_compat_concurrency_restore_lab.py`, commit `df8cd72938a6d91eeb681211056b2ecdf2a3a267`: muda o diagnóstico esperado para a recusa explícita, mantendo verificação de `in_transaction`, `PENDING`, `attempts=0`. Nenhum teste canônico A118 foi editado.
- Código do `aion_chat/store.py` **intacto**: SHA Git blob `6df8ad55673acaca6eeeb0bc3e3898d7a10b08ba`; commit-base A118 de Outbox `c62fab663c6349d7320f7843c8d09587c514426b`, blob `6bad4ee9ba5909bbb49c609a5d3ac3c05c16ab83`; ambos verificados pelo workflow.

## Evidências pós-correção
[Actions #39314233634](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39314233634), `status=completed`, `conclusion=success`, HEAD `df8cd72938a6d91eeb681211056b2ecdf2a3a267`.

| Seleção testada | Ubuntu job 118271426176 | Windows job 118271426348 |
|---|---|---|
| 7 contratos novos: recusa explícita, preserve tx/rollback/commit caller, SAVEPOINT, sem regressão claim, enqueue | **7 PASS** | **7 PASS** |
| 8 casos A118 de concorrência, thread e restore de backup anterior | **8 PASS** | **8 PASS** |
| 4 A110 de resultados ambíguos + 18 A63/A64/A65 Saga/Outbox | **22 PASS** | **22 PASS** |
| **Total** | **37 PASS** | **37 PASS** |

**74 execuções de casos / 37 casos distintos**. Não confundir com histórico Quality/Security completo.

## Limites e pendências
1. Esta patch torna explícita a **recusa de uma transação aninhada**; não implementa composição transacional de `claim_next()`. O chamador ainda precisa invocá-la fora de sua transação; `enqueue()` permanece operando com SAVEPOINT quando apropriado. Aplicação só em LAB, não em `main`.
2. A passagem de conexão entre threads ainda causa `sqlite3.ProgrammingError` por política `check_same_thread=True`. Cada thread com conexão própria é o padrão seguro investigado. Não habilitar `check_same_thread=False` sem serialização formal. Não alegar que P0 de thread foi corrigido.
3. Restore de backup SQLite íntegro antigo pelo método `SQLiteChatStore.restore_from_backup()` ainda pode apagar o marcador LOCAL `UNCERTAIN`, como o teste histórico demonstra. Requer **high-water comprovado fora do domínio de restauração** e controle de origem/custódia independente, não um segundo arquivo na mesma VM.
4. Os controles de produtor A118 continuam negando `adapter.send` na ausência de produtor autenticado. ZERO_AUTO_RESEND permanece.
5. Não executamos eletricidade física, reboot PC, dispositivos reais, prova WebAuthn do dono, provider readback autenticado, Security/Quality canônicos nesta rodada. Não fechar H0, F1/T1, M71 ou os seis P0 por 37 casos.
6. Esse RED→GREEN reproduz uma lacuna de compatibilidade específica mas **não identifica por si só os dois IDs canônicos dos P0 SQLite históricos**; rastrear IDs e contratos históricos antes de marcar conclusão.

## Próxima execução segura
Auditar o segundo eixo — APIs que compartilham conexão entre threads — com testes RED focados em modo fail-closed e isolamento de conexão própria, evitando degradar estado de store sem necessidade; continuar a especificação de antirollback independente. Se aprovada integração futura, revisar chamadas de `claim_next` e seus contratos e repetir Quality/Security integrados + revisão externa antes de qualquer merge.

**Checkpoint preserva RED e GREEN**; nenhum P0 foi declarado resolvido, nenhuma operação externa executada, nenhum custo contratado.
