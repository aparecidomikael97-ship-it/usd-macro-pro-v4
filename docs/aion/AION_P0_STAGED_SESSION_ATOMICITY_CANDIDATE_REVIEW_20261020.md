# AION P0 / STAGING — correção isolada da corrida entre sessões e fingerprints

**Data:** 20 de outubro de 2026. **Escopo:** somente pré-homologação LAB. **Veredito provisório: HARD NO-GO para qualquer uso operacional.** 0/6 P0 homologados, Worker OFF, ZERO_AUTO_RESEND.

## Contexto e evidências RED pré-correção

O PR [#1348](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/pull/1348) já disponibilizava o chat STAGING entre threads ao substituir uma conexão SQLite persistida na sessão pela fachada `OperationScopedSQLiteChatStore`. A revisão independente de sessão [issue #1349](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/issues/1349) isolou um erro de *check-then-act* no host, **diferente da afinidade da conexão SQLite**.

A suíte diagnóstica `tests/test_aion_p0_staged_concurrent_session_race_lab.py` na branch `lab/aion-p0-staged-session-race-review-20261020` usa uma barreira entre duas chamadas concorrentes ao host e mostrou:

1. **Identidades distintas simultâneas:** dois holders `STAGING` permaneciam registrados e vivos apesar de o host indicar somente uma chave ativa.
2. **Credenciais diferentes do mesmo usuário:** a última instância sobrescrevia o holder, mas a anterior continuava **ativa e sem registro para encerramento**.
3. No Ubuntu, uma tentativa inicial também encontrou `sqlite3.OperationalError: database is locked` durante inicialização concorrente do *mesmo* banco antes da barreira. O fixture foi refinado para serializar SOMENTE sua inicialização de SQLite, de modo a isolar a corrida de sessão de outra causa de indisponibilidade. [Run diagnóstico #39424530598](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39424530598) terminou `SUCCESS` em Windows e Ubuntu — **sucesso em reproduzir a lacuna, NÃO segurança aprovada**.

Nenhum caso demonstrou exploração em um Streamlit de produção; os testes usam host real com `dict` de sessão sintético e SQLite temporário, sem fornecedor/Worker.

## Alteração candidata mínima

A branch de correção `lab/aion-p0-staged-session-lock-candidate-20261020`, baseada **apenas no PR Draft #1348, não em main**, altera **um arquivo de produto**:

- `atlasquant_aion_chat_host_staging.py`: `_SESSION_STATE_CHANGE_LOCK = threading.RLock()` e decorador `@_serialized_staged_session_mutation` em **três operações**: `get_or_create_staged_store`, `close_staged_host_store` e `close_all_staged_host_stores`. A região crítica inclui inspeção de `_ACTIVE_SCOPE_KEY`, preflight da thread proprietária para handles nativos, revogação, construção/verificação do novo handle e atualização da sessão.
- O lock é **reentrante** porque `get_or_create...` pode chamar `close_all...`. É *global*, conservador e exclusivo do host STAGING: ele não requer chaves/hash/weakref do `Streamlit.session_state` e não é salvo na sessão. Esse bloqueio **pode afetar throughput** entre sessões independentes; não é desenho de escala para produto B2B.
- Não muda a fachada SQLite do #1348, nem `aion_chat/store.py`, `check_same_thread=True`, Outbox, Saga, Budget, Worker, rede, autenticação ADMIN/tenant/workspace, restauração antirollback ou proteção de recibos.
- Os `RLock` internos de cada fachada continuam controlando leitura em andamento versus close; o host agora controla a **publicação e remoção** de holders em conjunto.

## Teste RED anterior versus GREEN de segurança pretendido

Os **12 testes normativos** da nova suíte `tests/test_aion_p0_staged_session_atomicity_candidate_lab.py` exigem: nenhuma dupla de holders após corrida de identidades, nenhum holder órfão após mudança de fingerprint, oito rotações concorrentes com no máximo uma referência ativa, corrida logout/rebind consistente, preservação de native wrong-thread deny, operação em andamento antes do close, isolamento tenant, negação no modo produção, nenhuma credencial/lock no session_state, nenhuma API de dispatch, impossibilidade de reutilizar handle revogado.

Reexecutar também:
- 17 testes originais da fachada #1195 **inalterados**, oito hardstops novos herdados do #1348.
- 23 módulos raiz LAB e teste estrito de cobertura da Quality, que não pode ter waiver ou arquivo não catalogado.
- Suítes originais canônicas específicas de chat/host e segurança: foundation, golden path, product bridge, surface red-team, resource boundaries, load e resilience.
- Matriz Ubuntu/Windows. A CI deste candidato não é uma `full Quality` de 6.562 testes nem a `Security 365` inteira.

## Limites e riscos ainda abertos

- O lock serializa a *ordem de entrada* de requisições concorrentes, **não autentica qual credential fingerprint é a mais recente**; um chamador com credencial formalmente obsoleta ainda pode tentar uma nova vinculação se as políticas upstream não validarem revogação/epoch. Essa lacuna de identidade precisa de P0 HUMAN_OWNER e autenticação independente.
- Dois processos Streamlit separados ou backup/PITR não compartilham o mesmo lock Python; antirollback distribuído depende de custódia externa, no momento indisponível.
- Timeout enquanto outra sessão mantém o lock pode piorar disponibilidade global. Revisão de desempenho e métricas será necessária antes de eventual homologação comercial.
- Arquivo SQLite substituído, file identity local e `GET` de metadados não provam ausência de efeito do fornecedor.
- **32 ERROR Outbox/Saga OPEN_NOT_WAIVED**, os dois P0 originais SQLite sem associação inequívoca e quatro P0 de identidade/recibo/H0/primeira tentativa seguem abertos.

**Decisão:** permitir apenas revisão humana do PR Draft e novos testes em LAB. Sem merge/deploy, Worker, reenvio, provisionamento de AWS/Cloudflare, serviços pagos, chamada a provedores ou gasto adicional.