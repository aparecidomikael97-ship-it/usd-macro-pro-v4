# A286 — opt-in SQLiteChatStore data_version fence (LAB only)

**Estado:** research LAB, **HARD NO-GO**, **P0 homologados: 0/6**, **ZERO_AUTO_RESEND**, sem Worker/deploy/merge, sem envio a provedor, sem ordens e sem contratação nova.

## Hipótese verificada

A285 mostrou que outra conexão SQLite pode executar uma mudança semântica e revertê-la no **mesmo arquivo/inode**, mantendo `PRAGMA quick_check=ok`. A comparação de pathname do A240/A245 não observa essa sequência. `PRAGMA data_version` é um contador *local a uma conexão aberta*: muda quando **outra conexão** faz COMMIT, mas não quando a própria conexão grava. Uma conexão reaberta perde o histórico desse contador.

## Alteração proposta

`SQLiteChatStore(path, strict_local_data_version=True)` ativa **explicitamente** a barreira local A286:

- captura `PRAGMA data_version` depois do bootstrap do SQLite;
- verifica o contador antes de operações que passam por `_require_open()` e também em `storage_health()`;
- qualquer leitura inválida ou alteração fora da própria conexão trava **sticky FAILED**, sem auto-retry/rebase;
- um COMMIT da **própria conexão** continua permitido, pois o SQLite não modifica esse contador para a conexão escritora;
- `strict_local_data_version=False` é o **padrão deliberado**: os testes A248 permitem várias conexões/processos cooperarem escrevendo a mesma base. Ativar o modo estrito nesse cenário causaria veto legítimo, não provaria ataque.

Não há alteração no Outbox, no Worker, na rede, em ordens ou em implantação. O modo estrito é **somente pesquisa de cenário single-writer**, e não deve ser ativado para operação real.

## Limites de confiança (não resolvidos)

1. **Não autentica o FD/VFS SQLite nativo**, nem prova qual arquivo a conexão usa internamente.
2. **Não é antirollback**: não observa mudanças antes da abertura/reabertura; não resiste a adulteração do host; não prova monotonicidade fora da máquina.
3. **Não identifica escritor**: um processo cooperativo distinto e um escritor não coordenado produzem o mesmo sinal. Em múltiplos processos, o padrão permanece compatível e essa proteção opt-in **não** fecha P0.
4. **Não detecta alterações pela própria conexão**. Em particular, não substitui o marcador de COMMIT incerto nem o bloqueio de reenvio.
5. Janela **TOCTOU** entre a leitura do contador e a execução SQL continua possível.
6. `quick_check=ok` e inode inalterado continuam insuficientes para atestar histórico de eventos.
7. Nenhuma decisão de **SEND**, autoridade de dono, recuperação automática ou homologação deriva de data_version.

## Critérios da bateria A286

- Modo padrão mantém compatibilidade de escritores cooperativos.
- Modo estrito aceita gravação própria.
- Modo estrito bloqueia alteração externa, inclusive após sequência semântica A→B→A e com inode estável.
- `storage_health()` detecta e **não limpa** um bloqueio.
- Contador indisponível também falha fechado, sem auto-retry.
- Reabrir redefine baseline e **não prova a história**.
- Tipo não booleano da política é recusado.
- Outro `SQLiteChatStore` cooperativo também causa veto no modo estrito (documentado e testado).
- Regressões Linux+Windows preservam A233/A240/A245/A248/A249/A267/A282–A285 e os testes existentes.

A286 é uma redução de risco local **opt-in**, não evidência de homologação de P0-5/P0-6. Requer auditoria independente de FD/VFS/rollback e custódia externa antes de qualquer GO real.
