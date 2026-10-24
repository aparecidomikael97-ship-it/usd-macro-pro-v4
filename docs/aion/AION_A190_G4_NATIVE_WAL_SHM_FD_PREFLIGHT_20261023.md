# A190 G4 — SQLite WAL/SHM, conexão LIVE, inode/FD e substituição de caminho

**Data do proprietário:** 2026-10-23. **Escopo:** somente LAB/Draft sobre A190 G3 #1490; missão #1486. O código operacional AION, Worker, main e deploy não foram alterados.

## O que este novo bloco realmente testa

Cinco testes realizam I/O **verdadeiro via SQLite nativo e sistema de arquivos** sob Windows e Ubuntu, com diretórios SQLite artificiais e fechamento explícito das conexões. Adicionalmente, o workflow reexecuta os quatro testes A185 de conexão realmente usada por Chat/Outbox/Budget/Saga.

| Teste | Condição exercida | Critério do LAB | Como interpretar |
| --- | --- | --- | --- |
| G4-1 — WAL pós-COMMIT | Tabela checkpointada, depois INSERT confirmado no WAL, -wal/-shm fisicamente presentes | SQLite original lê linha; cópia bruta de somente *.sqlite não a lê; API de backup SQLite lê a linha | **RED de backup bruto:** arquivo principal pode estar atrás do commit; backup SQLite API cobre apenas o caso ensaiado |
| G4-2 — leitor LIVE | Leitor mantém snapshot antes de nova gravação; escritor confirma commit, tenta checkpoint TRUNCATE | Leitor antigo vê versão anterior, novo observador vê nova, checkpoint fica BUSY até encerrar snapshot | WAL e SHM podem ser imprescindíveis durante conexões abertas |
| G4-3 — caminho vs FD | SQLite mantém transação+handle no arquivo antigo, tentativa REAL de substituir arquivo por outro SQLite válido | Linux pode aceitar e revelar visão antiga vs novo path/inode; Windows pode negar substituição até fechar handles; registrar resultado OS observado sem impor mesma semântica | Uma comparação de path isolada não é uma prova persistente da identidade do FD |
| G4-4 — identidade nativa | UPDATE confirmado sobre mesmo arquivo SQLite em journal DELETE | Identidade (dev/inode) permanece, conteúdo e SHA mudam | **RED de regra inode-only**: mesmo inode não autentica histórico |
| G4-5 — Store real AION | SQLiteChatStore real cria conversa sintética em WAL após checkpoint; cópia bruta somente .sqlite | Store LIVE vê conversa; cópia bruta não | Demonstra risco do método de cópia avulsa, **não acusa** a API oficial de backup AION sem testá-la |

**Não confundir:** o G4 usa SQLite nativo efetivo, mas **não instala nem atesta um hook no VFS**. O descritor do SQLite não é exposto pelo Python; o ensaio G4-3 combina uma conexão SQLite aberta com um FD real aberto por OS. Não implica que toda operação real AION esteja coberta.

## Comparação com testes anteriores

- A185 #1481 provou que Chat, Outbox, Orçamento e Saga usam o mesmo handle em determinado fluxo, e que outra conexão/reabertura pode ignorar o progress handler revogado.
- A186/A187 adicionaram seam de fábrica opcional e reproduziram fábrica falsificada/handler removível.
- G1 #1488 testou ACLs de SQLite sob SIDs/UIDs distintos; G2 #1489 provou que root/admin do mesmo host consegue restaurar piso e banco conjuntamente.
- Este G4 isola **ciclo WAL/SHM real, janela de cópia, leitor antigo/novo e path-vs-handle**, sem reivindicar correção das provas anteriores.

## Critérios de autorização futuros, NÃO fornecidos aqui

1. Gate obrigatório em toda abertura/uso efetivo de conexão e em VFS, WAL, SHM, locks, page cache, FD, backup e restore — inclusive caminhos alternativos/atacante com outro processo; nenhum hook Python opt-in, path stat, SHA ou ACL local isolado é suficiente.
2. Testar restore atômico com efeitos reais sob controle e evidência custodiada fora do mesmo host; testar power loss/reboot H0, sidecars, ABA/same-inode e recuperação após COMMIT incerto. Sem autoridade independente, negar nova reserva/execução.
3. Ater a raiz de confiança e recibos de provedor autenticados à primeira intenção com identificador original independente (G3 ainda RED), sem reenvio automático e sem inferir sucesso após timeout.
4. Documentar comportamento distinto em cada SO. Se Windows negar replace ao vivo e Linux permitir, **ambos são resultados reais e limitados**, não prova de resistência a admin/root.
5. Não habilitar gate canônico vermelho por resultado de teste. Quality/Security completos não foram invocados nesta PR; cinco external-RED por OS e 43 advisories herdados continuam bloqueios históricos.

## Governança e evidência

Workflow: .github/workflows/aion-a190-g4-native-sqlite-files-lab.yml. Teste: test_atlasquant_aion_a190_g4_sqlite_native_files_lab.py.

**CI ainda não executado/conferido ao escrever este preflight**; somente logs, SHA exato e marcadores do GitHub Actions permitirão declarar resultado do laboratório. Um teste que reproduza backup bruto inseguro e saia 0 representa RED de segurança, NÃO homologação.

**0/6 P0 — HARD NO-GO — UNCERTAIN — ZERO_AUTO_RESEND.** Sem merge/main/deploy/Worker, provedores externos, contas novas, credenciais, efeitos, contratação ou gasto.
