# AION G78 — COMMIT do chat: interrupções e quarentena (LAB)

**Base:** G77 `300df9eff7948a14ac1f5b56d9ebd760ef2f66d1`. **Escopo:** `aion_chat/store.py::_commit_or_quarantine` e oito testes novos sintéticos. **0/6 P0 homologadas. HARD NO-GO; ZERO_AUTO_RESEND. Sem merge/deploy/Worker/SEND.**

## Evidência de falha real (antes do patch)
Auditoria Codex read-only `01a175fd-1702-7483-9b57-8a8edb228f31` identificou `except Exception` em COMMIT do SQLiteChatStore. Esse handler não capturava `KeyboardInterrupt`/`SystemExit`, podendo deixar a conexão utilizável mesmo após gravação de resultado incerto. O serviço de chat chama `create_conversation` e atinge o mesmo código. A revisão por si só não comprova falha: a reprodução foi executada separadamente.

Codex `01a175ff-072a-7f80-936e-5a3c2cde3387` escreveu primeiro `labs/a190/test_g78_chat_commit_interrupt_lab.py`, sem mudar produção nem executar os testes no sandbox restrito. Execução independente no Windows conectado, produção G77 intacta:

```text
py -B -m unittest -v labs.a190.test_g78_chat_commit_interrupt_lab.G78ChatCommitInterrupt
Ran 8 tests
FAILED (failures=6)
exit 1
```

Quatro cenários `KeyboardInterrupt/SystemExit` antes/depois do COMMIT apresentaram `close_count=0`, em vez da quarentena esperada. Outro cenário permitiu que `SystemExit` ao fechar substituísse o `OSError` original. A sexta falha também tratava de exceção não contida. Dois controles OSError passaram. Sem erros de fixture no RED válido.

## Contenção local e prova GREEN

Patch mínimo apenas em `aion_chat/store.py::_commit_or_quarantine`: captura `BaseException` ao tentar o COMMIT e tenta quarentena sem permitir que uma falha secundária durante fechamento substitua a exceção original; conserva a anotação `AION_CHAT_COMMIT_OUTCOME_UNCERTAIN_STORE_QUARANTINED_NO_RETRY`. Não amplia permissões, não reenvia, não executa rollback automático e não altera BEGIN/ROLLBACK.

Executado fora do Codex sandbox, no Windows:

```text
py -B -m unittest -q labs.a190.test_g78_chat_commit_interrupt_lab.G78ChatCommitInterrupt labs.a190.test_g33_chat_ambiguous_commit_lab labs.a190.test_g32_chat_store_rollback_quarantine_lab test_atlasquant_aion_first_attempt_witness_a180_lab labs.a190.test_g77_commit_interrupt_quarantine_lab.G77CommitInterruptQuarantine
Ran 65 tests
OK
exit 0
git diff --check: exit 0
```

As verificações incluem identidade da exceção, uma tentativa de COMMIT, zero rollback, conexão desanexada, saúde FAILED, bloqueio de segunda gravação e releitura do estado real (antes e depois do COMMIT) usando banco recém-aberto. Apenas dados sintéticos; nenhum HTTP/provedor real.

## Limites

A proteção vale apenas quando o processo Python alcança esse handler. Não demonstra persistência sob corte físico de energia, fechamento interrompido antes de encerrar o handle nativo, antirollback fora do host, custódia da primeira reserva, identidade HUMAN_OWNER ou recibos autenticados de provedores. O efeito da G78 não homologa as P0. Os caminhos BEGIN/ROLLBACK que ainda capturam `Exception` precisam de análise separada.

A validação no GitHub para Ubuntu e Windows será conferida pelo SHA exato antes de ser declarada aprovada. A auditoria canônica e os requisitos externos devem continuar separados dos testes sintéticos verdes.
## Revisao independente
Codex read-only (sessao 01a17601-4b46-7911-9bd5-d9d99cb4f095) nao detectou falhas altas/medias no trecho; ressalvou um caso baixo: excecao customizada cujo add_note() lance outra excecao poderia mascarar a original depois da quarentena. O teste atual nao cobre esse caso nem fechamento interrompido antes do close nativo. Nao remover bloqueios de seguranca para encerrar essas pendencias.
