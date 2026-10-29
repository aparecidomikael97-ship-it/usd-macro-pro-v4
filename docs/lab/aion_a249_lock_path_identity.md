# A249 — Detecção local de troca de pathname do lockfile (P0-5/6 LAB)

Estado: **HARD NO-GO · 0/6 P0 homologadas · sem merge/Worker/deploy/efeitos externos/novos gastos**.

## Escopo

A248 utiliza uma trava consultiva do kernel para coordenar processos cooperantes via arquivo `<db>.aion-message-lifecycle.lock`. Uma troca de nome/inode durante a aquisição ou a operação poderia fazer novas conexões abrirem outro arquivo de trava, acreditando coordenar o mesmo SQLite. A249 acrescenta checagem `fstat(fd)` vs `Path.stat(follow_symlinks=False)` **imediatamente após adquirir a trava** e **antes de liberá-la**. Se detectar nome inexistente, objeto não regular ou identidade `st_dev/st_ino` diferente, recusa com `MessageLifecycleLockIdentityError`; a camada de `append_message` converte em `StorageUnavailableError`, marca a instância FAILED e proíbe retry automático.

O cenário de troca **após um COMMIT concluído** é reconhecido como resultado incerto. Um rollback posterior não é considerado prova de ausência do efeito. O bloqueio de instância não equivale a um veto durável externo.

## Ensaios A249
- Fluxo normal de trava e mensagem.
- Divergência de inode simulada em ambas as plataformas: sem entrada no bloco protegido.
- Troca real do nome logo após aquisição da trava, antes de entrar na seção crítica: negação em POSIX.
- Remoção do nome enquanto o handle está aberto: erro na saída em POSIX.
- Remoção do lockfile depois de um COMMIT verdadeiro: instância FAILED, registro persistido, sem retry por essa instância.
- Falsificação de stat do lockfile durante startup: bloqueio antes de abrir/criar o SQLite.
- Mantêm-se regressões A248/A247/A246/A245/A240/A241/A242/A233, com XFAIL anteriores para ataques de host.

## Limitações fundamentais

- Não existe proteção contra um host malicioso fazer ABA, substituir o arquivo entre checagens, ou **adquirir um segundo lockfile antes que o primeiro detentor perceba a troca**. O teste A248 de detach continua XFAIL, mesmo que A249 detecte a troca na saída.
- O lockfile e o marcador são controlados pelo próprio host, sem raiz independente, custódia externa ou atestado do SQLite VFS/FD.
- A verificação pós-operação não impede retroativamente uma operação já gravada: registra apenas incerteza local.
- Nenhuma garantia contra falta de energia real ou recibo de provedor externo. Sem novos serviços, credenciais nem ativação do Worker. Outras rotas de escrita direta continuam fora do gate.
- **P0 0/6 e UNCERTAIN=ZERO_AUTO_RESEND permanecem**. Trader prioritário, Investimentos depois, Negócios congelada.
