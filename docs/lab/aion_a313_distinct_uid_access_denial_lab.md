# A313 — Teste real de duas identidades Unix e acesso ao SQLite (LAB)

**HARD NO-GO · ZERO_AUTO_RESEND · 0/6 P0 homologadas · sem Worker, deploy, merge, operações reais nem contratação nova.**

## Problema real que a A312 revelou

A312 comprovou que um segundo processo da **mesma conta** consegue abrir e
alterar um banco SQLite sintético, mesmo quando a pasta está em modo POSIX
`0700` e o banco em `0600`. Para existir um escritor realmente exclusivo,
os componentes clientes **não podem compartilhar o mesmo UID/SID** e precisam
ser bloqueados pelas regras efetivas do sistema operacional.

## Prova A313 no Ubuntu, sem criar usuários

No runner Ubuntu do GitHub, a A313 verifica a identidade existente
`nobody`, diferente da identidade do teste. Ela **não cria usuários, não
altera as contas do notebook e não inicia nenhum serviço permanente**.

1. Cria exclusivamente um banco SQLite descartável A311, em diretório
   temporário marcado, contendo somente a conversa `A311 TEST...`.
2. Aplica modo `0700` à pasta e `0600` ao banco e inspeciona UID, modo,
   `lstat` e tipo de arquivo. A própria conta proprietária consegue ler o
   banco, resultado que **não** representa uma conta de cliente isolada.
3. Usa `sudo -n -u nobody -- <python do runner> -c <script fixo>`
   em um subprocesso limitado a 15 segundos, sem shell nem entrada arbitrária.
   O processo não privilegiado tenta abrir o banco para leitura e escrita
   e listar a pasta. Esperam-se **três negativas do kernel**.
4. **Controle positivo obrigatório:** na mesma pasta **somente sintética**,
   muda temporariamente a pasta para `0755` e o banco para `0644`.
   Repete o subprocesso com o mesmo UID restrito e lê uma linha via
   SQLite `mode=ro`. Assim comprova que a negativa anterior não foi por
   incapacidade de executar Python, SQLite ou chegar ao diretório.
5. Restaura `0700/0600` no `finally`, sem conservar nenhum subprocesso.
   Todos os arquivos temporários são excluídos ao final do teste.

O ambiente de CI Ubuntu **exige** `A313_REQUIRE_DIFFERENT_UID=1`. Se
`nobody`, `sudo`, as negativas reais ou o controle positivo estiverem
indisponíveis, a bateria **FALHA**, não registra um falso PASS.

## Windows

O GitHub Actions executa também regressões Windows, mas o resultado A313
precisa ser `WINDOWS_DACL_SID_NOT_TESTED`. O teste não infere SID,
separação de tokens ou ACL NTFS a partir de `chmod` ou `stat`; a situação
Windows permanece **não homologada** até existir ensaio específico de
DACL/SID e identidade distinta com negação real.

## O que essa prova permite afirmar

Somente que, no runner Ubuntu descartável usado, duas identidades POSIX
**realmente distintas** receberam direitos diferentes sobre arquivos de
teste, com negativa real do kernel. As permissões e os UIDs observados
podem reduzir a superfície de acesso **se forem implantados e administrados
corretamente**.

O estudo **não implanta** um usuário dedicado ao SQLite do AION, nem comprova
a exclusividade do escritor operacional. O código AION atual pode rodar com
a mesma identidade do detentor do banco. Root/admin pode alterar arquivos;
quem controla o escritor pode alterar o banco; Windows SID/DACL não foi
verificado; o Python não atesta identidade VFS/FD/WAL/SHM nativa nem prova
custódia off-host, idempotência semântica, ACK externo e autorização do
titular.

`assess_operational_os_writer_readiness` nunca promove uma observação
de CI a produção, mesmo com um dossiê falsificado dizendo
`real_writer_account_deployed=True`, `p0_homologated=6` ou
`can_resume=True`.

## Como validar

No Ubuntu GitHub-hosted, com conta preexistente `nobody`, sudo não
interativo e sem instalação de dependências:

```bash
A313_REQUIRE_DIFFERENT_UID=1 python -m unittest -v labs.test_a313_distinct_uid_access_denial_lab
```

No Windows, executar os testes de negação de alegações falsas e registrar
explicitamente os testes Unix não aplicáveis. Rodar também as regressões
A312/A311/A310/A309/A246/A247/A292/A293/A299 em ambas as plataformas.

Nenhum código de operação foi ativado; esta PR rascunho fica empilhada
sobre A312, nunca sobre main. **P0-6 e as outras cinco P0 continuam abertas.**

### Próxima decisão arquitetural

Antes de qualquer homologação, precisamos especificar um **escritor com
identidade própria do SO**, restrições da pasta/DB/WAL/SHM e um IPC de
autorização com vínculo à intenção. Testar ao menos cliente sob UID/SID
distinto, processo escritor, crash/ACK incerto, tentativa de restauração,
alteração de permissões por host e controles contra rollback externo.
Não implantar sem nova aprovação operacional e revisão de custo.
