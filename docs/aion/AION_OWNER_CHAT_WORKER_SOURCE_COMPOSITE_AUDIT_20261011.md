# AION — auditoria de integração real das árvores Owner/Chat e Source/Worker

**11/10/2026 UTC · CANDIDATO CI-ONLY / DRAFT / NÃO MERGEAR NEM INSTALAR**

## Composição exata, sem alteração de PRs existentes

| Entrada | HEAD origem |
| --- | --- |
| `main` congelada para este ensaio | `5744b2b7b17c84331e6f27c569064993ff587782` |
| Owner + Chat + replay/SQLite + handoff (Draft #1203) | `6637638283b39a8cc751da32b9f95347b7560d66` |
| Source/Worker + trust/enrollment/witness e proteções privadas (Draft #1191) | `7d4af5e45b8e80ca43e65171d28255510b76b3b1` |

Árvores do GitHub foram consultadas de forma recursiva e **nenhuma veio truncada**:
`main`: 1650 blobs; UI: 1676; segurança: 1863.

Os caminhos alterados em relação à mesma `main` foram:
- UI/Owner: **40** caminhos, nenhuma exclusão;
- segurança/Worker: **246** caminhos;
- interseção nominal de caminhos alterados: **0**.

A composição foi feita **sem merge de PR e sem rebase de branch original**, criando uma nova árvore Git a partir da árvore exata da segurança `3c622cc2a89ee041b931e00ed6c528d0916c46cb` e apontando para os **40 blobs SHA da UI #1203**, intactos. O primeiro commit composto `1d884220f6e0959bc589b887088fa34ec941c751` tem como único pai o commit da cadeia de segurança #1191. Arquivos de ambos os lados são preservados por suas identidades SHA. Essa operação **não integrou código na `main`**, não alterou branches-fonte e não fez deploy. Posteriormente foram adicionados apenas testes de composição, CI negativa e este relatório a este branch isolado.

**A ausência de colisão de arquivo é evidência estrutural, não prova de compatibilidade semântica**: a suíte no HEAD final desta PR deve ser executada, e componentes que já pressupõem fontes externamente matriculadas continuarão fail-closed.

## Critério de segurança cruzada

A UI #1203 pode produzir:
- `owner_binding.bound=true` diante de um **atestado sintético** já declarado `verified=true` (o módulo é um plano, não verifier confiável);
- `HANDOFF_PREPARED_UNVERIFIED` sem autenticação do destino;
- `binding_digest` sensível à mudança de fingerprint (não assinatura, token nem identidade forte).

Isso nunca pode ser interpretado como:
- owner real matriculado, chave de assinatura instalada, membro de tenant/workspace autenticado, dispositivo autorizado ou witness monotônico;
- `source_verified=true`, autorização do Worker, GET de checkpoint protegido, início de CAS/executores ou liberação do instalador.

A cadeia da segurança #1191 contém `independent_worker_source_preflight`, que retorna `BLOCKED / INDEPENDENT_CHECKPOINT_SOURCE_UNAVAILABLE` antes de qualquer GET de checkpoint. Essa negação **permanece a condição esperada** até que exista trust root independente realmente inscrita e provada, com aprovação separada. A referência de 4 papéis Ed25519 declara todas as condições de matrícula física, consentimento e antirollback como `False`.

### Regressões adicionadas

`tests/test_aion_owner_worker_source_negative_composition.py` usa os próprios módulos concretos da combinação e verifica:
1. login real com senha *sintética* → owner/chat permitem preparação estrutural, mas source gate nega;
2. dados arbitrários de root, pin ou `verified=true` fornecidos pelo solicitante → source gate nega;
3. hash de identidade de sessão, digest de handoff e rotação de fingerprint → source gate continua negando;
4. referência matemática de roster de quatro chaves → não promove matrícula física nem autorização;
5. administrador com sessão revogada/negada → não consegue criar autoridade de origem.

O workflow `aion-owner-worker-source-composite-negative.yml` verifica o **HEAD exato** Windows/Linux, executa os novos testes, os testes originais de origem, faz leitura apenas, usa runner do GitHub e instala apenas dependências de teste do repositório no runner. Nenhuma chave real nem segredo são consultados no ensaio.

## Gatilhos de CI e interpretação dos resultados

A PR Draft é comparada a `main` **somente para iniciar os workflows de integração**. O resultado esperado é que:
- suites de testes offline, UI/Chromium, SQLite, Owners, Core/qualidade passem no código combinado, caso compatível;
- workflow operacional `AION Global Worker Activation Readiness` **permaneça vermelho/BLOCKED**, pois o source trust não existe. Essa falha não é para ser suprimida;
- outros gates de antirollback remoto, conta/credenciais/tenant, Windows físico e pacote permaneçam sem prova, não certificáveis com GitHub Actions.

**Não existe GO** por um teste negativo verde, digest, signature-math synthetic ou simples ausência de colisão de arquivos.

## Próximas decisões dependentes do proprietário e de evidência independente

1. Trust registry externa, matrícula e custódia separada de HUMAN_OWNER/COLLECTOR/witness, vínculo de tenant/workspace/dispositivo e revogação;
2. geração monotônica, antirollback independente e política de recuperação/falha;
3. artefato Windows local assinado com origem auditável, política de IPC/permissões e rollback;
4. aprovação distinta para testes físicos e eventual instalação, sem usar login/PWA como autorização local.

**A primeira instalação permanece HARD NO-GO**. Sem `main` merge, Worker/Render, deploy, ativação de persistência produtiva, despesa, chaves reais ou acesso ao PC.
