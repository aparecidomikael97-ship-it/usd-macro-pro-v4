# AION Biblioteca — ACL persistente e testes responsivos V1 (somente sandbox)

Pilha sobre a Draft PR #488. Proposta sem merge/deploy, sem migrar PostgreSQL real, sem habilitar Biblioteca ou ingressar documentos de clientes.

## ACL PostgreSQL autoritativa

`atlasquant_aion_library_acl_postgres.py` declara uma migração a ser executada **apenas** por operador de banco autorizado, fora do processo do aplicativo. O adaptador `PostgresLibraryMembership.roles_for` não cadastra usuários, não concede papéis, não revoga contas e não aceita papéis enviados pelo cliente; consulta `aion_library_tenant_acl` em transação nova `READ COMMITTED, READ ONLY` por chamada, com IDs validados e resposta negada quando há dados inconsistentes ou banco indisponível. O host deve fornecer **conexão PostgreSQL separada com permissão SELECT-only** e usar `roles_for` como callback `membership_provider` de `AtlasQuantLibraryHostAccess` já existente (#486). A fachada PostgreSQL (#487) reconsulta membership antes e depois da inspeção. Isso impede o reuso trivial de permissões em cache, mas **não** garante revogação instantânea caso ela ocorra após a última conferência ou na presença de réplica atrasada. Usar um primário autoritativo; confirmar política de recuperação/backup e auditoria de alterações administrativas antes de produção.

A migração/DDL ainda não foi aplicada fora de banco sintético. O ensaio de CI cria um papel de banco sintético com SELECT-only e verifica que não é possível atualizar a tabela; uma conta de teste privilegiada simula concessão e revogação. Em produção são necessários fluxos separados de provisionamento/auditoria com aprovação humana, chaves, RBAC de tenant e proteção do catálogo/documentos.

## Testes

- Offline: `test_atlasquant_aion_library_acl_postgres.py`: entradas inválidas, esquema, dados adulterados, nenhuma conexão, revogação simulada entre consultas, validação de papéis do host, falha segura e ausência de fallback. Os testes opt-in ficam `skip` fora do ambiente isolado CI com DSN exata.
- PostgreSQL temporário: `test_atlasquant_aion_library_acl_postgres_pg.py`: concessão e revogação reais vistas por instâncias independentes, escopo por cliente/domínio, usuário comum, restrição real de escrita do papel SELECT-only, restrições DDL e integração com a fachada existente antes/depois de revogação. Os únicos valores de conexão disponíveis estão fixados para o banco descartável do CI.
- Browser: `.github/workflows/aion-library-acl-browser.yml` inicia um **aplicativo sintético mínimo** usando a mesma função `render_library_shell` da interface. Playwright confere desktop 1440px e mobile 360/390/412px: sem overflow, sem ações de upload/botões, duas métricas somente no cenário autorizado, e bloqueio nos cenários flag desativada, sessão expirada, papel USER e produção. Não inicia o aplicativo completo, não testa autenticação de clientes reais nem simula upload.

## Restrições bloqueantes

1. Nenhuma rota do aplicativo usa automaticamente a ACL PostgreSQL nesta PR: a criação do `membership_provider` oficial, sua fábrica de conexão, o cofre de segredos e o fluxo de concessões/revogações continuam exigindo integração e revisão independentes.
2. Não interpretar o browser smoke da fixture como teste visual E2E do menu real completo; o teste de ligação estática do admin da PR #488 continua no gate isolado. Um E2E com Streamlit completo (sandbox isolado, autenticação real e dados sintéticos) ainda é requisito antes de ativação.
3. Migração, dados/segredos reais, aprovação de direitos, publicação, merge, deploy e ingerir PDFs estão expressamente fora do escopo; revisão de segurança e autorização específica do administrador são obrigatórias.
4. A PR #472 (ledger de Negócios), a `main` e a tarefa AION English #483 permanecem separadas.
