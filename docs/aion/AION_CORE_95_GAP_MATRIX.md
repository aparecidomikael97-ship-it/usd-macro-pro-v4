# AION Core 95+ — matriz de lacunas

Data da leitura: 2026-09-29
Issue: #325
Base observada: `main` @ `2c9dade6a87d6f618f05cbb628eb35cee2f3a8a1`
P0 em revisão: Draft PR #326, branch `cursor/aion-core-hardening-p0-v1`

Status usados: EXISTENTE, PARCIAL, AUSENTE, NÃO VERIFICADO.
Nenhuma linha abaixo afirma execução em produção. Teste de unidade não é runtime de produção. Workflow verde não é ruleset obrigatório.

| Capacidade | Status | Arquivos existentes | Testes existentes | Evidência | Risco | Lacuna | Prioridade | Ação proposta |
|---|---|---|---|---|---|---|---|---|
| Guardian / Proof of Safety | EXISTENTE | `atlasquant_aion_core.py`, `atlasquant_aion_fortress.py` | `test_atlasquant_aion_core.py`, `test_atlasquant_aion_fortress.py`, `test_atlasquant_aion_security_adversarial.py` | `guardian_decision` nega ação desconhecida e trading real. `proof_of_safety` bloqueia fonte sem autoridade. | Aprovação sensível ainda é contrato puro, não um executor único de produção. | Caminho de execução sensível real de ponta a ponta permanece NÃO VERIFICADO. | P0 | Manter o contrato; não tratar PASS como execução. |
| Flags booleanas exatas | PARCIAL | `atlasquant_aion_core.py`, `atlasquant_aion_fortress.py`, `atlasquant_aion_resilience.py`, `atlasquant_aion_memory.py`, `atlasquant_aion_model_router.py`, `atlasquant_aion_provider.py`, `atlasquant_aion_workspaces.py`, `atlasquant_aion_entitlements.py` | testes desses módulos e `test_atlasquant_aion_security_adversarial.py` | Writer de checkpoint, rota paga, transporte de provider, nível de desenvolvedor e entitlement só aceitam `True`. Strings e números foram reproduzidos como liberação e agora bloqueiam. | Outros módulos ainda podem usar `bool(valor)` fora destes sinks. | Varredura completa de flags privilegiadas no repositório não foi feita. | P0 | Continuar só onde a flag concede privilégio. |
| Fronteira de conteúdo externo | EXISTENTE | `atlasquant_aion_fortress.py` | `test_atlasquant_aion_fortress.py`, `test_atlasquant_aion_security_adversarial.py` | WEB, DOCUMENT, EMAIL, TOOL_OUTPUT, EXTERNAL_AI e UNKNOWN não emitem ação. | Detecção de texto não é a fronteira; a classificação da origem é. | Conteúdo malicioso armazenado e depois relido como memória não tem quarentena própria. | P0 | Não promover conteúdo externo a política. |
| Delegação e firewall de agente | EXISTENTE | `atlasquant_aion_resilience.py` | `test_atlasquant_aion_resilience.py`, `test_atlasquant_aion_security_adversarial.py` | Capacidades sensíveis são não delegáveis. Escopo e evidência ausentes bloqueiam. Workspace diferente bloqueia. | Mensagem livre entre agentes ainda não tem digest próprio. | Protocolo estruturado entre Prime, Shadow e Sentinel está AUSENTE. | P0/P1 | Reusar o firewall; não criar um segundo guardian. |
| Isolamento de tenant | PARCIAL | `atlasquant_aion_tenant.py`, `atlasquant_aion_tenant_privacy.py` | `test_atlasquant_aion_tenant.py`, `test_atlasquant_aion_tenant_privacy.py`, teste cruzado no adversarial | Namespace depende de credencial. Acesso cruzado só retorna verdadeiro para o próprio namespace. | Papel de login não é entitlement. Runtime persistente de assinante não está confirmado pelo próprio resumo de readiness. | Provisionamento real e backend compartilhado continuam desligados. | P0 | Não habilitar shell de assinante nesta etapa. |
| Isolamento de workspace | PARCIAL | `atlasquant_aion_resilience.py`, `atlasquant_aion_workspaces.py` | testes de delegação e workspaces | Delegação ACTIVE fica presa ao `workspace_id`. | Não foi reauditado cada autorizador de workspace nesta sessão. | Escalada entre workspaces fora da delegação permanece NÃO VERIFICADO como cobertura total. | P0 | Ampliar testes só sobre contratos já existentes. |
| Resource governor / watchdog / circuit breaker | PARCIAL | `resource_governor` em `atlasquant_aion_resilience.py`; profundidade e fan-out em `atlasquant_aion_loop_governor.py`, reusando `autonomy_budget` | `test_atlasquant_aion_resilience.py`, `test_atlasquant_aion_chaos_recovery.py`, `test_atlasquant_aion_loop_governor.py` | O plano bloqueia profundidade, fan-out, ciclo, escopo cruzado, risco REAL_TRADING e orçamento de recurso estourado. Não inicia worker e não concede permissão. | O governor não é consultado pelo worker global nem pelo executor. | Integração no caminho real de delegação permanece NÃO VERIFICADO. | P1 | Não ligar worker global para provar o contrato. |
| Recovery / checkpoint | PARCIAL | `atlasquant_aion_recovery.py` | `test_atlasquant_aion_recovery.py`, `test_atlasquant_aion_chaos_recovery.py` | O preflight recomputa `checkpoint_integrity_report` e bloqueia claim ou digest divergente. Restore sem `approved is True` retorna BLOCKED. | RPO/RTO reais e restore em ambiente operacional não foram exercidos. A revisão git do SHA contra os bytes continua no carregamento, não neste preflight offline. | Drill de backup/restore fora de harness local está NÃO VERIFICADO. | P0 | Não executar restore real nesta sessão. |
| Durable tasks | PARCIAL | `atlasquant_aion_durable_tasks.py` | `test_atlasquant_aion_durable_tasks.py` | Histórico limitado de chaves consumidas sobrevive a normalize, pause, resume e snapshot. Replay depois de nova falha não incrementa tentativa. Chave nova só passa nos gates de retry. | Dois workers reais concorrentes e persistência parcial em disco não foram simulados. | Cobertura continua no contrato em memória, não num broker. | P2 | Não criar um segundo motor de tarefas. |
| CODEOWNERS | EXISTENTE | `.github/CODEOWNERS` | revisão do arquivo na #326 | Arquivo cobre áreas AION, workflows e deploy. | O arquivo não obriga review. | Enforcement depende de ruleset administrativo. | P0 | Ação administrativa, não código. |
| Dependabot | PARCIAL | `.github/dependabot.yml` | arquivo presente | Configuração semanal de Python e Actions. | Ativação no GitHub e PRs gerados não foram observados nesta sessão. | Efeito operacional NÃO VERIFICADO. | P0 | Confirmar no GitHub após merge. |
| Security gate CI | EXISTENTE | `.github/workflows/aion-core-security-gate.yml` | jobs da #326 | No SHA `76f34e8c`, os dois jobs do gate terminaram SUCCESS. | O job ainda não é required check. | Sem ruleset, o gate pode ser ignorado no merge. | P0 | Documentar checklist; não alterar proteção da main nesta sessão. |
| Quality workflow | PARCIAL | `.github/workflows/quality-tests.yml` | `test_quality_workflow_coverage.py` | SHA `76f34e8c` falhou porque os dois testes novos não estavam listados. Correção entra neste bloco. | Resultado do workflow após a correção ainda precisa de execução. | CI pós-correção NÃO VERIFICADO até o próximo run. | P0 | Registrar todo `test_*.py` novo. |
| pip-audit | EXISTENTE | job `Supply-chain audit` | run `36517577045` SUCCESS no SHA anterior | O job executou `pip-audit -r requirements.txt`. | Sucesso anterior não cobre o diff novo até o próximo run. | Advisories futuros continuam dependentes do lock/ambiente. | P0 | Manter o job sem path filter. |
| SAST | PARCIAL | Bandit no security gate | run anterior SUCCESS | Bandit em severidade alta nos módulos listados. | CodeQL/code scanning não foi habilitado. Licenciamento NÃO VERIFICADO. | SAST não cobre o repositório inteiro. | P0 | Não substituir Bandit por promessa de CodeQL. |
| SBOM | PARCIAL | job CycloneDX do security gate | validação em memória no job | O job gera e valida CycloneDX do ambiente resolvido. | O SBOM não é publicado como artefato de release nem assinado. | Proveniência de build assinada está AUSENTE. | P0 | Manter geração no CI; assinatura fica fora desta sessão. |
| Pinagem de Actions | PARCIAL | workflows usam tags major, por exemplo `actions/checkout@v7` | inspeção do workflow | Tag major não é digest imutável. | Troca da tag major pode alterar o gate. | Pin por SHA não foi aplicado neste bloco para não ampliar o diff de CI sem revisão própria. | P1 | Pinagem em bloco separado, com checagem de disponibilidade. |
| Prime + Shadow + Sentinel | PARCIAL | `atlasquant_aion_critical_review.py`; `protocol_shadow_probe` continua sendo outro contrato de readiness | `test_atlasquant_aion_critical_review.py` | Papéis exigidos continuam os mesmos. O mesmo principal não pode ocupar papéis independentes. Review de outro tenant, workspace, task_ref ou plan_version não é aceito. `sensitive` só vale se for bool. | O contrato não está ligado a um executor de produção. `ACCEPT_PLAN` não chama Guardian sozinho. | Integração com o caminho real de tarefa continua NÃO VERIFICADO. | P1 | Não criar chatbots paralelos. |
| Protocol firewall entre agentes | PARCIAL | `seal_agent_message` / `validate_agent_message` no contrato de review; `agent_firewall` segue para capacidade | `test_atlasquant_aion_critical_review.py` | Na leitura, capability, permissions, tenant, workspace, papel, agente, versão e nonce são revalidados. Schema desconhecido bloqueia. Segredo em conteúdo ou ref é redigido e bloqueia. Digest é fingerprint canônico, não assinatura. | O validador só protege quem o chama. Não há PKI. | Callers antigos ainda podem tratar texto livre como autoridade se não passarem por este contrato. | P1 | Adotar o contrato nos fluxos novos; não reescrever o Guardian. |
| Blast radius / quorum | PARCIAL | `classify_blast_radius` e `autonomy_budget` | `test_atlasquant_aion_critical_review.py`, `test_atlasquant_aion_fortress.py` | Fatores como credencial, tenant cruzado, produção, financeiro e regulatório elevam para CRITICAL mesmo se o nome da ação for de leitura. CRITICAL não executa sozinho. | A classe ainda não é consultada por todos os autorizadores existentes. | Quorum não está imposto no executor real. | P1 | Ligar o classificador aos gates já existentes em um bloco posterior. |
| Action receipt / flight recorder único | PARCIAL | `atlasquant_aion_action_receipt.py` referencia receipts filhos por id e fingerprint; executor/worker/developer continuam com os recibos locais | `test_atlasquant_aion_action_receipt.py` | O envelope registra escopo, revisores, blast radius, policy, guardian, evidência, aprovação e fingerprint canônico. Não é assinatura. Segredo no resultado é redigido. Mutação invalida o fingerprint. | Os executores existentes ainda não emitem este envelope. | Ligação com o receipt de execução real está NÃO VERIFICADO. | P1 | Não copiar o receipt do executor. |
| Memory quarantine | PARCIAL | `atlasquant_aion_memory_quarantine.py` na frente de `atlasquant_aion_memory_layers.py`; `cyber_immune_plan` continua sendo contenção, não admissão de memória | `test_atlasquant_aion_memory_quarantine.py` | Conteúdo novo fica QUARANTINED/REJECTED/STALE/CONFLICT/REVIEW_REQUIRED. Promoção grava na camada existente com truth UNKNOWN. Injeção relida não autoriza. Segredo redigido não é ecoado. | O gate só protege quem o chama. `atlasquant_aion_memory.py` ainda não passa por ele. | Integração com o checkpoint persistente está NÃO VERIFICADO. | P1 | Não criar um segundo arquivo de memória permanente. |
| Model registry / promotion | PARCIAL | `atlasquant_aion_model_registry.py` consome `evaluate_run` e `budget_decision`; router e laboratório continuam donos da rota e da evidência | `test_atlasquant_aion_model_registry.py` | Sem benchmark o estado fica CANDIDATE. Benchmark pior rejeita. Falha de segurança rejeita ou exige rollback. Provider indisponível cai para a rota local. Custo booleano não vira 1 USD. Texto não aprova. O módulo não chama provedor. | O registro não está ligado ao router em runtime. Aprovação aqui não ativa modelo em produção. | Seleção automática do modelo padrão no caminho real permanece NÃO VERIFICADO. | P1 | Não cadastrar chave e não chamar API paga. |
| Independência do Core | PARCIAL | allowlist em `test_atlasquant_aion_core_independence.py` e `docs/aion/AION_CORE_INDEPENDENCE_V1.md` | `test_atlasquant_aion_core_independence.py` | A allowlist pura importa sem Trader, Radar, Investimentos, Negócios, Streamlit ou requests. Memória e recovery importam com Negócios bloqueado; o normalizador de negócio só é carregado ao tocar a seção. | O inventário AST ainda registra memory → business porque a seção continua usando o módulo. Recovery e memory ainda importam `requests`. Specialist e admin continuam acoplados. | Extração total do domínio de negócio e da rede não foi feita. | P2 | Não mover specialist nesta etapa. |
| Custo desconhecido e verdade exata | PARCIAL | `cost_guard`, `budget_decision`, `truth_record`, `entitlement_effective`, `release_confidence` | testes de core, router, entitlements e release confidence | Custo inválido não vira zero. `confirmed` só é verdadeiro com bool exato. Expiry presente e inválida bloqueia. Release sem verifier não trata ref inventada como evidência. | `new_task` ainda pode clamp de custo negativo para zero antes do guard. Varredura de todo `bool()` do repositório não foi feita. | Caminho de cobrança real permanece desligado. | P1 | Não tratar diagnóstico de release como merge. |
| Representação de credencial | PARCIAL | `RuntimeConfig`, `ProviderConfig`, `AccessUser` | testes de memory, provider e access control | `repr` desses objetos mostra `[REDACTED]` e não o valor. | Outros logs que imprimem o atributo diretamente não foram varridos. | Não há rotação nem cofre operacional nesta mudança. | P1 | Não imprimir o atributo em log novo. |
| Vault | PARCIAL | `atlasquant_aion_vault.py` | `test_atlasquant_aion_vault.py` | Módulo e teste existem. Backend real, rotação e ausência de plaintext operacional NÃO VERIFICADOS nesta sessão. | Segredo em log/receipt/PR continua proibido. | Hardening de backend real fica bloqueado sem serviço externo. | P2 | Só testes offline de rejeição/redação. |
| Ruleset de `main` | AUSENTE no repositório | documentação do P0 | `gh` não altera proteção nesta sessão | O documento do P0 registra que `main` estava desprotegida na leitura anterior. | Merge pode ocorrer sem os gates. | Ação administrativa ainda necessária. | P0 | Checklist apenas. Não aplicar ruleset nesta sessão. |

