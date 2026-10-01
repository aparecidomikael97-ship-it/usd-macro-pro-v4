# AION Biblioteca — adaptação ao login existente do AtlasQuant (sandbox V1)

**Estado: pesquisa e integração contratual, SEM ativação de rotas ou login de produção.** Base: Draft PR #485, issue de segurança #477. Este módulo reutiliza a autenticação local já presente no AtlasQuant, não inventa um segundo login nem implementa OIDC, FIDO2 ou reconhecimento facial.

## Contrato preparado

- `atlasquant_aion_library_host_access.py` depende de `atlasquant_access_control.py` existente no repositório. Confere `AUTHENTICATED` com acesso permitido, papel e usuário consistentes, `session_is_current` com a configuração **atual** de usuários do servidor, o conjunto exato de permissões da função e a idade/ociosidade da sessão. Nunca aproveita os modos `OPEN` ou `PREVIEW` do app como autorização de Biblioteca.
- O servidor fornece três funções de confiança: `access_provider` (resultado do fluxo existente de autenticação, não dados da requisição), `users_provider` (registro corrente `AccessUser`, incluindo alterações/revogação) e `membership_provider` (ACL SEPARADA por principal, empresa/tenant e domínio). Chaves e emissores ficam exclusivamente no servidor; testes usam apenas bytes sintéticos.
- Funções `USER` e `SALES` nunca obtêm permissões de aprovação; podem apenas ser leitores se a ACL do servidor as conceder explicitamente. `ADMIN` **não** recebe automaticamente acesso a outras empresas. Para aprovação, precisa tanto da função apropriada quanto de uma ACL específica, além das assinaturas de aprovação e direitos exigidas pelas camadas #479–#482.
- Emite apenas atestado de identidade HMAC compatível com o `ExternalIdentityBridge` existente. Usa handle aleatório de curta duração guardado em memória, com verificação da sessão e ACL a cada emissão. A função host-only `read_catalog_for_host` exemplifica leitura segura de METADADOS do catálogo legado: leitores comuns recebem apenas registros previamente aprovados; um revisor com ACL específica pode visualizar revisão.
- As funções de emissão de atestados, provedor de identidade, catálogo bruto, ACL e chaves não podem ser expostas em HTTP, voz, chatbot, ferramentas do agente nem JavaScript no cliente.

## Evidência e pré-requisitos

- Na cópia local do handoff da PR #485: **383 testes descobertos, 366 executados, 17 testes opt-in de PostgreSQL ignorados, 0 falhas**. Desses, **41** são da nova suíte. Testes locais usam fixture *compatível*, não o repositório inteiro. O GitHub CI deve validar esta suíte contra o **módulo de login real** antes de reivindicar integração.
- Blobs host verificados para revisão no commit-base #485: `atlasquant_access_control.py` = `19a775fbecdcc05bb89439f6c587604ca55af1fe`, `atlasquant_access_panel.py` = `8cea322a9b7607c8a822dea16ef635f3c268bf70`, `aion_core/library_security_runtime.py` = `1a32f63e4d37801e189c3c13cbb608265dab5277`.
- Sem dados de usuário real, segredos de produção, serviços de terceiros ou novos pacotes pagos.

## Impedimentos obrigatórios para produção

1. Este é um **adaptador server-only não montado na UI/HTTP**. O `render_access_gate()`/`st.session_state` existente precisa ser conectado apenas em ponto de entrada confiável, com teste E2E de autenticação real, logout, sessão revogada e revalidação das permissões em cada solicitação. Uma instância configurada com callables fornecidos pelo cliente seria insegura.
2. `atlasquant_access_panel.py` mantém política própria de duração da sessão. As constantes foram espelhadas aqui apenas para sandbox; devem ser compartilhadas em módulo canônico antes da integração real, com testes de regressão.
3. **Atestados HMAC previamente emitidos não são cancelados magicamente** quando alguém perde ACL. O ponto de entrada precisa emitir uma prova nova a cada operação e reconsultar a ACL. Qualquer verificador de armazenamento deve incorporar revogação quando exigir validade imediata.
4. `read_catalog_for_host` lê o catálogo legado **em memória**, enquanto #482 salva a versão transacional em PostgreSQL. É proibido expor ambos simultaneamente em produção; escolher um armazenamento autoritativo e desenvolver a consulta transacional escopada/autenticada.
5. Não há vínculo automático com Portal do Cliente, consentimento LGPD, concessão jurídica de direitos/licenças, armazenamento externo de checkpoints, backup real ou IdP OIDC/JWKS. A autenticação local hoje é uma configuração com usuários PBKDF2; integrar SSO/IdP real exigirá decisão técnica e configuração confiável separadas.
6. Não executar merge, deploy, indexação/ingestão, publicação ou ativação por causa desta PR. Manter #472 (ledger Negócios) isolada.

## Teste da branch empilhada

```bash
python -m unittest -q test_atlasquant_aion_library_host_access
python -m unittest -q test_aion_core_domain_registry test_aion_core_evidence_pack test_aion_core_memory_architecture test_aion_core_provenance test_aion_core_security_audit test_aion_core_trust_engine test_aion_core_library_foundation test_aion_core_library_guard_contract test_aion_core_library_authorization test_aion_core_library_security_runtime test_aion_core_library_shared_approval_port test_aion_core_library_atomic_store test_aion_core_library_atomic_pg test_aion_core_library_recovery_gate test_aion_core_library_recovery_pg test_aion_core_library_backup_evidence test_aion_core_library_restore_drill_pg test_atlasquant_aion_library_host_access
```
