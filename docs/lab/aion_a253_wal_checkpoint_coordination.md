# A253 — checkpoint WAL coordenado com gravações e backup (somente LAB)

**HARD NO-GO · 0/6 P0 homologadas · sem Worker, merge, deploy, efeitos reais ou contratação.**

## Diagnóstico

Após A252, `backup_to` já aguardava a trava de ciclo de vida do SQLite, mas `wal_checkpoint` podia ser chamado diretamente enquanto outro processo cooperante ainda tinha COMMIT confirmado e marcador de confirmação pendente. Um checkpoint FULL/TRUNCATE fora do protocolo de gravação poderia mover dados do WAL em um momento que nossa aplicação classifica como incerto.

## Alteração A253

1. `wal_checkpoint` público agora possui `@_local_commit_gate`, o mesmo RLock de threads e lockfile consultivo (POSIX/Windows) de writers e backup.
2. A implementação do PRAGMA foi extraída para `_wal_checkpoint_under_lifecycle_lock`, método interno para uso **somente com a trava adquirida**.
3. `backup_to`, que já entra com `@_local_commit_gate`, chama o método interno em vez de tentar reabrir o lockfile por uma chamada pública aninhada. Locks de SO não são garantidamente reentrantes; evitar deadlocks especialmente no Windows.
4. Modos aceitos continuam `PASSIVE`, `FULL`, `RESTART`, `TRUNCATE`. Modo inválido não produz PRAGMA.
5. Incerteza persistente de COMMIT mantém veto local, inclusive após interrupção do processo; nenhuma recuperação ou replay automático.

## Ensaios

- Checkpoint público nos quatro modos e rejeição de comando inválido.
- **Dois processos reais:** o writer conclui COMMIT, segura por ~800 ms a trava e o marcador antes da confirmação; checkpoint FULL na outra conexão aguarda e então termina.
- **Crash real de subprocesso** entre COMMIT e limpeza do marcador: checkpoint público é negado com marcador persistente.
- Timeout do lock do kernel mantido por outro processo: checkpoint negado.
- Backup online ainda é executado, chama a versão interna de FULL e não tenta adquirir lockfile recursivamente.
- Contrato explícito verifica que backup e checkpoint público têm o gate e não criam lock aninhado.
- **XFAIL intencional:** conexão SQLite crua, não cooperante, ignora o lockfile e pode executar PRAGMA diretamente, demonstrando limitação da proteção.

## Não resolvido

A trava é apenas consultiva e depende do host e de participantes cooperantes. Um administrador pode apagar/substituir lockfile, marcador e banco; outro software com SQLite pode ignorar o protocolo. O checkpoint WAL pode alterar estrutura física de arquivos, mas não equivale a efeito externo autorizado nem certifica COMMIT contra queda de energia.

Não há prova nativa autenticada de VFS/FD, custódia monotônica independente, proteção contra rollback no mesmo inode, identificação humana independente ou recibo de fornecedor. O XFAIL é falha aberta, não sucesso de segurança.

**HARD NO-GO operacional · 0/6 P0 · UNCERTAIN=ZERO_AUTO_RESEND**. Produto: Trader sob demanda prioritário, motor econômico compartilhado com Investimentos, aba Negócios congelada, sem novos custos.
