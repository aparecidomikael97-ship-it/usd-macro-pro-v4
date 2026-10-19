# AION P0 — Retorno de backup SQLite com histórico de execução: HARDSTOP da API genérica

19/10/2026. **GO-LAB condicionado**. 0/6 P0 homologados. HARD NO-GO, Worker OFF, ZERO_AUTO_RESEND. Nenhum merge, deploy, fornecimento externo, operação real ou gasto.

## Falha do original comprovada

`SQLiteChatStore.restore_from_backup(source, target)` A118 validava `PRAGMA quick_check`, `PRAGMA foreign_key_check` e hash SHA-256 do arquivo, depois executava `os.replace` do target. Integridade estrutural do arquivo não demonstra a *atualidade* do histórico da primeira tentativa. Teste de API real anterior mostrou: snapshot antes de `UNCERTAIN` + tentativa marcada incerta + restore de snapshot antigo = retorno a `PENDING` e possível novo claim LOCAL. A barreira de fornecedor A118 impede `adapter.send` real neste estado (nenhum reenvio real provado), mas o mecanismo de rollback local estava exposto.

## Escopo do remendo (somente em LAB)

Branch isolada `lab/aion-p0-sqlite-execution-restore-hardstop-20261019` com base `a172c88f67e47d001b804b16808b8648cba3804e`. Código `aion_chat/store.py` alterado nos commits `0f0ba9f033c2d1e257e542b4bc695a595c680eac` e `543a47e0d3a897a6a5a6903826d6255307d18d37`. Novos testes `test_aion_p0_sqlite_execution_restore_hardstop_lab.py` (13 casos) congelados ANTES do patch, commit `042d83d8a5e6ffd71bf13934f52e8b8d37636c0c`; workflow independente `.github/workflows/aion-p0-sqlite-execution-restore-hardstop-lab.yml`, commit `e89737093f764e8897564b48c886f50682f8ae11`.

O método padrão **não aceita nenhum parâmetro, flag ou token autoafirmado capaz de liberar execução**: continua sem prova de witness independente.

- Analisa (em modo SQLite `mode=ro`) ambos SOURCE e TARGET existentes antes de criar a pasta de destino ou copiar arquivos, procurando nomes exatos de tabelas operacionais: `action_decisions`, `action_outbox`, `action_effects`, `aion_authority_spend`, `aion_execution_sagas`, `aion_execution_saga_steps` e `aion_execution_saga_events`.
- Se **qualquer** uma dessas tabelas estiver presente, mesmo vazia, lança `StorageUnavailableError("P0_EXECUTION_RESTORE_REQUIRES_INDEPENDENT_WITNESS")`, **sem substituir o destino**.
- Valida um target existente antes de sobrescrevê-lo, negando target ilegível/corrompido.
- Recusa WAL/SHM **órfãos sem arquivo principal**; WAL de target existente deve ser avaliado pela própria conexão SQLite (a presença do filename por si só não prova efeito ou corrupção).
- Revalida a cópia temporária e o target antes do `os.replace`. Isso reduz algumas janelas, **NÃO torna a operação atômica contra escritores externos concorrentes**.
- Restauração de base exclusivamente de mensagens/conversas continua a funcionar, inclusive sobre uma outra base também chat-only. Nada foi habilitado para Worker/Outbox/adapter.

## Registro exato do TDD

[RED inicial #39321611432](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39321611432): 13 cenários no Ubuntu, **9 FAIL** e 4 PASS, confirmando que a API original aceitava substituir bancos com tabelas de execução e até target ilegível, ou ignorava WAL órfão.

[Execução pós-patch #39321841939](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39321841939) falhou no cenário de restauração chat-only de um target existente porque a verificação ingênua de `-wal/-shm` vetava mesmo arquivos auxiliares normais. O código foi aperfeiçoado, não os testes nem o critério de proteção. O estado GREEN final deve ser lido do workflow `39322051809` no commit `543a47e0d3a897a6a5a6903826d6255307d18d37`, Ubuntu/Windows, e NÃO inferido de uma tentativa anterior.

O teste histórico `test_aion_p0_original_sqlite_compat_concurrency_restore_lab.py::test_06_real_restore_api_erases_later_uncertain_state_without_witness` foi mantido como evidência de regressão, mas sua expectativa no LAB corrigido passou de `RESTORE_VERIFIED` para **recusa explícita e preservação de `UNCERTAIN`**; commit `2dafeb7d7d84fa12ccd3ebd1cdd2a3c4754b1951`. O original A118 permanece intocado em main e é usado como baseline de RED.

## Limites / bloqueios remanescentes

1. **Não bloqueia substituição manual, restore por ferramenta externa, snapshots da VM, reimagem de host, rollback de volume, nem um adversário com escrita direta no banco.** Não existe ainda witness de first-effect de custódia externa, high-water monotônico autenticado, consumo de nonce, prova de produtor ou fence de não-efeito. Isso permanece um P0 técnico não homologado.
2. A detecção por nomes exatos protege os esquemas conhecidos e oficiais; ela não detecta esquemas renegados/renomeados, eventuais módulos novos ou tampering preexistente. Não substituir por promessa de proteção universal.
3. A validação de target/cópia temporária seguida por `os.replace` tem TOCTOU se um outro processo alterar o path durante o intervalo. Nenhuma trava distribuída nem custodiante independente foi implementado. Do not deploy/integrate.
4. Uma restauração chat-only continua destrutiva para mensagens mais novas, por definição de snapshot; é permitida apenas se não houver esquema de execução conhecido, e ainda requer política de retenção/privacidade própria.
5. O nível de integridade é de API de armazenamento local, não autenticação HUMAN_OWNER, fornecedor de recibos, retorno de operações incertas, H0 físico, resolução M71 ou reparo de Quality/Security históricas.
6. Antes de homologar o P0 exigir armazenamento monotônico independente FORA do domínio do backup/host; readback autenticado do produtor, fail-closed em inicialização e antes da primeira intenção, casos concorrentes, Windows físico, blackout real e revisão externa.

**Conclusão técnica: um caminho específico de perda de histórico via API oficial foi bloqueado em LAB; 0/6 P0 homologados, HARD NO-GO.**
