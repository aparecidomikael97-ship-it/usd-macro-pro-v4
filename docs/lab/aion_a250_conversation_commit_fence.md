# A250 — Proteção de criação de conversas contra COMMIT incerto (somente LAB)

**HARD NO-GO · 0/6 P0 homologadas · nenhuma autorização de Worker/deploy/merge/efeito externo/despesa.**

## Problema observado

Após A249, `append_message()` possui trava cooperativa entre processos, marcador pré-COMMIT e bloqueio após perda de ACK. **`create_conversation()` ainda utiliza `with self.db:`**, sem reserva de marcador e sem a trava cooperativa durante o COMMIT. Se um erro acontece depois de a transação realmente persistir, a aplicação pode acreditar que não houve criação e tentar novamente, criando conversa duplicada.

## Mudança A250

- Adiciona `@_local_commit_gate` a `create_conversation` e usa `BEGIN IMMEDIATE` para abranger inserção, `_commit_fenced_chat_write()` e confirmação.
- Extrai a etapa de COMMIT com marcador local **já usada** em `append_message` para uma função compartilhada, mantendo a semântica antiga das mensagens.
- Falha no COMMIT: estado `FAILED`, `StoreCommitOutcomeUncertainError`, arquivo de veto local permanece; reinício automático bloqueado.
- Não assume que rollback após exceção prova ausência de efeito. Operação normal elimina o marcador apenas após confirmação de COMMIT.
- A trava local/entre processos é **consultiva e não autenticada**, como em A248/A249.

## Ensaios A250

1. Criação e mensagem normais, sem marcador residual e com reabertura.
2. COMMIT SQLite real seguido de ACK sintético perdido: uma conversa persiste e o host recusa nova criação/reinício.
3. Exceção antes do COMMIT: a conversa não persiste e o veto conservador impede reinício.
4. Falha sintética antes de preparar marcador: COMMIT não ocorre.
5. Falha de limpeza pós-COMMIT: a conversa existe e o marcador bloqueia reabertura.
6. Subprocesso `os._exit` **após COMMIT real da conversa**, antes da limpeza do marcador: nova abertura recusada.
7. **Três subprocessos reais criando 18 conversas distintas**, sem perda/duplicação, utilizando o mesmo SQLite.
8. **XFAIL explícito**: `archive_conversation` ainda é um writer baseado em `with self.db:` que contorna o marcador pré-COMMIT; precisa correção separada.

## Limites críticos

- Testes simulam perda da confirmação, e saída abrupta do processo — **não** provam resistência a queda real de energia.
- A proteção continua local e adulterável: um host com acesso aos arquivos pode apagar o marcador, substituir a trava ou fazer rollback.
- `archive_conversation`, `add_attachment_metadata`, gravações de checkpoint/resumo e outros writers ainda precisam da mesma semântica. O novo XFAIL não é um PASS de segurança.
- Não existe raiz externa de confiança, recibo de efeito externo, identidade atestada do VFS/FD nativo do SQLite nem validação dos seis P0.
- Nenhum reenvio automático de operação incerta; **UNCERTAIN=ZERO_AUTO_RESEND**. Product roadmap: Trader principal, motor econômico compartilhado sob demanda com Investimentos, Negócios congelada.

O próximo trabalho deve revisar sistematicamente os demais writers, com testes que não interpretem descoberta de vulnerabilidade como autorização de operação.
