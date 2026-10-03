# AION Biblioteca — integridade de leitura e pré-validação de recuperação V1

**Status: sandbox, aguardando revisão.** Bloco de segurança isolado, empilhado sobre Draft PR #482. Nada aqui migra, restaura, indexa, autoriza merge/deploy, configura login ou consulta documentos de clientes reais.

## Escopo implementado

- `aion_core/library_recovery_gate.py`: `LibraryRecoveryGate` obriga sessão verificada via `ExternalIdentityBridge` **fornecido pelo host** e RBAC de fonte confiável por cliente (tenant), domínio e ação READ. Impede consultas fora do escopo e reavalia permissões após a leitura para reduzir o risco de revogação durante a consulta. O callback externo é um contrato de integração; **não é login/OIDC/JWKS implementado**.
- Consulta a tabela documental, cadeia cronológica de auditoria e registro persistente de aprovação em transação `REPEATABLE READ READ ONLY` no PostgreSQL. Recusa documentos revogados, estados inesperados, hash adulterado, histórico sem gênese, transições desconhecidas, aprovações sem registro de consumo e base indisponível. Retorna relatório **resumido, sem conteúdo do documento**.
- `admin_checkpoint()`: somente administrador com permissões verificadas pode gerar um ponto de comparação contendo SHA256 documental, estado, hash/sequência final da auditoria e MAC HMAC independente. O servidor deve arquivar o checkpoint **fora da mesma base**, sob segredo separado. `compare_archived_checkpoint()` verifica a autenticidade e compara o estado atual ao checkpoint arquivado; recusa divergências (inclusive mudanças legítimas: exigem checkpoint administrativo novo).
- **Nunca restaura dados**: é uma barreira de **pré-validação** que interrompe a recuperação quando o histórico é inconsistente, não uma prova de backup recuperável ou de conformidade regulatória.

## Testes

- 36 novos testes offline em `test_aion_core_library_recovery_gate.py`, cobrindo login/RBAC de fonte confiável *simulados*, isolamento tenant/domínio, expiração/revogação, adulteração de auditoria, perda da aprovação, checkpoint válido/adulterado/obsoleto e indisponibilidade do banco. Chaves, tokens e bases dos testes são **totalmente sintéticos**.
- 6 novos testes opcionais reais em `test_aion_core_library_recovery_pg.py`, executados só quando o CI injeta DSN restrita à instância PostgreSQL 16 temporária. Independente do ambiente de produção. Workflow existente PostgreSQL atualizado nesta branch para as 11 verificações (5 da PR #482 + 6 novas).
- Suíte local completa: **310 testes descobertos, 299 executados, 11 ignorados por falta de PostgreSQL temporário; nenhum erro**. `compileall` aprovado. A aprovação das seis novas verificações em PostgreSQL no CI remoto ainda precisa ser confirmada antes do fechamento deste bloco.

## Limitações e próximas etapas

1. **Autenticação real:** não existe implantação IdP/OIDC/JWKS/PKCE nesta branch. O host deve implementar `verify_token`, armazenamento de sessão, `lookup_roles` e rotas que só exponham o serviço seguro; o catálogo e os adaptadores brutos continuam acessíveis no processo Python e não podem ser exportados a clientes.
2. **Checkpoint não é backup:** HMAC não fornece não repúdio ou resistência a administradores que tenham a mesma chave. Exige custódia de chaves, rotação, arquivo externo imutável e revisão administrativa. Backup consistente, PITR, restauração testada e evidência de redundância continuam pendentes.
3. **Escopo limitado:** um documento por requisição; suporta somente `GENESIS` e `APPROVE_INDEX` da PR #482. Documentos revogados, eventos futuros, auditorias longas/incompletas e inconsistências são recusados até implementação e teste de política específica. Checagem do registro de aprovação confere presença e marca temporal, mas não reconstitui a concessão assinada original nem prova direitos legais.
4. **Operação:** requer credencial SELECT-only separada do PostgreSQL do app, PostgreSQL primário/isolamento configurados, validação E2E do servidor real e revisão de segurança. Nada está integrado a Render, aos endpoints da interface ou ao usuário administrador real.
5. **Governança:** manter toda a stack #473 → #476 → #478 → #479 → #480 → #481 → #482 → nova PR em rascunho. O ledger da área Negócios (#472) e as prioridades da aba Negócios/Núcleo permanecem separados. Não mesclar nem publicar sem autorização explícita do Mikael.
