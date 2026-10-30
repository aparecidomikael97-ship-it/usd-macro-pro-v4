# A309 — Controle opt-in dos auxiliares de escrita SQLite (somente LAB)

**HARD NO-GO · ZERO_AUTO_RESEND · P0 homologadas 0/6 · nenhuma nova contratação.**

## Mudança concreta no SQLiteChatStore

Os métodos privados `_update` e `_save_record` executavam comandos DML na conexão `self.db`. A292 (PR #1743) provou que, quando chamados diretamente por outro código Python, eles permitiam alterações seguidas de `self.db.commit()` sem publicar o marcador pré-COMMIT. A antiga A292 foi preservada para demonstrar essa lacuna no **modo padrão**.

A309 altera `aion_chat/store.py` em branch de laboratório, acrescentando um modo **explicitamente opt-in**, desligado por padrão:

`SQLiteChatStore(path, strict_private_write_helpers=True)`

Nesse modo:
- `_update` e `_save_record` exigem simultaneamente uma transação SQLite ativa e a titularidade da região de escrita protegida **na mesma thread**;
- A região é aberta apenas durante o corpo dos escritores legítimos: `append_message` e transações `_fenced_chat_transaction`, que atendem ao arquivamento, anexos, checkpoint e resumo;
- Ao sair da transação, a permissão transitória é encerrada antes da próxima operação;
- Acesso direto a esses auxiliares fora da região é negado **antes do DML**, deixando o handle local em estado `FAILED` com motivo explícito `PRIVATE_HELPER_OUTSIDE_FENCED_WRITE_ZERO_AUTO_RETRY`;
- As seis operações públicas continuam usando o marcador antes de COMMIT e a semântica de ACK incerto;
- `strict_private_write_helpers=False` continua sendo o padrão para não modificar silenciosamente fluxos legados enquanto ainda há bloqueios canônicos.

## Regressão real encontrada e corrigida na A309

A primeira execução da PR A309 identificou **6 ERROR no Windows** em testes
legados A246/A247: os testes usam `LostAckConnection`, um proxy sintético
que não oferece o atributo `in_transaction`. A implementação inicial
consultava esse atributo mesmo com `strict_private_write_helpers=False`.

Correção: no **modo padrão desligado**, a região A309 não consulta esse
atributo nem muda o fluxo antigo. No **modo estrito ligado**, ausência de
comprovação de transação agora falha explicitamente com
`PRIVATE_HELPER_TRANSACTION_UNVERIFIED_ZERO_AUTO_RETRY`, antes do COMMIT,
e marca a conexão como FAILED. Foram adicionados **dois testes próprios** de
regressão e A246/A247 passaram a compor a bateria direta de CI da A309.

O resultado desses novos testes e da CI integral **permanece pendente**
até execução real; registrar a correção não basta para dar PASS.

## Contraprovas obrigatórias

Esta não é uma segurança resistente ao host. A classe ainda expõe a conexão `self.db`, que permite `self.db.execute(...); self.db.commit()` sem passar pelos helpers. Além disso, código Python dentro do mesmo processo pode invocar o gerenciador `_fenced_chat_transaction` diretamente ou alterar atributos privados.

Esses **dois contornos remanescentes são reproduzidos pelos testes novos, não ocultados**. A309 reduz uma superfície de erro cooperativo e introduz um modo testável de rejeição, mas **não prova exclusividade de gravação SQLite, durabilidade física, identidade nativa FD/VFS, proprietário, custódia externa ou idempotência de intenção**.

Até a conclusão das seis P0, o modo opt-in **não deve ser adotado operacionalmente**. Sucesso de testes LAB não autoriza merge, Worker, deploy, ordens ou restauração.

## Testes

- 16 casos A309 com bancos SQLite reais temporários, incluindo os seis writers, helpers diretos, transação iniciada manualmente, fechamento da região, regressão do default, ACK perdido depois de COMMIT, recusa de retry e os dois bypasses restantes;
- Regressões A246/A247/A292/A293/A299, com testes negativos preservados, em Ubuntu/Windows;
- GitHub Actions com biblioteca padrão Python 3.12, sem extensão C, serviço pago ou chamada a provedor.

**Aceitação possível:** melhora local de laboratório, reduz bypass dos dois helpers quando modo estrito estiver ativo.

**Ainda impossível:** declarar P0-6 homologada ou liberar AION real. Para isso é preciso isolar e autenticar todas as escritas da mesma conexão e do host, provar resultado/durabilidade nativos e reconciliar efeitos de forma autoritativa.