## Leitura desta sessão

CONFIRMADO por arquivo ou log:

- PR #326 está em draft contra `main`.
- Head conhecido no início da continuação: `76f34e8cc333c851b909908f0be0dd5e0f49413f`.
- Quality tests desse SHA falhou em `test_quality_workflow_coverage` porque omitiu os dois testes novos. A suíte reportou 3536 testes e 1 falha.
- AION Core Security Gate e Release Readiness desse SHA terminaram SUCCESS.

NÃO VERIFICADO:

- se o próximo CI fica verde depois da correção;
- proteção efetiva da `main`;
- Dependabot gerando PRs;
- CodeQL disponível para este repositório;
- restore real, worker global, tenant persistente e qualquer API paga.

BLOCKED nesta sessão:

- merge, deploy, alteração de ruleset, gasto, segredo real, trading real e uso da PR #286 como dependência.

## Leitura do red team P1

CONFIRMADO por teste local neste branch:

- RT09: custo `"unknown"`, NaN, infinito, bool, objeto e ausência não autorizam como zero.
- RT10: repr de `RuntimeConfig`, `ProviderConfig` e `AccessUser` não mostra o segredo.
- RT11: `confirmed="false"` não produz `CONFIRMED`.
- RT17: expiry presente e inválida, inclusive timestamp sem fuso, fica `INVALID_EXPIRY`.
- RT18: dimensão sem `confirmed is True` ou sem verifier não vira evidência. Merge e deploy continuam falsos.
- RT19: importar memória e recovery com Negócios bloqueado passa. O acoplamento AST permanece.

NÃO VERIFICADO:

- CI remoto desta PR empilhada, porque a base não é `main`.
- SHA oficial de `actions/checkout`, `actions/setup-python` e `actions/upload-artifact` nesta sessão. Não foi inventado pin.
- Certificação de skill/plugin. Não há registry existente com os estados pedidos; o contrato novo fica para o próximo bloco.

RT20, PARTIAL / BLOCKED para pinagem:

- `requirements.txt` usa `>=` em streamlit, pandas, numpy, requests e pyarrow. Não houve bump cego.
- Workflows usam `actions/checkout@v7`, `actions/setup-python@v7` e `actions/upload-artifact@v7`.
- O security gate instala `pip-audit`, `bandit` e `cyclonedx-bom` sem pin.
- O SBOM CycloneDX é gerado em `/tmp/aion-sbom.cdx.json` e validado no job. Não é artefato persistido nem assinado.
- Nenhum ruleset foi alterado.
