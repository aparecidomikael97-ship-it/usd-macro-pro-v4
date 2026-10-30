# A311 — Separação de processos descartáveis para acesso SQLite (somente LAB)

**HARD NO-GO · ZERO_AUTO_RESEND · P0 homologadas 0/6 · sem merge, Worker, deploy, providers ou novas contratações.**

## Por que este experimento existe

A310 concluiu 27/27 verificações do GitHub Actions com proteção opt-in por `sqlite3.set_authorizer` e A309, mas confirmou uma contraprova: o próprio código Python que acessa `SQLiteChatStore.db` pode chamar `set_authorizer(None)`. Uma segunda conexão/processo com acesso ao arquivo ignora os callbacks do primeiro.

A311 **não ativa um Worker operacional**, serviço persistente nem componente para clientes. Usa apenas `subprocess.run` no Python de testes: um subprocesso **descartável por pedido** cria `SQLiteChatStore` com as flags A309/A310 e sai após responder. A parte solicitante recebe somente JSON, nunca o objeto de conexão.

## Contrato de demonstração

- Script único `labs/a311_process_isolated_sqlite_lab.py`, executado como `python -m ... --fixture-child <diretório-temporário>`, com um único documento JSON recebido via `stdin` e uma resposta JSON em `stdout`.
- Diretório precisa ter nome começando por `a311-lab-` e marcador explícito `.a311-disposable-synthetic-only`. O banco é sempre o arquivo `a311-only-synthetic.db` dentro da pasta. **Não** é uma garantia contra um host malicioso; é só um freio contra uso acidental fora do LAB.
- Escopo `owner/tenant/workspace` fixo e sintético; títulos e conteúdos precisam começar com `A311 TEST `. Entrada limitada a 4 KiB, sem comandos SQL do chamador.
- Ações permitidas: criar conversa sintética, gravar mensagem sintética, consultar IDs das mensagens e consultar saúde local. Pedidos de `RESEND`, `RESTORE`, `DEPLOY`, `PROVIDER_CALL`, `SEND_ORDER`, SQL arbitrário ou mudança de escopo são recusados.
- Para cada solicitação, o subprocesso abre/fecha o banco SQLite real com `strict_local_data_version=True`, `strict_private_write_helpers=True` e `strict_sql_authorizer=True`; o solicitante não recebe `store`, `db` ou handles.
- Não há retry do IPC. Timeout, falha do subprocesso, resposta inválida ou status `ACK_UNKNOWN_QUARANTINE` nunca convertem o resultado em autorização.
- Cenário com `SyntheticAckLossConnection` (somente fixture) aplica o COMMIT, perde o ACK e deixa o marcador persistente. Um processo novo recusa gravar/reabrir até inspeção manual.

## Contraprovas obrigatórias (não omitidas)

1. **Mesmo usuário do sistema ainda pode abrir o arquivo SQLite diretamente**, contornando o autorizador dentro do subprocesso. Não há isolamento de contas, ACL de filesystem, sandbox nem VFS nativo comprovado.
2. Se alguém apaga do filesystem o marcador `.aion-message-commit-pending`, um subprocesso novo pode aceitar um identificador diferente e duplicar o efeito já registrado. Isso mostra que não há antirollback/custódia independente.
3. Mesmo com dois pedidos válidos, o mesmo `intent_id` sintético com *message IDs* diferentes ainda pode gerar duas mensagens. **Idempotência semântica P0-3 não está fechada.**
4. O módulo Python e o marcador do fixture são acessíveis por quem controla o código e o host. Isolamento por subprocesso não autentica quem solicita a operação.

## Resultados esperados e limites

Sucesso em LAB demonstra **separação de objetos Python e redução de superfície do protocolo**. Não comprova exclusividade OS, assinatura de origem externa, durabilidade física, rollback, identidade independente do proprietário, idempotência de intenção, ACK de provedor, FD/VFS SQLite ou permissão de retomar.

Todas as respostas reportam `can_authorize_real_effect=False`, `can_resume=False`, `can_resend=False`, `automatic_retries=0`, `zero_auto_resend=True`, `hard_no_go=True`, `p0_homologated=0`, `independent_os_storage_isolation=False`.

Nenhum serviço/servidor fica residente. O módulo não liga Worker, não envia operações externas e só aceita mensagens explicitamente sintéticas de LAB. Toda execução é descartável e sem custos adicionais.

## Validação

```sh
python -m unittest -v labs.test_a311_process_isolated_sqlite_lab
```

Executar em Ubuntu/Windows Python 3.12, sem dependências novas. Regressões A310/A309/A246/A247/A292/A293/A299 na mesma branch. Verde em CI não autoriza merge ou homologação P0.

## Próximo passo de arquitetura

A verdadeira redução de P0-6 exige **separação de principal do sistema operacional, controles de acesso ao banco/arquivo e um escritor exclusivo**, mais trilha durável/independente de intenção e COMMIT/ACK. Em paralelo, P0-5 exige atestar identidade nativa do handle/VFS SQLite, e P0-1/2/4 exigem autoridade, recibos e antirollback independentes. A311 prepara essa separação sem ativar infraestrutura, sem custo novo e sem concluir nenhuma P0.
