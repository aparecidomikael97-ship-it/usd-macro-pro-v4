# AION Biblioteca — Registro durável de identidade (leitura sandbox)

**Estado:** protótipo **não montado**, somente leitura, sem migração/ativação. [Issue #502](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/issues/502). A ACL por principal V2 é proposta na Draft #503; a V1 de username e login AtlasQuant permanecem intactos.

## Limite de confiança e identidade

`PostgresPrincipalRegistry` recebe um callback `verified_host_account` do servidor confiável. O callback **deve** fornecer `VerifiedHostAccount` atual com username, issuer, subject permanente, geração de conta, fingerprint atual e status ativo. Isso não pode ser derivado apenas de username, hash de senha, dados de formulário, request, JWT sem validação independente nem da própria tabela de ACL/registro. O login V1 atual **não oferece issuer, subject e geração duráveis**; por isso o registro ainda não pode ser conectado ao app. O callback simulado nos testes é um contrato, não um provedor de identidade implantado.

A tabela documental `aion_library_principal_registry_sandbox` usa PK (issuer, subject, generation), binding da credencial, ativo/revogado e índice único parcial que impede dois sujeitos ativos com mesmo issuer+username. O leitor faz transação nova READ COMMITTED READ ONLY, exige correspondência exata de identidade e credencial, rejeita ausência/duplicação/conta aposentada, reconsulta o callback após a consulta ao PG e nunca faz fallback para ACL de username V1.

O callback `registry.current_principal` retorna `CurrentPrincipal` V2 e pode ser injetado em `PrincipalBoundPostgresMembership` somente em teste ou futura integração aprovada. O reader não tem `INSERT/UPDATE/DELETE/DDL`, não cria usuários, não autentica senhas e não guarda secrets. A DDL é **somente documentação**; apenas fixtures PG opt-in executam o SQL em banco efêmero.

## Ciclo de vida esperado (futuro e bloqueado)

1. Cadastro: autoridade administrativa independente emite ID imutável e geração imprevisível; persiste controle de conta com auditoria e verifica que não existe outro principal ativo para o mesmo issuer+username.
2. Exclusão: aposenta a identidade e remove/nega grants de tenant/domain da geração antiga. Novo usuário com mesmo nome exige **nova geração e regrant explícito**, mesmo que possua credencial idêntica.
3. Rotação de senha da **mesma conta**: invalidar a sessão antiga e, em operação privilegiada coordenada, atualizar `credential_binding` do mesmo principal; enquanto houver desencontro, negar acesso, sem migrar grants antigos silenciosamente.
4. Recuperação: autoridade externa de identidade/revogação deve reconciliar o backup. Nunca reativar um grant anterior à exclusão/revogação por restauração de snapshot. Definir RPO/RTO, custódia de chaves e fail-closed se o histórico autoritativo não estiver disponível.

## Evidências previstas

Testes offline no arquivo já listado no Foundation/Quality `test_atlasquant_aion_library_acl_postgres.py`: chave completa, consulta nova, fechamento de conexões, rejeições por mudança de identidade, duplicação, conta inativa, credencial desatualizada, reautenticação correta e ligação com ACL V2. Testes reais PostgreSQL 16 em `test_atlasquant_aion_library_acl_postgres_pg.py` exigem `CI=true` e DSN sintética exata; registram duas gerações em momentos diferentes, ACL A persistente, nenhum acesso de B até registrar/reconceder, revogação entre workers, índice de unicidade, negação a SELECT-only para UPDATE/INSERT e substituição de identidade durante leitura.

**Importante:** aprovação do Quality/Foundation sem PG pode incluir skips. Só a execução separada do workflow PostgreSQL sintético no MESMO SHA comprova os casos de banco. Nenhum desses testes comprova ainda identidade persistente real, operação multi-host em produção ou DR independente.

## Pendências para qualquer ativação

- Plano de controle privilegiado e auditado para criação, rotação, exclusão e concessão de ACL, com origem verificável das gerações/IDs. Revisão de concorrência e rollback, exportação/exclusão LGPD.
- End-to-end do host de autenticação com fonte persistente **independente**, rejeição de claims de cliente, DB SELECT-only realmente separado e auditoria de migração V1→V2 sem grants herdados automaticamente.
- Ensaio de backup/restore da fonte de identidades + ACL V2 com revogação posterior ao backup (#501), chaves/âncoras externas e auditoria independente (#477).
- Gatilhos protegidos dos workflows main (#499), proteção de branch/required checks (#325), autorização expressa antes de merge, migração, publicação ou deploy.

**Esta Draft não monta nova rota, não manipula usuários/segredos/PDFs reais, não altera o workflow protegido nem realiza qualquer operação no ambiente produtivo.**
