# A312 — Auditoria real dos limites de permissões do sistema operacional (LAB)

**HARD NO-GO · ZERO_AUTO_RESEND · P0 homologadas 0/6 · sem Worker/deploy, merge ou custos novos.**

## Propósito

A311 demonstrou uma API JSON restrita com um subprocesso descartável por
solicitação, mas também que um processo do mesmo usuário do sistema pode
abrir o arquivo SQLite diretamente. A312 verifica esse limite **por
observação real do filesystem e do sistema operacional**, sem presumir que
separação de processos equivale a separação de credenciais.

## Experimento em arquivo descartável

1. Cria somente uma pasta temporária `a311-lab-...` com o marcador sintético
   obrigatório da A311; o SQLite contém uma conversa `A311 TEST...`.
2. Em sistemas POSIX, aplica **`0700` à pasta** e **`0600` ao arquivo
   SQLite** e ao marcador; observa `os.lstat`, `stat.S_IMODE`,
   proprietário e UID efetivo, sem assumir identidade do VFS/FD interno.
3. Lança outro processo Python, pela mesma conta do runner, executando um
   **UPDATE fixo, somente na conversa sintética**.
4. Reabre o banco apenas para ler e confirmar se o outro processo alterou a
   linha. A observação explicita `SAME_ACCOUNT_WRITE_BYPASS_CONFIRMED`
   quando o segundo processo escreveu.
5. No Windows, **não interpreta `chmod` nem `st_mode` como prova de ACL
   NTFS/DACL**. Um segundo processo herdando a identidade do runner pode
   demonstrar o contorno, mas a auditoria não afirma que contas distintas
   não poderiam ser isoladas por ACL.
6. Testa dados inválidos, permissões relaxadas, caminhos incorretos,
   symlink (POSIX), e fontes de evidência autoafirmadas.

O ensaio não cria usuários, não faz `chown`, não exige administrador e
não modifica arquivos fora do diretório temporário. Não acessa rede,
fornecedor, ordens ou armazenamento real.

## Conclusões que o código está proibido de assumir

Um arquivo `0600` protege contra **outras identidades sem privilégios
superiores** sob condições apropriadas, mas **não** contra outros processos
rodando com a **mesma identidade**. Separação de PID não é separação de
principal. Um proprietário/admin também pode alterar permissões e arquivos.
No Windows é preciso validar o SID do escritor e do cliente, DACL dos
arquivos/pasta e handles; nenhum desses controles é homologado aqui.

As informações de `stat`, UID, modo ou PID são **locais ao host**, não
provas de independência, efeito do provedor, custódia histórica antirollback,
identidade nativa SQLite VFS/FD ou idempotência semântica. `P0-5` e
`P0-6` permanecem abertos, assim como `P0-1/2/3/4`.

## Matriz necessária antes de pensar em homologação P0-6

| Condição | Requerimento futuro | A312 |
|---|---|---|
| Escritor separado por principal do SO | UID/SID de escritor distinto do cliente | Não comprovado |
| Arquivo do banco inacessível ao cliente | ACL/DACL e identidade com negação efetiva testada | Não comprovado |
| Um único escritor com API restrita | Isolamento + exclusividade e política auditável | Parcial (A311) |
| Banco e WAL/SHM vinculados ao handle real | VFS/FD verificado, não só pathname | Não comprovado |
| ACK incerto e histórico durável | Custódia independente de intenção e reenvio zero | Não comprovado |
| Autoridade externa e incidentes | Assinatura, revogação, antirollback fora do host | Não comprovado |

## Invariantes permanentes

`assess_production_writer_boundary` rejeita até alegações inventadas de
`separate_os_principal_attested=True`. Toda saída permanece
`can_resume=False`, `can_resend=False`, `can_auto_retry=False`,
`can_authorize_real_effect=False`, `automatic_retries=0`,
`hard_no_go=True`, `zero_auto_resend=True`, `p0_homologated=0`.

Executar `python -m unittest -v labs.test_a312_os_principal_file_boundary_lab`
e regressões A311/A310/A309/A246/A247/A292/A293/A299 no Ubuntu e no Windows.

**Passar o LAB não libera AION.** Uma próxima arquitetura teria que
considerar um escritor com credencial SO exclusiva e IPC autenticado, sem
expor os arquivos ao cliente, e exigiria análise de custos e permissões
antes de qualquer serviço permanente. Nada disso foi ativado na A312.
