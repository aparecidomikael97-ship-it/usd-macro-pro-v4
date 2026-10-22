# AION A172 — Impressão digital estreita de renomeação de diretório (LAB)

**Data 2026-10-22. Stacked sobre A171 (#1461). Não homologado.**

## Origem
A171 registrou um resultado reproduzível em 2 sistemas: detectar uma troca real ABA de mesmo inode durante leitura no Ubuntu, **mas rejeitar também uma leitura legítima** quando outra conexão escreveu ao WAL. A172 investiga especificamente a separação entre "conteúdo alterado em WAL" e "nome de arquivo movido para fora e de volta".

## Mudança isolada
- Antes/depois de uma chamada **somente leitura**: comparar somente identidade do FD de observação (`st_dev`, `st_ino`, `st_nlink`) e identidade/tempos `ctime_ns`, `mtime_ns` **do diretório-pai**.
- Não comparar `st_mtime_ns`, `st_ctime_ns` ou tamanho do DB, nem os metadados de `-wal`/`-shm`: uma transação concorrente legítima normalmente muda WAL, sem renomear o arquivo principal.
- Races de troca ABA que mudem o diretório durante a janela podem ser detectados. Qualquer observação de drift da impressão digital nega o resultado da leitura e trava a fachada. **Não há replay.**

## Cenários a medir
1. ABA real de leitura no Ubuntu detectado, quando o SO permite o rename; Windows classificado como OS_DENIED se não exercer.
2. Escrita normal de outra conexão ao WAL durante leitura deve ser permitida.
3. Adição de arquivo **não relacionado** no mesmo diretório pode causar falso positivo de diretório.
4. Mudança de conteúdo de arquivo não relacionado, sem renomear/criar entrada, não deve alterar a impressão digital.
5. ABA **durante escrita** continua fora de escopo e deve ser reproduzido como gap.

## Limites
Apenas um sensor temporal do diretório. Ele **não prova** vínculo atômico com o handle SQLite nativo, pode perder ABA mais rápido que granularidade de relógio do FS ou quando metadados forem manipulados, e não garante ordem de writes/rollback. Se um adversário move o banco em outro diretório enquanto restaura timestamps ou controla host, o teste não o exclui. Mesmo sem atacante, criação de outro arquivo na pasta pode causar falso positivo. Bloqueio de leitura não identifica culpado nem prova ausência de write. Outras fases (custódia externa, recibos, assinaturas de produtores distintos) não são cobertas.

**HARD NO-GO; 0/6 P0 homologados; main inalterada; no merge/deploy/Worker/providers/cost; ZERO_AUTO_RESEND.**

## CI / evidência
[GitHub Actions #39853106563](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39853106563): **SUCESSO, Ubuntu 69/69 e Windows 69/69 (138 testes).** O verde comprova o resultado esperado dos ensaios; não é homologação.

| Observação dos logs | Ubuntu | Windows |
|---|---|---|
| ABA real na leitura | `ABA_COMPLETED_OBSERVED_DENIED` | `OS_DENIED_OR_RESTORED_OS_NOT_EXERCISED` |
| Concorrência legítima | `READ_ALLOWED_WITH_WAL_CHANGE` | `READ_ALLOWED_WITH_WAL_CHANGE` |
| ABA real na escrita | `ABA_COMPLETED_NOT_ATTESTED` | `OS_DENIED_OR_RESTORED_OS_NOT_EXERCISED` |
| Criação de arquivo não relacionado | `READ_DENIED_DIRECTORY_FALSE_POSITIVE` | `TIMESTAMP_DRIFT_NOT_OBSERVED` |
| Alteração de conteúdo em arquivo não relacionado | `READ_ALLOWED` | `READ_ALLOWED` |

**Interpretação:** A172 removeu o falso positivo específico de escrita concorrente ao WAL observado na A171 e conservou a detecção Ubuntu de ABA de leitura. **Restam:** falso positivo por alteração legítima de entrada no diretório Ubuntu; ausência de mudança observada nos timestamps do diretório Windows neste ensaio; ABA durante escrita Ubuntu não detectado. Não houve prova de prevenção de manipulação de host, recuperabilidade externa, nem custódia independente. A Quality canônica completa continua pendente.
