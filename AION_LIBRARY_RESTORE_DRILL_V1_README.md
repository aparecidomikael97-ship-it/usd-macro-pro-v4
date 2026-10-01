# AION Biblioteca — ensaio de backup e restauração PostgreSQL (somente sandbox)

**Estado:** contrato de custódia offline + ensaio destrutivo **exclusivamente** em PostgreSQL 16 temporário do GitHub Actions. Empilhado sobre Draft PR #484, issue de segurança #477. Nenhum backup, restauração, conta, credencial ou documento real é acessado. Nenhum código de produção é ativado.

## Entrega
- `aion_core/library_backup_evidence.py`: digest SHA-256 por streaming de arquivo limitado, com *sidecar* HMAC independente vinculado ao digest/tamanho do arquivo e ao checkpoint HMAC de auditoria preexistente. O sidecar e as chaves **devem** ser guardados fora do banco/backup por infraestrutura confiável; não há armazenamento nem cron automático neste módulo.
- `test_aion_core_library_backup_evidence.py`: 26 novos testes unitários negativos/positivos, sem acesso à rede.
- `test_aion_core_library_restore_drill_pg.py`: seis testes com `pg_dump -Fc` e `pg_restore` **de verdade** via imagem `postgres:16`, opt-in apenas quando `CI=true`, `AION_LIB_RESTORE_DRILL=1` e DSN *exatamente* igual à credencial sintética do serviço GitHub. Executam somente contra `aion_library_sandbox` e o destino separado `aion_library_restore_sandbox` no mesmo contêiner efêmero. Verificam restauração de estado aprovado + auditoria + burn, restauração de documento em revisão, adulteração do arquivo, adulteração do log restaurado, checkpoint obsoleto e revogação da associação do usuário.
- Workflow GitHub de PG efêmero ampliado com etapa de ensaio; gate isolado e Quality passam a incluir os novos testes (os de PG ficam corretamente em `skip` fora de CI explicitamente habilitado).

## Modelo de segurança
1. Só **arquivos sintéticos** no ensaio; `pg_dump` das três tabelas Library e `pg_restore` em um segundo banco efêmero. Qualquer execução fora dessa DSN sintética exata deve ser ignorada, e nenhuma restauração arbitrária é exposta por interface/API.
2. O ensaio **recalcula o hash dos bytes exatos** que serão passados ao `pg_restore`, verifica o sidecar sob chave independente e **depois** valida a cadeia de auditoria do banco restaurado contra o checkpoint autenticado guardado fora do banco. Checkpoints inválidos ou obsoletos não aprovam um ensaio.
3. Proteção contra adulteração depende da custódia **realmente independente** do HMAC/checkpoint. Uma assinatura com segredo vazado, ou arquivada somente dentro do banco adulterável, não é uma prova útil. Não há verificação de legalidade de licenças neste componente.
4. Esta rotina prova **restauração lógica de três tabelas de teste**, não PITR, alta disponibilidade, RTO/RPO, cluster/distribuição, cópia remota, chaves seguras, LGPD/retention ou eficácia de backup de produção.
5. O usuário autenticado e papéis do host continuam simulados; emissão OIDC real, RBAC persistente e fronteira de rotas não estão implementados. A PR não fecha a issue #477.

## Comandos
- Offline: `python -m unittest -q test_aion_core_library_backup_evidence test_aion_core_library_restore_drill_pg` (seis testes PG ignorados sem DSN especial).
- GitHub: a ação separada `AION Library atomic PostgreSQL sandbox` roda 11 testes anteriores em PG real e **seis novos testes de ensaio**, com flags e credenciais sintéticas definidas exclusivamente no job.

**Governança:** não realizar merge/deploy, criação de banco real, migração em produção, upload de PDFs, ingestão/indexação, nem permitir acesso do usuário a objetos Python de baixo nível. Somente uma futura revisão administrativa autorizada poderá avaliar integração.
