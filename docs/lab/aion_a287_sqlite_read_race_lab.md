# A287 — SQLiteChatStore read-check interleaving: deterministic negative proof

**AtlasQuant/AION LAB only, HARD NO-GO, P0 homologados 0/6, ZERO_AUTO_RESEND.** Não ativa Worker/deploy, não faz envios, ordens ou contratação; a área Negócios segue congelada.

## Questão técnica

A286 adicionou strict_local_data_version=True como modo **opt-in single-writer**. O método _require_open() verifica PRAGMA data_version antes de leituras. A287 testa precisamente a janela entre essa verificação e o SELECT, usando duas conexões SQLite nativas no mesmo arquivo e um agendamento determinístico da segunda conexão.

O laboratório não altera aion_chat/store.py, para evitar regressões e consumo de muitas rotinas de CI enquanto a medida é estudada. Ele importa o SQLiteChatStore real da A286.

## Resultado que os testes devem distinguir

| Cenário | Esperado | Significado |
|---|---|---|
| Guard original A286; segunda conexão confirma COMMIT após check e antes de SELECT | Endpoint retorna; somente health posterior vê LOCAL_DATA_VERSION_CHANGED | Check antes da leitura não cobre uma mudança intercalada |
| Helper LAB postcheck_read_candidate checa novamente após o endpoint | Bloqueia o resultado e trava FAILED | Reduz janela para operações selecionadas, sem autorização real |
| Segunda conexão confirma COMMIT exatamente após o check final | Helper pode retornar e checagem seguinte vê falha | Mesmo o pós-check não prova atomicidade de histórico |
| PRAGMA quick_check=ok e inode idêntico | Permanecem verdadeiros | Não autenticam FD/VFS ou imutabilidade do histórico |
| Própria conexão grava sem concorrente | Operação permitida | Evita veto falso nesse caso |

Endpoints pesquisados: get_conversation, list_conversations, get_message, list_messages, get_latest_summary, retrieve_messages.

## Limites obrigatórios

1. O helper é um **protótipo isolado**, não está conectado aos métodos oficiais nem ao Outbox.
2. Como o check não é atômico com devolver o resultado, um commit posterior segue possível. Sem raiz de confiança externa, nem um precheck nem postcheck validam histórico passado.
3. Não autentica FD/VFS nativo, escritor, proprietário, testemunha off-host, rollback persistente ou resultado de COMMIT incerto.
4. Não permite reenvio automático, sends, deploy, Worker, ordens ou mudança do HARD NO-GO.
5. A286 não pode ser ativada globalmente sem resolver o caso legítimo de conexões/processos cooperativos.

## Critério para próxima integração

Se a bateria A287 passar em Ubuntu/Windows, propor apenas uma integração opt-in de pós-check em todos os caminhos de leitura, com testes de corrida e compatibilidade. Tal mudança **não** fecha P0-5/6 e deve passar regressões de chat/SQLite antes de qualquer consideração.
