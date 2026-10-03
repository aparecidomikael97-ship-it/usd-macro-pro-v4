# Biblioteca AION — ACL por identidade permanente (Sandbox V2)

**Status: laboratório isolado; nenhuma ativação ou migração automática.** A V1 baseada em username e as Drafts anteriores permanecem sem alterações. Este módulo V2 oferece somente uma porta alternativa de consulta read-only e o DDL documentado para tabela nova. Nunca promover V2 isoladamente.

## Problema que o protótipo verifica
Na V1, o fingerprint protege a sessão de quem trocou senha, mas a ACL no PostgreSQL consulta `username + tenant + domain`. Se um username antigo for excluído, as concessões dele não forem revogadas e uma conta nova usar o mesmo nome, a nova conta pode coincidir com linhas de ACL antigas. Não há rota pública operacional da Biblioteca; este é um risco de arquitetura para a futura integração, não um incidente de produção.

## Contrato V2 proposto
- Uma fonte **confiável e independente** fornece `CurrentPrincipal(username, issuer, subject, account_generation, active)`. O ID/geração **nunca** vem do browser, nome, hash de senha, token não verificado ou pedido ao AION. A geração muda ao excluir/recriar a conta. Trocar a senha da **mesma** conta mantém a identidade permanente.
- `PrincipalBoundPostgresMembership` recusa ausência de identidade, conta inativa, IDs inválidos, username diferente ou alteração da identidade durante a consulta. Uma conexão nova usa READ COMMITTED READ ONLY, procura a chave completa `issuer + subject + generation + username + tenant + domain` e não usa cache.
- `MIGRATION_PRINCIPAL_ACL_V2` é **somente documentação**, cria tabela separada `aion_library_tenant_acl_principal_v2`, não executa SQL, não reaproveita grants V1, não cria contas nem chave de assinatura.
- O adaptador existente do AtlasQuant pode receber `membership_provider=v2.roles_for` quando (e só quando) o host tiver identidade durável obtida do registro confiável; teste offline integra o login nativo com esse provider isolado. **Esta PR não implementa o registro de principal nem sua persistência.**
- Não há fallback silencioso para username nem conversão/migração automática dos grants antigos: usuários legitimamente existentes ficam sem acesso até validação/reconcessão no plano administrativo revisado.

## Provas e limites
Testes offline no arquivo `test_atlasquant_aion_library_acl_postgres.py` incluem criação B com mesmo username, mudança de geração, concessão explícita para B, tenant e domínio divergentes, exclusão durante consulta, revogação, valores inválidos e injeção da porta V2 no login real do AtlasQuant. Testes de PostgreSQL efêmero em `test_atlasquant_aion_library_acl_postgres_pg.py` exigem **CI=true e DSN exata do serviço sintético**, incluindo consulta read-only, usuário B sem herdar A, atualização de grants, revogação entre workers e substituição do principal durante a leitura. Se o runner não fornecer o PG efêmero, esses testes são ignorados; não contar skips como execução.

## Etapas obrigatórias fora desta Draft
1. Desenhar autoridade e ciclo de vida persistentes de principal/geração, com desprovisionamento auditável, eventos e prevenção de nomes reutilizados; verificar duas instâncias concorrentes.
2. Planejar implantação idempotente com DBA, concessões SELECT-only e política de isolamento entre tenants. Fazer migração controlada com reconcessão auditada (nunca converter automaticamente linhas V1).
3. Ensaiar backup/restore PostgreSQL e autoridade de ACL/identidade externa de forma coerente com [issue #501](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/issues/501), inclusive revogação posterior ao último backup.
4. Resolver gatilhos e hardening de workflows com executor autorizado (#499), aprovar branch protection e required checks (#325), auditoria independente, LGPD, direitos/assinatura de documentos e chaves externas (#477).
5. Solicitar autorização administrativa específica para qualquer integração real, migração, merge, ativação do runtime ou deploy.

**Borda técnica:** a consulta revalida a identidade após o SELECT, mas não torna instantaneamente impossíveis mudanças externas nos milissegundos após a última verificação. Qualquer futura resposta pública exige autorização fresca e transação integrada com o ponto de leitura/autorização escolhido.
