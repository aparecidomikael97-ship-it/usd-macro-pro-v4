# A248 — Lock consultivo entre processos para mensagens SQLite (LAB)

**Estado: HARD NO-GO, 0/6 P0 homologadas, sem Worker/deploy/contratação/merge.**

## Problema
A247 adicionou um `threading.RLock`, útil para concorrência dentro do mesmo processo Python. Múltiplos processos, contudo, mantêm `RLock` diferentes e podem interpretar incorretamente o marcador `.aion-message-commit-pending` de uma transação que está sendo concluída normalmente.

## Mitigação A248 (somente arquivos locais)
- Uma trava **consultiva do kernel** usando arquivo `<db>.aion-message-lifecycle.lock`, `fcntl.flock` no POSIX e `msvcrt.locking` no Windows, é adquirida durante a abertura de `SQLiteChatStore` e durante o ciclo completo de `append_message()`. A trava de threads A247 permanece.
- Aguarda por até cinco segundos com tentativas não bloqueantes; se não adquirir, **recusa** sem abrir/reutilizar o banco. Não tenta reenvio.
- O arquivo da trava **não é apagado** na limpeza normal: a trava é no handle do SO, liberada ao fechar ou quando o processo termina. O marcador de incerteza A247 continua sendo o **veto após crash**.
- Rejeita alvo não regular e usa `O_NOFOLLOW` quando o SO oferece; são salvaguardas parciais, não uma raiz de confiança.
- Sem novo pacote ou serviço.

## Bateria de ensaios A248
1. Fluxo normal e reabertura com arquivo de trava reutilizado.
2. **Três subprocessos independentes, 24 gravações reais em SQLite**, sem sequências perdidas ou duplicadas.
3. Uma trava mantida por outro processo é esperada e liberada antes de abrir.
4. Tempo limite sem acesso a bloqueio resulta em negação antes de criar banco.
5. Marcador local pendente continua vetando após liberar a trava.
6. Symlink para arquivo de trava é recusado, quando há `O_NOFOLLOW`.
7. **XFAIL POSIX:** administrador pode remover o nome do arquivo da trava já aberta e criar outro inode, permitindo duas posses de lock simultaneamente. No Windows, o teste é SKIP por diferenças do SO.

Também repetir regressões A247/A246/A245/A240/A241/A242/A233 e runtime staging nos dois SOs.

## Limites, sem homologação
Essa trava **coordena apenas processos cooperantes no mesmo host**, não oferece identidade de VFS/FD, prova de monotonicidade externa, segurança diante de administrador adversário, prova de durabilidade física após falta de energia nem recibos independentes de efeito externo. Um host capaz de remover/truncar o arquivo de trava ou marcador, fazer rollback do SQLite, ou usar rotas de escrita sem a trava pode ignorá-la. Erros de concorrência sob carga ou XFAIL inesperados proíbem promoção.

**UNCERTAIN=ZERO_AUTO_RESEND. Trader priorizado, motor econômico compartilhado sob demanda com Investimentos e Negócios congelada/preservada.**