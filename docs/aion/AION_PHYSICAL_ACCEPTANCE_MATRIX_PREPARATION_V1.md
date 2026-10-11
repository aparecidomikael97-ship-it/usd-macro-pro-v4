# Matriz de aceite — futura validação física, não executada

Todas as linhas continuam **BLOCKED**. O manifesto original não foi editado. `plan.collection_layers` é plano de coleta; não autoriza provisão. Qualquer recurso externo com custo deve aguardar decisão financeira explícita, mesmo que um teste simulado ou uma camada de coleta esteja completo.

| Gate | Evidência externa/física que falta | Reutilização offline |
|---|---|---|
| SOURCE_ROOT_ENROLLMENT | Matrícula fora de banda, chave e pin protegidos, verificador independente | Source gate real sempre BLOCKED; trust registry não prova custódia |
| OWNER_IDENTITY_CEREMONY | Identidade real, presença e decisão do proprietário no dispositivo | `ceremony.review_ceremony`, assinatura/challenge de fixture |
| TENANT_RESOURCE_REGISTRY | Registro revogável de proprietário/tenant/workspace/repo/branch/path | `contracts.binding`, negativos A→B e mudança de recurso |
| INDEPENDENT_KEY_CUSTODY | Custódia/rotação/revogação comprovadas separadamente | Testes negativos de pins, credenciais e revogação |
| ADMIN_FAILURE_DOMAIN_SEPARATION | Domínios administrativos/restauração distintos comprovados | Mesmo domínio/credencial rejeitado; strings diferentes não provam independência |
| COORDINATOR_ATOMIC_CAS | CAS monotônico no provider real, concorrência entre máquinas | CAS SQLite existente; quatro processos locais, sem rede |
| COORDINATOR_ROLLBACK_TEST | Ensaio PITR com anchor protegido fora do alcance do operador | Restore/rollback de fixture e floor simulado |
| SECOND_DOMAIN_IMMUTABLE_HISTORY | Retenção imutável efetivamente configurada e verificada | Spec de witness, sem matrícula real |
| SECOND_DOMAIN_CURRENT_HEAD | Leitura autenticada do head atual, versões/paginação/delete markers | Dual-head/challenge, somente matemática e contratos |
| FRESH_NONCE_CHALLENGE | Fonte CSPRNG, replay/retomada sob estado durável confiável | Registry existente, rejeição de nonce usado/estado ausente |
| CROSS_DOMAIN_PARTIAL_COMMIT | Crash entre providers com readback causal independente | UNKNOWN, commit/erro/crash real local; sem repetição automática |
| B2B_CROSS_TENANT_NEGATIVE_TESTS | Isolamento no host/serviço/caches reais entre empresas | Contratos A/B, browser binding e witness tenant negatives |
| OWNER_WINDOWS_PHYSICAL_VALIDATION | Host autorizado, OS/arquitetura, assinatura, ACL, sandbox, storage seguro | `windows.review_windows_checks`; 11 controles, nenhuma coleta |
| RECOVERY_REVOCATION_BREAK_GLASS | Recuperação autorizada por partes independentes, continuidade de epoch | Floor/epoch/fork/revogação e cenário descartável |
| LGPD_RESIDENCY_AND_OPERATORS | Revisão de finalidade, região, operadores e contratos reais | 7 critérios de privacidade; `UNKNOWN` nunca vira aprovação jurídica |
| FULL_BRL_BUDGET_QUOTE | Cotação vigente completa em BRL com storage, rede, APIs, impostos e recuperação | 11 categorias, inteiro em centavos, cap provisório 20.000; não há cotação real |
| CLOUDFLARE_SECURITY_ROUTE_NO_BYPASS | Ensaio real de quota/rota de segurança sem bypass | Dependência externa preservada; nenhuma flag autodeclarada é aceita |
| CLOUDFLARE_DO_SINGLE_OBJECT_STORAGE_HEADROOM | Medição por objeto, margem e SQL_FULL em provider aprovado | Spec existente não substitui medição |
| FINANCIAL_SPEND_APPROVAL | Aprovação específica de fornecedor, escopo e limite antes de qualquer gasto | `spending_approved=false` em todas as saídas |
| RELEASE_MERGE_DEPLOY_APPROVAL | Decisões separadas para merge, deploy, instalação e ativação | Todos os campos de autoridade falsos; Draft não autoriza liberação |

## Plano físico futuro — somente depois de autorização específica

1. Proprietário identifica host e operador, janela e escopo de coleta somente leitura. Definir local privado autorizado dos resultados. Inventário não autoriza instalação, rede, biometria ou criação de chaves.
2. Apresentar comandos exatos para revisão posterior, antes de coletar. Não há coletor nem comando executável de TPM/Hello/FIDO2 nesta entrega. Confirmar o que o equipamento suporta, mantendo UNKNOWN quando não houver evidência.
3. Verificar OS/arquitetura/pré-requisitos, artefato/assinatura/publisher e integridade, identidade do arquivo/volume, ACL e reparse points, conta de serviço de menor privilégio, armazenamento seguro, processos/rede, isolamento de sessões/tenants e logs sem segredos. Conferir restart/recovery com material descartável em ambiente aprovado.
4. Autorizar, separadamente, a cerimônia de identidade/matrícula se o proprietário decidir fazê-la. Não enviar documento pessoal, biometria, PIN, tokens ou chave privada ao GitHub. A verificação deve registrar origem, vínculo, timestamp/validade, teste negativo e verificador independente.
5. Provas de provider/witness exigem escopo e aprovação externos próprios, além de aprovação financeira quando houver custo. Não configurar serviços ou substituir a custódia por uma assinatura criada pelo projeto.
6. Rever as 20 evidências e riscos residuais. Só uma avaliação independente posterior pode recomendar GO; nenhuma função desta preparação retorna instalação autorizada. Worker, produção e operações sensíveis continuam fora deste procedimento.

## Riscos residuais e limites

HIGH: identidade, dispositivo e trust root reais ausentes; HIGH: antirollback/custódia externos ausentes; HIGH: isolamento físico entre empresas e recuperação externa não demonstrados. Todos são dependências bloqueadas, não uma descoberta de bypass atualmente habilitado. MEDIUM corrigido: classificação falsa de rollback após commit na referência SQLite. MEDIUM mitigado na nova entrada: manifesto/coleções não limitados no planejador antigo. Não foram encontrados resultados físicos a promover.

Não existe confirmação de preço ou consumo atual. Opção local facilita CI e estudo, mas SQLite no mesmo domínio administrativo não substitui witness independente. O teto R$200/mês é referência de planejamento, não autorização de gasto nem promessa de que um fornecedor cabe no limite.
