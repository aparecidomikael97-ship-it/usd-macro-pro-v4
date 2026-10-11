# AtlasQuant / AION — Pacote mestre de pré-instalação, prova externa e segurança Windows

**Edição V1:** 11/10/2026. **Estado:** HARD NO-GO / preparatório. **Origem:** auditoria GitHub em Drafts #1191, #1204–#1215. **O que existe:** suite AION P0 integrada verde, sem evidências físicas ou root de confiança externo matriculado.

## 1. Princípio fundamental

Este documento **não** autoriza nem executa instalação, matrícula de chave, biometria, TPM/FIDO2, consulta a dados privados, Worker, deploy, merge ou contratação de serviço. O proprietário precisa conceder autorização **específica e posterior** para qualquer validação física. Evidência vinda do próprio manifesto, uma string `HUMAN_OWNER`, sessão ADMIN, URL, token, SHA do GitHub, recibo autorreferido ou assinatura de fixture não é comprovação externa. CI verde comprova somente as verificações que de fato executou.

**Estado da base:** `docs/aion/evidence/AION_WITNESS_EXTERNAL_ENROLLMENT_GATE_V1.json` tem 20/20 requisitos BLOCKED e os campos de evidência/verificador vazios. Não inferir valor da variável global Worker em nuvem: não foi consultada. A função real `independent_worker_source_preflight` bloqueia a leitura do checkpoint antes do GET/CAS/exec, independentemente de input fabricado.

## 2. Planos por bloco, ordem de execução e condições de aceite

### Fase A — proprietário, identidade e origem

Gates: `SOURCE_ROOT_ENROLLMENT`, `OWNER_IDENTITY_CEREMONY`, `TENANT_RESOURCE_REGISTRY`, `INDEPENDENT_KEY_CUSTODY`, `ADMIN_FAILURE_DOMAIN_SEPARATION`.

Pré-requisito **futuro**, não executado: selecionar um Windows concreto com assentimento do proprietário, identificar root de confiança independente do repositório e do usuário ADMIN, mapear tenant/workspace/repo/branch/path/dispositivo com expiração, revogação, scope e custódia distinta. Provar assinatura e verificação de mensagens usando keys não exportáveis quando tecnicamente viáveis, em cerimônia autorizada, sem publicar segredo no GitHub.

Negativas obrigatórias: usuário ADMIN fingindo ser HUMAN_OWNER; troca de sessão; outro dispositivo; outra empresa; repo/branch/path divergente; credencial expirada/revogada; chave ou PIN apresentado pelo próprio solicitante; replay de nonce. **Não há GO** até prova capturada por verificador distinto e auditável.

### Fase B — testemunha independente e recuperação resistente a rollback

Gates: `COORDINATOR_ATOMIC_CAS`, `COORDINATOR_ROLLBACK_TEST`, `SECOND_DOMAIN_IMMUTABLE_HISTORY`, `SECOND_DOMAIN_CURRENT_HEAD`, `FRESH_NONCE_CHALLENGE`, `CROSS_DOMAIN_PARTIAL_COMMIT`, `RECOVERY_REVOCATION_BREAK_GLASS`.

Exigir evidências externas reais de compare-and-swap monotônico, contador/epoch high-watermark independente, retenção imutável sob administração diferente, leitura de head atual com histórico de versões e del markers, challenge fresh nonce com rejeição de replay, PITR/restauração e crash entre dois domínios. Uma operação de resultado `UNKNOWN_OUTCOME` não pode ser repetida automaticamente; exige leitura autorizada + recibo causal antes de reconsiderar.

Negativas: rollback de storage, fork, stale head, retorno HTTP 404/409/422 ambíguo, ACK perdido, concorrência e credencial revogada. Não permitir que uma única pessoa/conta sobrescreva simultaneamente ledger e witness.

### Fase C — Windows e empresas isoladas

Gates: `OWNER_WINDOWS_PHYSICAL_VALIDATION` e `B2B_CROSS_TENANT_NEGATIVE_TESTS`.

