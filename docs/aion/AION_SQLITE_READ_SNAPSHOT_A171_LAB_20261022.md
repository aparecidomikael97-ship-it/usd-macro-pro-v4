# AION A171 — Observação de metadados em leituras SQLite (LAB)

**Data:** 2026-10-22. **Escopo:** somente host de chat SQLite staged, candidato experimental empilhado sobre A170. **Não homologado.**

## Hipótese e implementação
O identificador de caminho `(st_dev, st_ino)` em A169/A170 não observa uma troca ABA que renomeia o mesmo inode para fora e de volta. Na A171, para **métodos de leitura** apenas, são comparados, imediatamente antes e depois da operação:
- `os.fstat` do descritor separado aberto pelo guard: inode, tamanho, link count, ctime_ns, mtime_ns;
- `lstat` do diretório-pai: inode, ctime_ns, mtime_ns;
- `lstat` de `-wal` e `-shm` quando presentes: inode, tamanho, ctime_ns, mtime_ns.

Se qualquer observação muda ou não pode ser efetuada, falha fechada e latch da **fachada staged**; não há replay automático. O resultado da leitura não retorna como sucesso. A verificação ocorre depois de o método de leitura ter sido executado, e não impede alterações externas.

## Matriz esperada para comprovação pelo CI
| Caso | Decisão esperada |
|---|---|
| Leitura inalterada | Aceitar |
| Drift de leitura injetado | Bloquear e latchear |
| ABA real no Linux durante leitura | Detectar pela mudança do diretório; bloquear |
| ABA real no Windows | Se o SO impedir a renomeação, registrar OS_DENIED; não declarar detecção |
| Escrita de outra conexão durante leitura | Pode bloquear uma operação **legítima** por mudança de WAL: falso positivo operacional |
| ABA durante **escrita** | **Não coberto** pela A171; registrar explicitamente se o SO permitir |
| Falha de leitura de metadados | Bloquear e latchear |

## Limites materiais e critérios NO-GO
1. Não há `openat2`/handle SQLite VFS nativo ligado atomicamente ao FD observado. Mudanças fora da janela, ABA rápido com timestamp arredondado, replays físicos/host hostil ou metadados forjados podem escapar.
2. O diretório contém entradas que podem mudar legitimamente, e o WAL muda sob concorrência normal; **um bloqueio não comprova ataque**. A escolha de falhar fechado impõe risco de disponibilidade e requer medição antes de qualquer adoção.
3. A observação não autentica produtor externo, recibos, custodiantes, nem consegue estabelecer ordem global ou durabilidade independente. Não resolve os 6 P0.
4. **Nenhuma autorização em produção:** HARD NO-GO, P0 0/6; main intacta, zero deploy/Worker, zero mensagens/fornecedores/cobranças. Qualquer escrita com desfecho incerto deve ser reconciliada independentemente; ZERO_AUTO_RESEND.
5. CI só comprova que os cenários simulados/locais tiveram os resultados registrados; não é homologação de servidor, plataforma ou proteção anti-rollback.

## Evidências
Aguardar os dois jobs do workflow `AION SQLite staged lifecycle` em Ubuntu e Windows, com contagem e observações `A171_...` transcritas posteriormente. A Quality canônica completa, assinaturas reais e recibos externos continuam pendentes.
