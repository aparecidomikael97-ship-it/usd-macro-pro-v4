# AION P0 / STAGING — revisão independente de troca concorrente de sessão

**20/10/2026.** Revisão em branch isolada derivada do [PR Draft #1348](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/pull/1348). **Nenhuma alteração de produto.** HARD NO-GO, Worker desligado, ZERO_AUTO_RESEND.

## Nova hipótese de ameaça, diferente do SQLite thread-affinity

O PR #1348 corrige o acesso ao banco por múltiplas threads com uma fachada `OperationScopedSQLiteChatStore` por chamada. Entretanto, as funções **`get_or_create_staged_store`**, `close_staged_host_store` e `close_all_staged_host_stores` inspecionam/modificam o mesmo `session_state` sem um bloqueio transacional compartilhado. O `RLock` da fachada protege *operações dentro de UM handle*, mas **não protege a coleção de holders da sessão**, incluindo o `_ACTIVE_SCOPE_KEY`, a troca de principal, tenant ou fingerprint.

Os testes `tests/test_aion_p0_staged_concurrent_session_race_lab.py` usam um `Barrier(2)` **depois** de inicializar as duas fachadas e **antes** de cada instância entrar no estado da sessão. Assim a interleaving incorreta é reprodutível, e não apenas probabilística.

| Ensaio | Estado esperado do código não corrigido | Por que importa |
| --- | --- | --- |
| Duas identidades simultâneas, uma sessão | Dois holders `SQLiteChatStore` connection-free permanecem ativos, apesar de existir somente um `_ACTIVE_SCOPE_KEY` | Uma identidade anterior pode continuar usando a referência |
| Mesmo principal, fingerprints distintos simultâneos | Só o último holder fica registrado, porém a referência anterior fica **ativa e órfã** | Uma rotação de credencial pode não revogar todas as referências |
| Rotação sequencial | Referência anterior revogada normalmente | Demonstra que a lacuna é concorrência na sessão |
| Campos de execução de binding | Todos os flags de efeitos externos continuam `False` | Não há envio real, nem elevação comprovada de autoridade externa |

**Importante:** o GREEN desses ensaios na branch de diagnóstico **reproduz um defeito**, não prova segurança. Não afirmar exploração de sessão real em Streamlit ou produção sem evidência de compartilhamento concorrente da sessão.

## Contrato esperado da correção futura (branch diferente, sem merge automático)

- Proteger atomicamente a verificação da sessão e todas as transições de escopo/credencial (consultar active, preflight de conexões nativas legadas, revogar holders, criar/bindar novo, atualizar `_ACTIVE_SCOPE_KEY`).
- Evitar **qualquer** eliminação silenciosa de `SQLiteChatStore` nativo que não possa ser fechado pela thread proprietária.
- Preservar `OperationScopedSQLiteChatStore.close()` aguardando operação em andamento. Uma referência antiga nunca deve voltar a ser utilizável depois de revogação concluída.
- Suportar sessões Streamlit que não podem ser usadas como chaves hash/weakref, sem armazenar locks contaminando `session_state` ou expondo API ao Worker.
- Exigir testes que agora **negam** duas identidades vivas, referências órfãs ou fingerprint anterior utilizável, incluindo rotação em duas threads, e manter os 17 testes #1195 + oito novos do #1348 intactos.
- Executar testes Windows/Ubuntu e suites canônicas apropriadas; Quality/Security completas separadas, sem waiver ou classificação falsa de GREEN.

Não há autorização de operação real, movimentação financeira, deploy, migração de clientes ou troca da raiz de confiança. Dois P0 SQLite originais seguem sem identificação exata; 32 ERROR históricos Outbox/Saga continuam `OPEN_NOT_WAIVED`.

**Veredito até ensaio:** hipótese de concorrência de sessão em análise, NO-GO para integrar #1348 antes de revisão do achado.