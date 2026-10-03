# AION Biblioteca — fronteira verificável de autorização V1 (sandbox)

**Estado:** contrato offline, simulação de integração, **não habilitar em produção**. Branch empilhada sobre a PR #478, vinculada à issue #477. Preserva a API anterior da `LibraryCatalog` para os testes V1; **portanto acesso direto à `LibraryCatalog` pode contornar o gateway**. Em ambiente real, isso exige encapsulamento seguro e integração de autenticação externa antes de qualquer processamento.

## Implementado

- `aion_core/library_authorization.py`: `AttestationVerifier` valida atestações HMAC-SHA256 em três domínios independentes de confiança: identidade/RBAC, decisão humana e concessão de direitos. As chaves são fornecidas por camada confiável em memória; **nenhuma chave real no repositório**.
- `SecuredLibraryBoundary`: consulta limitada por tenant/domínio e aprovação para indexação sujeita às três atestações verificadas. Vincula os comprovantes ao mesmo documento, versão, SHA256 completo, tipo de licença e escopo, e confere identidade do revisor, direitos de uso e validade temporal.
- Quando o uso previsto for `PUBLISHED`, exige explicitamente o direito `PUBLISH`; para outros escopos, exige `INDEX`. A simples declaração `ALL_RIGHTS_RESERVED` continua insuficiente no catálogo V1.
- `AuthorizedDecision.decision_sha256` é um resumo de auditoria não secreto das três atestações e da decisão. **Não é uma assinatura de auditoria persistente**.
- A fonte de tempo vem do verificador internamente (relógio injetável só para testes) e não é controlada pelos argumentos de cada solicitação.
- Tokens de aprovação repetidos são bloqueados por processo, após transição bem-sucedida; **esse mecanismo não resiste a reinício nem concorrência entre processos**.
- Testes adversariais `test_aion_core_library_authorization.py` exercitam ataques de escopo, manipulação de atestações, papéis, licença, prazos e replay; suítes legadas permanecem sem alteração.

## Limitações inegociáveis para produção

1. HMAC aqui exemplifica prova verificada de um emissor confiável, **não faz login**, OIDC, WebAuthn/FIDO2, Windows Hello ou assinatura assimétrica com não repúdio. Em produção, trocar o emissor de identidade/assinatura por um mecanismo confiável configurado e auditado, sem permitir que um cliente emita suas próprias atestações.
2. Emissões e metadados de licença dependem de **fontes externas verificadas**. Uma assinatura emitida por um serviço mal configurado não prova direitos legais. É obrigatório verificar proveniência/autorização da fonte que concede direitos, expiração e revogação dos grants.
3. Gateway em memória não é prova de isolamento do runtime: **impedir que qualquer fluxo externo chame `LibraryCatalog` diretamente**. Todas as rotas precisam passar pelo adaptador de autenticação e pelo bloqueio de permissões.
4. Persistir de modo transacional e auditável o consumo de aprovação/nonce e a revogação de chaves e licenças. Sem esse componente não é seguro usar em diversos workers, reinícios nem como autorização permanente.
5. Revisar a máquina de estados, modelos de tenant, proteção de conteúdo e observabilidade, executar CI completo, revisão de segurança humana e solicitar aprovação de Mikael antes de qualquer merge ou deploy.

## Execução offline

```bash
python -m unittest -q test_aion_core_domain_registry test_aion_core_evidence_pack test_aion_core_memory_architecture test_aion_core_provenance test_aion_core_security_audit test_aion_core_trust_engine test_aion_core_library_foundation test_aion_core_library_guard_contract test_aion_core_library_authorization
```

Utilize **exclusivamente chaves sintéticas** como as da suíte de testes. Nunca inclua credenciais de produção, tokens de usuários ou conteúdos privados nos fixtures.