**Roteiro físico futuro apenas após autorização separada:** confirmar host, Windows edition/build, patching, BitLocker/Windows Hello/FIDO2 conforme disponível, serviço em identidade de menor privilégio, caminho de dados, backup local e isolamento real de rede/sandbox. Verificar hash, publisher e assinatura do instalador antes de qualquer execução. Testar ações com materiais descartáveis e endpoints isolados, nunca com clientes reais. Fornecer logs sem senhas, chaves, biometria, e-mails ou identificadores pessoais.

Testar empresa A tentando ler/escrever escopo da empresa B, cache entre logins/logouts, reuso de token, permissões de gestor vs proprietário, processos locais sem assentimento, acesso ao sistema operacional via conteúdo de chat. Rejeitar qualquer cenário que alegue isolamento apenas por etiqueta de UI.

### Fase D — privacidade, fornecedores, custo e liberação

Gates: `LGPD_RESIDENCY_AND_OPERATORS`, `FULL_BRL_BUDGET_QUOTE`, `CLOUDFLARE_SECURITY_ROUTE_NO_BYPASS`, `CLOUDFLARE_DO_SINGLE_OBJECT_STORAGE_HEADROOM`, `FINANCIAL_SPEND_APPROVAL` e `RELEASE_MERGE_DEPLOY_APPROVAL`.

Registrar fornecedores/região, subprocessadores, finalidade, retenção e acesso a dados. Fazer orçamento incluindo Workers/DO, segundo domínio de witness, storage, logs, tráfego, recuperação, APIs, câmbio, impostos e margem, comparado ao teto de **referência R$200/mês**; valores reais dependem de cotação vigente e não foram verificados aqui. Demonstrar que rota de segurança não cai em modo bypass durante esgotamento da cota e que há margem real de armazenamento por objeto. Aprovação financeira, merge, deploy, migração e ativação global exigem **decisões distintas** do proprietário.

## 3. Como produzir um dossiê sem transformar alegações em provas

Para cada uma das 20 gates, guardar em local privado autorizado: ID e classe, escopo exato, documento/arquivo de origem, momento de captura, hash calculado por verificador independente, identidade do verificador, dependências, experimento negativo, resultado bruto e decisão. Segredo, biometria, token, PIN, chave privada e documento pessoal **nunca** em PR, print público ou log de CI. O manifesto atual permanece bloqueado; só outro procedimento formal, aprovado e comprovado fora da mesma autoridade, pode atualizar estado.

Marcar `UNKNOWN` ou `BLOCKED` quando evidência for parcial, ausente, impossível de atribuir ao tenant correto ou não reproduzível. Não promover status automaticamente ao preencher `evidence_uri`, `evidence_sha256` ou `independent_verifier`: campos declarativos não são verificação.

## 4. Entrega desta fase, o que é e o que não é

- `atlasquant_aion_first_install_plan_v1.py`: classificador **puramente offline** que produz apenas relatório de pendências, nunca autorização.
- `tests/test_aion_first_install_plan_v1.py`: regressões negativas de falsificação, duplicação, campos ausentes, ausência de efeitos externos e consistência das 20 gates.
- `.github/workflows/aion-first-install-readonly-plan-v1.yml`: CI Windows e Linux que deve passar **somente** quando a recusa é mantida.
- Manifesto externo original e Core V1 **não modificados**.

**Critério de fechamento:** Windows/Linux com suite negativa verde; manifesto ainda 20/20 BLOCKED; nenhuma mudança produtiva nem atividade externa. Isso fecha a **preparação do protocolo**, não o readiness operacional da primeira instalação. Para GO físico ainda há 20 provas independentes faltando.

## 5. Pacote de autorização futura — NÃO EXECUTAR SEM RESPOSTA

Quando o proprietário estiver no PC e quiser iniciar somente o inventário **sem instalação**, o pedido de autorização precisa especificar: host e versão do sistema, janela, arquivos que o coletor pode ler, comandos exatos, local privado dos resultados, informações que não podem ser coletadas, nome do operador e confirmação de que a etapa é somente inventário. A autorização de inventário não concede instalação, biometria, FIDO2, TPM, chaves, deploy ou rede. Essas ações devem ser propostas e aprovadas uma a uma em etapa distinta.
