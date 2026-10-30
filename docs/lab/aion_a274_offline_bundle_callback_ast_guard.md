# A274 — Negação de callbacks no pacote offline AION (LAB 30/10/2026)

**Base A273 #1724, PR draft isolada. Sem merge, Worker, Render, rede, corretora, ordens, novas compras ou custos.**

## Falha
A260 gerava ZIP de estudo com apenas seis arquivos allowlisted e exigia `_reserved_first_attempt` retornando `False`. Contudo, não verificava se `dispatch_claimed` ou `reconcile` tinham novas referências ao `adapter`, ao `authorize` ou ao `cumulative_authority_guard`. Uma alteração no próprio código empacotado poderia inserir chamadas host-controlled sem mudar a função `_reserved_first_attempt`.

Os testes antigos de adulteração alteravam um arquivo sem atualizar o SHA do manifesto. A recusa podia ocorrer apenas por divergência de hash, sem testar o limite de callbacks.

## Correção offline
O analisador AST exige exatamente um método normal `dispatch_claimed` e `reconcile`; recusa referências diretas aos argumentos host-controlled, `getattr`/`setattr`/`eval`/`exec`/`locals`/`globals`/`__import__` e chamadas diretas de métodos de envio/autorização sensíveis. O gate `_reserved_first_attempt` continua literalmente `False`.

Três novos testes A260 (#14–16) criam arquivos Python sintaticamente válidos alterando os métodos, **atualizam o hash do arquivo no manifesto** e exigem que o AST recuse: `adapter.send`, `adapter.reconcile`, `getattr(adapter, "send")`. Os tests existentes continuam cobrindo lista de arquivos, symlink, import de LAB, determinismo e isolamento do processo extraído.

## O que não é provado
AST não é sandbox para Python adversarial; há formas indiretas de executar código não capturadas por essas regras. O manifesto não é assinado por autoridade independente. A260 é um ZIP de **estudo**, não um artefato que o Render é obrigado a consumir; a xfail de ligação ao Render permanece. Nada permite SEND ou valida P0. **HARD NO-GO · 0/6 P0 homologadas · UNCERTAIN=ZERO_AUTO_RESEND.**
