# AION Biblioteca — Login nativo + consulta PostgreSQL verificada (sandbox V1)

**Estado:** adaptador de leitura server-only para futura aba do AION. Empilhado na PR #486. **Não** monta rota Streamlit/API, não acessa contas ou bancos de produção, não cria usuários, não lê os bytes dos documentos, não faz indexação e não aprova conteúdo.

## Por que este bloco existe

A PR #486 conecta o login local atual do AtlasQuant a uma ACL específica da Biblioteca, mas seu exemplo de leitura usa o catálogo em memória. A PR #482 introduziu o armazenamento autoritativo de documentos/consumos/auditoria em PostgreSQL, e a PR #484 acrescentou inspeção consistente e falha segura de integridade. Esta proposta une os contratos **sem fallback ao catálogo antigo**.

## Interface

`atlasquant_aion_library_postgres_preview.py::LibraryPostgresReadFacade` recebe somente dependências preparadas **no servidor**:

- `AtlasQuantLibraryHostAccess` com provedores confiáveis e atualizados de login, registro de usuários e ACL tenant/domínio;
- `AttestationVerifier` cujo emissor e chave de identidade devem coincidir com o login do host;
- fábrica de conexão PostgreSQL **SELECT-only** protegida e chave HMAC de checkpoint independente;
- relógio confiável.

A chamada `read_preview(tenant_id, domain_id, entry_id)` exige login explícito e ACL. `OPEN` ou `PREVIEW` continuam proibidos. Emite identificador opaco efêmero apenas internamente e consulta `LibraryRecoveryGate.inspect`, que verifica o documento na fonte PostgreSQL em transação de leitura consistente, inclusive auditoria e consumo da aprovação. Depois revalida o login atual, identidade e ACL. Devolve apenas `entry_id`, `version`, `state`, `integrity_checked=True`; **nunca expõe hash de conteúdo, nome do cliente, identificador de sessão, documento ou eventos de auditoria brutos**. Um leitor comum só recebe metadados de documentos já aprovados, e revisores/administradores precisam de associação explícita para consultar estado de revisão. Nenhum `ADMIN` recebe privilégios entre empresas por padrão.

O serviço é um **contrato para o aplicativo montar futuramente**, não uma rota ativa nem garantia de autorização contínua depois que a resposta foi emitida. O host deve manter a conexão e provedores completamente fora de entradas do usuário e revalidar cada requisição; não fazer cache de retornos confidenciais.

## Evidência e testes

- `test_atlasquant_aion_library_postgres_preview.py`: 33 testes negativos/positivos em ambiente local, incluindo negação de acesso cruzado, tentativas de elevação, sessão/ACL alteradas durante leitura, erros do banco e respostas forjadas do verificador.
- `test_atlasquant_aion_library_postgres_preview_pg.py`: 5 testes opt-in contra o **PostgreSQL 16 temporário** do GitHub usando o login local verdadeiro da árvore GitHub e as tabelas autoritativas. A suíte testa leitor antes/depois de aprovação, isolamento, auditoria adulterada, falta do consumo da aprovação e sessão revogada. **Ignorada localmente** e exige `CI=true` e DSN sintética exata.
- Gate isolado e Quality atualizados para os dois testes. Workflow PostgreSQL atualizado para executar a suíte real somente em ambiente sintético.
- A evidência local usa uma cópia de teste compatível de `atlasquant_access_control.py` porque o pacote incremental não contém todo o repositório. O GitHub testa com o arquivo real da branch empilhada; verificar CI antes de considerar validado.

**Atenção:** os testes que passam não comprovam que Streamlit ou qualquer endpoint está protegido. O serviço não deve ser instalado diretamente em um servidor sem revisão de segurança.

## Pendências #477 antes de habilitar no ecossistema

1. Decisão operacional sobre banco e credenciais **SELECT-only** reais, proteção de segredos e endpoint interno autenticamente controlado. Montar a aba somente depois de revisar o fluxo de autenticação Streamlit e impedir invocação de serviços brutos por usuários.
2. Persistir ACL por cliente em serviço confiável com revogação, testes E2E de tela e ataques de concorrência envolvendo mudanças na sessão, além de revisar as regras de retenção LGPD.
3. Definir integração de identidade corporativa/OIDC (se necessária), comprovação independente de licenças, revogação de direitos e gestão/rotação de chaves.
4. Recuperação produtiva com cópias independentes e testes PITR/DR, análise de segurança externa, validação de custos, aprovação administrativa explícita para merge/deploy.

O ledger Business #472, a aba AION English #483, a `main` e a produção permanecem intocados. Todas as PRs da stack continuam **Draft**.
