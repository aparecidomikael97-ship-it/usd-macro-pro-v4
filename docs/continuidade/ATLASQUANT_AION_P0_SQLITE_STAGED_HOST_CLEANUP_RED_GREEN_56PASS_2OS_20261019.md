# AtlasQuant AION — P0 SQLite: limpeza segura de handles de sessão após falha entre threads

Data 19/10/2026. **RED→GREEN comprovado em LAB no host staging; nenhum dos seis P0 homologado.** HARD NO-GO, Worker OFF, ZERO_AUTO_RESEND, sem merge/deploy/custos e sem conta ou fornecedor real.

## Escopo / rastreabilidade
- Branch `lab/aion-p0-sqlite-staged-host-cleanup-20261019`, derivada do LAB `346eefb83786cacadf6b9c3b8b48a35d79851e5e` (guard `SQLiteChatStore` + guard Outbox).
- Host A118 original `atlasquant_aion_chat_host_staging.py`, blob `18c05d150d6e95cd134c530e801917e54cb1c2ff`; `SQLiteChatStore` LAB `aion_chat/store.py` blob `faafd3b61e90f3a4b3c863dcfc97b83ba32a0f3b`; Outbox LAB blob `cd78ed43ad63888408eb599e28379c193c541de2`. CI verifica essas âncoras de origem; código A118 não está sendo mesclado.
- `test_aion_p0_staged_host_sqlite_cleanup_lab.py`: commit `c83669791fe14f9e2696a016fc5083a2f8ca7a93`. **Dez contratos escritos ANTES do patch**.
- `.github/workflows/aion-p0-staged-host-sqlite-cleanup-lab.yml`: commit `0692d433bbad7bb3ef26a21e7e2ecb315f734668`, readonly Ubuntu+Windows.
- **RED real** [GitHub Actions #39317602864](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39317602864): Ubuntu job `118283028120`, 10 cenários, **5 FAIL, 4 ERROR e 1 PASS**. A sessão removia o holder antes da chamada `store.close()` em `close_all_staged_host_stores` e `close_staged_host_store`. A rotação de binding descartava erro de fechamento com `except Exception: pass`, abandonando o handle e criando outro. `SQLiteChatStore` corretamente negava a chamada cross-thread, mas o **host perdia rastreio de handle ainda aberto**. O teste não demonstrou envio externo ou perda física do banco.
- **Fix LAB** `1cf092cdb4deaa6faa10c35f017e61bffde91580`, `atlasquant_aion_chat_host_staging.py` (blob `c3a3a539bd6be53b4054169946ecd83c4d88f1c7`):
  - `close_all_staged_host_stores`: pré-verificar thread proprietária de TODOS os handles `SQLiteChatStore` presentes na sessão **antes de qualquer remoção**. Se algum pertence a outra thread, negar sem mexer na sessão; para fechar, chamar `store.close()` e só depois `session_state.pop`.
  - `close_staged_host_store`: não remover holder antes de confirmar `store.close()`.
  - `get_or_create_staged_store`: ao rotacionar binding, não engolir exceções de fechamento nem substituir a referência após erro; troca de scope respeita pré-verificação de todos os handles.
  - Não alterar `check_same_thread`, SQLite store/Outbox já corrigidos, Worker, provider, persistência dos recibos, transações ou nenhuma autorização operacional.

## GREEN pós-correção
[GitHub Actions #39317770909](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39317770909), `completed/success`, HEAD `1cf092cdb4deaa6faa10c35f017e61bffde91580`:
- Ubuntu job `118283598221`: **10/10** novos staged lifecycle + **4/4** originais host binding/switch/logout + **15/15** store owner thread + **12/12** Outbox thread + **15/15** nested-transaction/restore/concorrência = **56/56 PASS**.
- Windows job `118283597781`: mesmos **56/56 PASS**.
- **56 cenários distintos, 112 execuções** em dois sistemas. Não equivale à Quality/Security canônica completa nem a teste físico de sessão do usuário. Hash de host original e versões LAB Store/Outbox verificados por workflow.

## O que ainda não está resolvido
1. Pré-checagem por thread cobre somente a situação de handle em thread alheia; não torna mutações de dicionário de sessão atômicas contra duas tarefas que compartilhem e modifiquem estado simultaneamente. Não alegar suporte a Streamlit multi-thread/async definitivo.
2. Se `close()` falhar por uma causa diferente de thread depois de alguns fechamentos bem-sucedidos, a operação de limpeza em múltiplos handles pode ser parcial; o código mantém os holders que não foram fechados, mas não provou rollback atômico. Não confundir com transação distribuída.
3. `ExecutionSagaCoordinator` (`atlasquant_aion_execution_saga.py`) é consumidor explícito de `store.db`: guarda `self.db=store.db` e chama transações `BEGIN IMMEDIATE` diretamente, fora da interface do `SQLiteChatStore`. Necessita investigação de thread proprietário, transação do caller e efeito de falha. Outras classes que guardam `store.db` e outras rotas públicas são pendentes de inventário.
4. `store.db` permanece exposto; código que chama `sqlite3.Connection` diretamente contorna os guards Python da API, mas não a checagem nativa do driver. Não desativar `check_same_thread=True` sem provas adicionais.
5. O método original de `restore_from_backup()` ainda aceita backup íntegro antigo e pode apagar `UNCERTAIN`; requer prova de high-water assinada sob custódia independente e readback do fornecedor, ainda ausentes.
6. Seis P0 pendentes, inclusive H0 reboot físico, identidade HUMAN_OWNER, emissor de recibos e primeira operação incerta. Quality/Security integrais, M71 original e auditoria externa continuam não homologados. Não habilitar Worker, retry, merge, deploy ou serviços pagos.

## Próxima ação orientada a impacto

Auditar `ExecutionSagaCoordinator` e demais consumidores diretos de `store.db` que compartilham conexão entre threads: propor contrato de negação antes do primeiro acesso a SQLite, usando os mesmos padrões de teste RED→GREEN, sem afrouxar as verificações do Outbox e sem tocar em produtor externo. Uma correção no Saga só pode ser considerada no LAB após testes canônicos, especialmente sob reuso de conexão, token de escopo e transações externas.

**Conclusão:** progresso concreto no ciclo de vida do staging host, nenhum P0 declarado resolvido. HARD NO-GO mantido.
