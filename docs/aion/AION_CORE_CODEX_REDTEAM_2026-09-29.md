# AION Core — Independent Codex Red Team Audit V1

AUDIT ONLY — NO PRODUCTION FIXES

## Escopo, identidade e concorrência

Repo: aparecidomikael97-ship-it/usd-macro-pro-v4.
Branch exclusiva: codex/aion-core-redteam-audit-v1.
Issue lida: #325, incluindo o comentário de continuidade.
Foram lidos os corpos, diffs, comentários e reviews disponíveis das PRs #326/#327/#328.
Nenhuma branch Cursor foi modificada. Nenhuma produção, workflow, Checkpoint real,
regra administrativa, provider externo, banco remoto, serviço pago ou worker foi acionado.
PR #286 está fora desta missão.

| Referência | Primeiro snapshot | Revalidação durante a auditoria |
|---|---|---|
| main | 2c9dade6a87d6f618f05cbb628eb35cee2f3a8a1 | Base canônica observada |
| #326/P0 | 332554ab075279f9a90b993c7a8c8f8ca67e00e6 | Mesmo SHA |
| #327/P1 | 273e28b30617f92fa2b09edf49ccd4090f3d2de2 | 75730506c412169628a9ee1b09e693db5c382305 |
| #328/P2 | b87730811f15f09528272a9ee61d93dc64e31ffd | ddff7312b04925c8d5b909dedca35fcb12cc159d |

Base FINAL fixada da branch Codex: **ddff7312b04925c8d5b909dedca35fcb12cc159d**.
A base inicial foi efetivamente testada antes da atualização; resultados históricos
não são apresentados como defeitos ainda abertos. Não se promete acompanhar HEADs
indefinidamente: conclusões são vinculadas aos SHAs acima.

## Resultado executivo

O Core não pode receber uma certificação geral de maturidade 95+ nesta auditoria.
Há 17 achados ainda abertos: 1 CRITICAL de isolamento no contrato de revisão,
5 HIGH, 10 MEDIUM e 1 LOW. Três achados da primeira passagem foram corrigidos
pelo Cursor e revalidados independentemente.

**Limite da severidade CRITICAL:** RT04 demonstra mistura de escopo de reviews
no contrato offline, conforme a taxonomia solicitada. Não demonstra leitura
do banco de outro tenant nem execução real. O CoreStore e a memória pessoal
negaram os cruzamentos concretos testados. O adjudicador ainda não tem consumidor
de produção identificado: sua saída é eligible_for_guardian, não autorização.

Os defeitos com maior proximidade a efeitos externos são RT07/RT08:
flags textuais alcançaram requests.put/client.post INTERCEPTADOS por mocks.
Nenhuma requisição foi enviada. O alcance a um chamador externo não autenticado
não foi demonstrado; estes são defeitos reproduzidos nos contratos dos sinks.

## Execução e segurança dos experimentos

- Windows, Python 3.11 disponível; python3 local é alias do Windows Store.
- Cópia Git isolada; o diretório original da sessão não era um repositório.
- Harness: ambiente mínimo sem credenciais herdadas, HOME temporário, rede e
  subprocessos bloqueados no filho, escrita Python permitida somente no TEMP.
- Configurações/identidades são sintéticas. HTTP foi substituído por mocks.
- SQLite foi usado apenas como fixture local temporária; não se acessou banco real.
- Harness não é uma sandbox contra código nativo hostil: é defesa em profundidade
  para testes de código revisado. Testes não executaram extensões hostis.
- Nenhuma alteração de produção. Compileall gera apenas bytecode ignorado.
- Fonte AION: inventário AST de 129 módulos (116 arquivos raiz + 13 no pacote Core).
- Leitura estática não equivale a cobertura exaustiva de todos os estados possíveis.

Comandos reproduzíveis:

```text
python tools/aion_redteam_runner.py -- -m unittest -v test_atlasquant_aion_redteam_extended.py
python tools/aion_redteam_runner.py --strict-defects
python tools/aion_redteam_runner.py -- -m unittest discover
python tools/aion_redteam_runner.py --imports
python tools/aion_redteam_runner.py --independence
python tools/aion_redteam_runner.py --inventory
python -m compileall -q .
git diff --check
```

O runner chama o mesmo interpretador com -m unittest, em processo isolado.
ExpectedFailure contém assertivas do comportamento SEGURO, não assertivas
celebrando o defeito. O modo --strict-defects remove a marca expectedFailure:
os 17 testes de defeitos atuais falham explicitamente. Não são 17 controles aprovados.

### Resultados

| Execução | Resultado observado |
|---|---|
| Baseline b877308, antes dos testes novos | 3580 testes; 1 failure, 4 errors, 1 skipped |
| Adversariais em b877308 | 53 testes; 31 passaram, 22 expected failures |
| Full b877308 com testes novos | 3633; 1 failure, 4 errors, 1 skipped, 22 expected failures |
| Adversariais em ddff731 | 53; 36 passaram, 17 expected failures |
| Defeitos sem expectedFailure em ddff731 | 17 testes, 17 failures, zero errors |
| Full ddff731 | 3644 testes; 2 failures, 4 errors, 1 skipped, 17 expected failures |
| Imports limpos | 13/13 concluídos; zero threads novas, mutação de ambiente ou Streamlit carregado |
| Sem módulo Negócios | 11/13 importam; memory e recovery falham por dependência obrigatória |
| compileall / diff check | PASS |

BASELINE FAILURE / ambiente:

1. test_atlasquant_aion_convergence: subprocesso Git bloqueado pelo harness;
   checkout raso também limita testes que precisam de ancestralidade remota.
2. test_atlasquant_aion_developer_adversarial_auditor: Windows nega criação
   de symlink (WinError 1314). Não foi solicitado privilégio para contornar.
3. test_atlasquant_aion_global_worker_activation: teste escreve fixture na
   raiz da cópia; bloqueado pelo harness. Nenhum worker foi iniciado.
4. test_atlasquant_production_admin_flow: AttributeError no uso de
   session_state.get do Streamlit instalado.
5. test_scanner_freshness_v1074: falha na fronteira exata de 60 minutos na primeira
   baseline; não reapareceu na execução seguinte e reapareceu na execução final.
   Possível dependência de relógio,
   não classificada aqui como regressão introduzida pelo audit.

FAILURE INTRODUCED BY AUDIT TEST:
test_quality_workflow_coverage acusa o novo arquivo raiz ausente da lista explícita
do workflow. É uma falha real de registro do teste de auditoria, não de produção.
O workflow não foi editado, conforme proibição expressa. Esta PR é Draft e não
alega suíte integral verde. Decidir o registro no CI junto da integração futura.

CI remoto consultado: #326 tem cinco checks SUCCESS no SHA auditado; #327/#328
iniciais não tinham checks. Os workflows de quality/security disparam para PR
com base main, não garantem validação automática das branches empilhadas.
Relatos de suíte verde nos corpos das PRs não substituem os resultados acima.

## Matriz de achados

Convenções: todos os testes abaixo estão em test_atlasquant_aion_redteam_extended.py,
exceto RT19/RT20. Conflito com Cursor significa sobreposição temática/arquivo
para uma futura correção; **a auditoria não altera esses arquivos**.
Privilegiado descreve a decisão afetada, não uma exploração remota comprovada.

### RT01 — Retry consumido volta a incrementar (histórico resolvido)
- Severidade: HIGH; status: REPRODUZIDO em b877308, corrigido em ddff731.
- Arquivo/função: atlasquant_aion_durable_tasks.py, update_step/retry_step.
- Cenário/entrada: FAILED → k1 → RUNNING → FAILED → k1; também normalize,
  JSON round-trip e pause/resume. k2 intencional era recusada.
- Atual: no-op para k1, k2 incrementa uma vez, histórico preservado.
- Seguro esperado/impacto: não repetir tentativa consumida; risco de double
  scheduling local, sem prova de efeito externo duplo.
- Teste: três test_RT01_* em ResolvedByCursor; todos PASS no novo SHA.
- Correção mínima: já feita pelo Cursor; manter regressões, limite e migração.
- Prioridade histórica P0; privilegiado: estado de tarefa; conflito: SIM (#328).

### RT02 — Capability/permission adulterada e resselada (resolvido)
- Severidade: HIGH; status: REPRODUZIDO inicialmente, corrigido em 7573050/ddff731.
- Arquivo/função: atlasquant_aion_critical_review.py, validate_agent_message.
- Entrada: contexto READ, mensagem reescrita para DEPLOY/WRITE, SHA-256 recalculado.
- Antes INFORMATION_ONLY; agora BLOCK. Seguro: revalidar permissões no receptor.
- Impacto anterior: fronteira de plano aceitava capacidades fora do contexto;
  não concedia execução. Fingerprint não é autenticação.
- Teste: test_RT02_resealed_capability_permission_escalation_blocked, PASS.
- Correção mínima: já feita; preservar testes. P0 histórico; privilegiado:
  contrato de autorização futura; conflito: SIM (#327).

### RT03 — Mesmo agente preenche Prime, Shadow e Sentinel
- Severidade: HIGH; status: REPRODUZIDO; prioridade P0.
- Arquivo/função: atlasquant_aion_critical_review.py, adjudicate_critical_task.
- Cenário/entrada: trusted_assignments associa os três papéis a one-agent,
  três vereditos AGREE, referências existentes no registry sintético.
- Resultado atual: ACCEPT_PLAN. Seguro esperado: BLOCK por independência inválida.
- Impacto: quórum aparente sem revisão independente; exige configuração de
  assignments inadequada, não é roubo de identidade autenticada.
- Teste: test_RT03_same_agent_cannot_fill_three_roles, EXPECTED FAIL.
- Correção mínima: unicidade dos principals revisores, vínculo a tarefa/escopo
  e política explícita de independência. Privilegiado: gate de plano.
- Conflito com Cursor: SIM (#327).

### RT04 — Reviews de outro tenant/workspace aceitos
- Severidade: CRITICAL (isolamento contratual); status: REPRODUZIDO; P0.
- Arquivo/função: atlasquant_aion_critical_review.py, adjudicate_critical_task.
- Entrada: reviews identificados como tenant-b/trader-b usados em adjudicação
  tenant-a/admin-a, com nomes de agentes que coincidem com assignments.
- Resultado: ACCEPT_PLAN; escopo da saída é o argumento A, campos B dos reviews
  são ignorados. Verificadores dos refs A não autenticam os reviews B.
- Seguro esperado: rejeitar escopo divergente/ausente e reviews sem binding
  verificável à tarefa, plano, agente, tenant e workspace.
- Impacto: mistura de decisões entre escopos no contrato; NÃO foi demonstrado
  vazamento de armazenamento, nem executor consumindo esse plano.
- Teste: test_RT04_foreign_review_scope_cannot_be_relabelled, EXPECTED FAIL.
- Correção mínima: ingress confiável de reviews, closed schema e revalidação
  de escopo/identidade/versão. Privilegiado: revisão de plano crítico.
- Conflito com Cursor: SIM (#327).

### RT05 — Referência inventada bastava (histórico resolvido)
- Severidade: HIGH; status: REPRODUZIDO inicialmente, corrigido no novo SHA.
- Arquivo/função: critical_review, adjudicate_critical_task/validate_agent_message.
- Entrada: approval_refs/evidence_refs com strings inventadas.
- Atual: ausência de verifier ou referência não vinculada bloqueia.
- Seguro/impacto: presença não é validade; não aceitar confirmação autodeclarada.
- Teste: test_RT05_invented_sensitive_approval_evidence_not_accepted, PASS.
- Correção mínima: preservar binding por caller confiável; implementação real
  deve capturar escopo/subject/ação/TTL no verifier, pois a API recebe apenas refs.
- P0 histórico; privilegiado: aprovação/evidência; conflito: SIM (#327).

### RT06 — sensitive textual remove exigência de aprovação
- Severidade MEDIUM; status REPRODUZIDO; P0.
- Arquivo/função: critical_review, adjudicate_critical_task.
- Entrada: sensitive="true", approval_refs=[], evidência válida.
- Atual ACCEPT_PLAN; seguro BLOCK/invalid type. Impacto: plano sensível
  processado como não sensível; não executa ação.
- Teste test_RT06_sensitive_string_is_not_safe_false, EXPECTED FAIL.
- Correção mínima: tipo bool exato; valores ambíguos devem restringir/rejeitar,
  não equivaler a False. Privilegiado: exigência de aprovação.
- Conflito com Cursor: SIM (#327).

### RT07 — Aprovação textual chega ao writer de Checkpoint
- Severidade HIGH; status REPRODUZIDO; P0.
- Arquivo/função: atlasquant_aion_memory.py:1470, save_runtime_checkpoint.
- Entrada: approved="false", configuração sintética válida e checkpoint default.
- Atual: requests.put é chamado uma vez no mock. Seguro: BLOCK antes do transporte.
- Impacto: sink de persistência aceita falsidade textual como aprovação, mesmo
  com Guardian endurecido em outro módulo. Não houve escrita real.
- Teste test_RT07_checkpoint_string_approval_cannot_attempt_put, EXPECTED FAIL.
- Correção mínima: approved is True no sink; testar False/strings/números e
  revalidar demais gates no limite de escrita. Privilegiado: SIM, persistência.
- Conflito com Cursor: SIM (hardening Core/memory).

### RT08 — Strings false liberam rota e transporte de provider
- Severidade HIGH; status REPRODUZIDO; P0.
- Arquivos/funções: atlasquant_aion_model_router.py normalize_budget,
  budget_decision, route_intelligence; atlasquant_aion_provider.py:351 execute_openai_answer.
- Entrada: external_feature_enabled/request_approved/allow_paid="false",
  orçamento 10, preço/modelos/credencial estritamente sintéticos.
- Atual EXTERNAL_FAST e client.post do mock alcançado. Seguro: rota local e
  transporte nunca chamado. Impacto potencial de custo/saída de dados se um caller
  repassar tipos incorretos; exploit por usuário remoto não foi demonstrado.
- Testes: dois test_RT08_*, EXPECTED FAIL.
- Correção mínima: tipos exatos em router E sink; estado normalizado não deve
  tornar autorização inválida válida. Privilegiado: SIM, chamada externa/paga.
- Conflito com Cursor: SIM (hardening de autorização).

### RT09 — Custo inválido vira custo zero
- Severidade MEDIUM; status REPRODUZIDO; P1.
- Arquivos/funções: atlasquant_aion_core.py cost_guard;
  atlasquant_aion_model_router.py budget_decision.
- Entrada: custo "unknown", sem aprovação. Atual allowed=True/custo 0.
- Seguro: UNKNOWN/BLOCKED. Impacto: avaliação orçamentária falsamente gratuita.
  Provider tem seu próprio estimador: esta falha isolada não prova cobrança.
- Testes: dois test_RT09_*, EXPECTED FAIL.
- Correção mínima: rejeitar falha de parsing, negativos, bool e não finitos
  uniformemente; separar ausência de preço de zero verificado.
- Privilegiado: orçamento; conflito com Cursor: SIM.

### RT10 — RuntimeConfig repr inclui credencial
- Severidade MEDIUM; status REPRODUZIDO; P1.
- Arquivo/função: atlasquant_aion_memory.py:260, RuntimeConfig/__repr__ gerado.
- Entrada: token sintético. Atual repr contém valor integral.
- Seguro: repr=False/redação do campo. Impacto: logging/debug de configuração
  pode divulgar segredo; nenhum vazamento real foi observado.
- Teste test_RT10_runtime_config_repr_redacts_token, EXPECTED FAIL.
- Correção mínima: esconder segredo em representações; revisar ProviderConfig,
  que também declara api_key em dataclass. Não mudar chave real.
- Privilegiado: confidencialidade; conflito com Cursor: SIM.

### RT11 — truth_record confirma com string false
- Severidade MEDIUM; status REPRODUZIDO; P1.
- Arquivo/função: atlasquant_aion_core.py:140, truth_record.
- Entrada: confirmed="false". Atual kind=CONFIRMED; seguro UNKNOWN/rejeição.
- Impacto: helper de verdade promove tipo inválido; não prova que texto externo
  controle esse parâmetro nos callers atuais do onboarding.
- Teste test_RT11_truth_confirmation_string_is_not_true, EXPECTED FAIL.
- Correção mínima: classificação tipada/exata e evidência requerida no ingress.
- Privilegiado: estado de verdade, não execução; conflito com Cursor: SIM.

### RT12 — Nível de desenvolvedor aceita human_approved textual
- Severidade MEDIUM; status REPRODUZIDO; P0 antes de executor.
- Arquivo/função: atlasquant_aion_workspaces.py:216, developer_step_allowed.
- Entrada: level=2, human_approved="false". Atual True; seguro False.
- Impacto: helper utilizado em developer_implementation autoriza nível acima
  do autônomo por truthiness. Demais boundaries não foram substituídas nem
  se provou execução física através delas.
- Teste test_RT12_developer_level_requires_exact_human_approval, EXPECTED FAIL.
- Correção mínima: aprovação booleana exata e nível inteiro exato.
- Privilegiado: escopo Developer; conflito com Cursor: SIM, coordenar outra frente.

### RT13 — Versão desconhecida e nonce vazio passam revalidação
- Severidade LOW; status REPRODUZIDO; P1.
- Arquivo/função: critical_review, validate_agent_message.
- Entrada: version=999/nonce vazio, fingerprint recalculado e refs legítimos.
- Atual INFORMATION_ONLY; seguro BLOCK por schema/nonce.
- Impacto: receptor aceita objeto que seu sealer não deveria produzir;
  não vira autorização. Campos extras também não formam schema fechado.
- Teste test_RT13_unknown_version_empty_nonce_must_block, EXPECTED FAIL.
- Correção mínima: closed schema, versão exata, tipos e limites no receptor.
- Privilegiado: integridade documental; conflito com Cursor: SIM (#327).

### RT14 — Recovery confia no rótulo de integridade apresentado
- Severidade HIGH; status REPRODUZIDO; P0.
- Arquivo/função: atlasquant_aion_recovery.py:186, recovery_preflight.
- Entrada: checkpoint={}, integrity.state=CONFIRMED, revision hexadecimal,
  runtime atual rotulado CONFIRMED com SHA.
- Atual allowed=True apesar de checkpoint_integrity_report({}) não confirmar.
- Seguro: recomputar integridade dos bytes/campos e comparar binding de revisão.
- Impacto: candidato fabricado pode ser apresentado como elegível para restore;
  aprovação humana e writer ainda existem. Não houve restore real.
- Teste test_RT14_recovery_must_recompute_candidate_integrity, EXPECTED FAIL.
- Correção mínima: ignorar rótulo fornecido como autoridade; recomputar e rejeitar
  incoerência, incluindo digest/escopo/revisão. Privilegiado: recovery.
- Conflito com Cursor: SIM.

### RT15 — Mensagem serializável preserva segredo textual
- Severidade MEDIUM; status REPRODUZIDO; P1.
- Arquivo/função: critical_review, seal_agent_message/_clean.
- Entrada: content com token sintético em formato token=valor.
- Atual valor preservado no envelope; seguro rejeitar/redigir antes de persistência.
- Impacto: envelope pode carregar credencial para logs/memória; não se comprovou
  consumidor persistindo essa mensagem em produção.
- Teste test_RT15_message_content_does_not_keep_credentials, EXPECTED FAIL.
- Correção mínima: reutilizar redação antes do fingerprint; proteger também refs.
- Privilegiado: confidencialidade; conflito com Cursor: SIM (#327).

### RT16 — Entitlement falso textual torna usuário elegível
- Severidade HIGH; status REPRODUZIDO; P0.
- Arquivos/funções: atlasquant_aion_entitlements.py normalize_entitlement;
  atlasquant_aion_tenant.py personal_aion_eligibility.
- Entrada: status ACTIVE_CONFIRMED, approval.approved="false",
  provider_evidence.confirmed="false", provider/external_id inventados.
- Atual eligible=True para o sujeito correspondente; seguro negar.
- Impacto: elegibilidade comercial declarada sem aprovação/evidência válidas;
  fixture não altera conta, cobra ou permite ler outro tenant.
- Teste test_RT16_string_entitlement_approval_cannot_grant_eligibility, EXPECTED FAIL.
- Correção mínima: tipos estritos e binding a evidência de provider confiável,
  não só strings presentes. Privilegiado: entitlement.
- Conflito com Cursor: SIM (auth/entitlements).

### RT17 — Expiração inválida vira entitlement sem prazo
- Severidade MEDIUM; status REPRODUZIDO; P1.
- Arquivo/função: entitlements, _parse_iso/entitlement_effective.
- Entrada: entitlement ativo sintético, expires_at="invalid-expiry".
- Atual effective=True; parse inválido equivale a data ausente.
- Seguro: expiração malformada bloqueia; ausência intencional é outro estado.
- Impacto: prolongamento indevido de elegibilidade em estado corrompido.
- Teste test_RT17_invalid_expiry_is_not_unlimited_entitlement, EXPECTED FAIL.
- Correção mínima: diferenciar missing/invalid, exigir timezone explícito e
  validar janela; manter bloqueio na igualdade de expiry.
- Privilegiado: entitlement temporal; conflito com Cursor: SIM.

### RT18 — Release coverage confirma strings false
- Severidade MEDIUM; status REPRODUZIDO; P1.
- Arquivo/função: atlasquant_aion_release_confidence.py, evidence_dimension/release_confidence.
- Entrada: seis dimensões confirmed="false", refs inventados.
- Atual HUMAN_REVIEW_READY; seguro NEEDS_EVIDENCE.
- Impacto: cobertura de evidências falsa para revisão humana; merge_allowed e
  deploy_allowed continuam False. Não chamar isso de deploy autorizado.
- Teste test_RT18_release_string_confirmation_is_not_evidence, EXPECTED FAIL.
- Correção mínima: bool exato e binding ao candidato/fonte/resultado observado.
- Privilegiado: diagnóstico de release; conflito com Cursor: SIM.

### RT19 — Memory/recovery não independem de Negócios
- Severidade MEDIUM; status REPRODUZIDO; P2.
- Arquivos/funções: atlasquant_aion_memory.py:31 import de business;
  atlasquant_aion_recovery.py:19 import de memory.
- Entrada: finder de teste torna somente módulos opcionais indisponíveis.
- Atual ambos falham com ImportError; 11 outros imports continuam funcionando.
- Seguro esperado: Core básico independente de produtos, adapters opcionais.
- Impacto: portabilidade/manutenção e indisponibilidade propagada, sem escalada.
- Teste: runner --independence, duas falhas esperadas explicitamente reportadas.
- Correção mínima sugerida: separar registro/normalização opcionais por adapter;
  não refatorado nesta PR. Privilegiado: NÃO; conflito com Cursor: SIM, bloco arquitetural.

### RT20 — Cadeia de build ainda não é reproduzível/pinada
- Severidade MEDIUM; status CONFIRMADO por código; P2.
- Arquivos: requirements.txt; .github/workflows/aion-core-security-gate.yml;
  quality-tests.yml e demais workflows lidos. Função: instalação/checagem CI.
- Entrada/cenário: nova resolução de dependências e tags major de Actions.
- Atual: requirements com >=; actions/checkout e setup-python @v7, tooling
  pip-audit/bandit/cyclonedx-bom sem versão fixa; quality instala pacotes soltos.
  SBOM é gerado em /tmp e seu digest é impresso, sem upload desse SBOM no gate.
- Seguro: lock/hash/proveniência revisados, Actions por SHA, artefato do SBOM
  preservado e validação também na stack. Não há compromisso de pacote demonstrado.
- Impacto: builds diferentes e superfície de supply chain; versões variáveis
  também dificultam comparar nossa baseline Windows com CI Linux.
- Teste/evidência: inspeção literal dos workflows e requisitos; CI #326 verde.
- Correção mínima: pinagem e retenção por PR própria do implementador;
  required checks/ruleset dependem do administrador.
- Privilegiado: pipeline; conflito com Cursor: SIM, workflows não editados.

## Cobertura dos 20 blocos pedidos

| Bloco | Evidência / conclusão / limite |
|---|---|
| 1 Boolean/type | Varredura e testes de Guardian/Fortress, custos, provider, memória, review, entitlement, release e Developer. RT06–18. Bool de flag restritiva foi separado de bool que concede privilégio. |
| 2 Autoridade/injection | 10 fontes x 11 textos adversariais mantêm content_may_control_tools=False. Texto não virou ADMIN nesses contratos; não é teste contra LLM remoto. |
| 3 Prime/Shadow/Sentinel | Spoof de role/id e duplicate role bloqueiam; RT03/04/06/13/15 persistem. SHA-256 documentado corretamente como fingerprint após update. |
| 4 Durable/idempotência | Ciclos k1/k2, JSON/restart de estado, normalize, pause/resume, terminal, limite, empty/None/huge key e external-side-effect. RT01 resolvido; nenhum efeito externo duplo demonstrado. |
| 5 Tenant | A→B negado em memória pessoal e CoreStore/read/approval; reviews cruzados RT04. Não certifica todos os caches/serviços implantados. |
| 6 Workspace | Chaves por persona distintas; ações proibidas negadas; CoreStore isola workspace/domain/actor. Não se afirma isolamento de toda UI Streamlit persistida. |
| 7 Secrets | Redação de campos/metadata passa; repr e envelope falham RT10/15. 646 arquivos Python/docs AION escaneados por padrões de tokens; quatro candidatos são fixtures de testes/auditores. Nenhuma credencial real utilizada/publicada. |
| 8 Imports | 13 processos limpos: sem rede, escrita, thread nova, alteração de env ou Streamlit. Não é prova sobre todos os 129 módulos, em especial UI/CLI. |
| 9 Dependências | Inventário AST + teste de ausência de opcionais. RT19; matriz abaixo. |
| 10 Supply chain | RT20. Security gate tem contents:read; não encontrado pull_request_target nem curl pipe bash nos workflows examinados. Writes de bootstrap são funções explícitas de manutenção, não import side effects. Ruleset operacional NÃO VERIFICADO. |
| 11 Paths | Identificadores Core rejeitam traversal; tenant path é hash fixo. Scripts bootstrap/migrate aceitam path do operador e CoreStore path do host; nenhum fluxo de intenção não confiável até esses paths foi provado. Symlink adversarial amplo BLOCKED pelo Windows. |
| 12 Commands | Inventário AST dos módulos AION não encontrou chamada de eval/exec/pickle/subprocess com entrada não confiável. json.loads não foi tratado como pickle. Escritas em bootstrap/migrate e fixtures de auditor não são execução arbitrária por import. Sem RCE demonstrada. |
| 13 Resources | Limites: 300 tasks, 80 steps, retry history 32, key 128 no novo SHA, 200 Evidence no Core, metadata profundidade 12. list(values) antes de slice em helpers pode materializar entradas grandes: PARCIAL, não houve teste de exaustão do host. Fanout/delegação recursiva total NÃO VERIFICADO. |
| 14 Recovery | Missing/unavailable/corrupt encoding e aprovação string bloqueiam nos testes; RT14 aceita rótulo de integridade forjado. Partial/duplicated records em toda migração não foram exauridos. |
| 15 Tempo | Mensagem naive/future/ancient bloqueia; max_age=900 é inclusivo, 901 bloqueia. ApprovalGate expira na igualdade. Expiry inválida de entitlement RT17. Clock skew distribuído NÃO VERIFICADO. |
| 16 Approval/evidence | RT05 corrigido com verifiers; Core ApprovalGate exige adapter humano e subject binding. Restam entitlement/release e binding dos reviews. Presença não foi confundida com validade no relatório. |
| 17 Testes | ExpectedPass, ResolvedByCursor, ExpectedFailure, BoundaryObservations e modo strict; sem modificar testes existentes. |
| 18 Achados | Matriz RT01–20 com entradas, resultados, funções, evidências, limites e remediações mínimas. |
| 19 Prioridade | P0/P1/P2 abaixo, sem implementação. |
| 20 Produção | Zero arquivos existentes alterados; somente novos testes, harness e relatório. |

## Grafo/matriz de dependências reais

| Categoria | Exemplos / dependências observadas |
|---|---|
| CORE | core, critical_review, durable_tasks, fortress; stdlib + observability/core. Importam sem módulos de produto bloqueados. |
| CORE application | core_intelligence.service → context/store/approval/evidence/router; sem Trader/Negócios carregados no teste. |
| SHARED | observability, truth, access_control, clock; usados por vários contratos. |
| OPTIONAL | business, studio, promotions, entitlements. Memory importa normalizadores diretamente; OPTIONAL tornou-se obrigatório para esse agregado. |
| INFRA | memory → requests/runtime_store; recovery → memory; CoreStore → sqlite3 e caminho confiável do host. |
| UI | aion_admin → Streamlit e dezenas de componentes; não é Core puro e não integra o teste de import puro. |

Fluxo invertido reproduzido: recovery → memory → business.
O núcleo de contratos pode funcionar sem produtos; o agregado completo de
memória/recovery atual não. Não afirmar que todos os módulos AtlasQuant foram
removidos: os shared helpers continuam sendo dependências reais.

## Hipóteses, limites e falsos positivos descartados

- SHA recalculável não é, por si só, uma falha criptográfica: não existe segredo
  nem assinatura nesse contrato. Defeito só foi contado quando validação esperada
  foi contornada; RT02 já corrigido.
- Novo nonce muda digest e passa como nova mensagem informativa. Sem executor,
  isso não demonstra double execution. É preciso identidade de operação e
  idempotência no consumidor antes de autonomia.
- ACCESS/Context/trusted_assignments são argumentos do host confiável. Passar
  role ADMIN arbitrariamente numa chamada direta não prova bypass de login.
- Same-agent quorum RT03 exige assignments inválidos; não se provou que um
  usuário comum consegue editar os assignments reais.
- CoreStore usa escopo completo e parâmetros SQL; nenhuma injeção SQL demonstrada.
- Sanitização de portable connectors reconstrói flags desativadas; truthiness
  posterior em tool_hub não foi suficiente para reproduzir ativação.
- Scripts locais que escrevem path escolhido pelo operador não foram rotulados
  traversal explorável sem origem de input não confiável.
- Não se invocou banco remoto, API paga, provider real, worker ou deploy.
- Metadados dinâmicos/integridade de arquivos de plugins, concorrência real
  entre workers, cache multitenant implantado e RPO/RTO operacional:
  NÃO VERIFICADO; exigem outro ambiente/escopo.
- Payloads enormes/aninhados e iteradores ilimitados: HIPÓTESE de DoS em helpers
  com materialização anterior ao corte; testes destrutivos não executados.
- Quatro candidatos de token no scan de fonte pertencem a cenários artificiais
  de auditoria/teste; não demonstram comprometimento de credenciais.

## Priorização e responsabilidade

P0 — antes de integrar executor:
RT03, RT04, RT06, RT07, RT08, RT12, RT14, RT16.
RT01/RT02/RT05 saem da lista pendente no SHA final; manter suas regressões.

P1 — antes de autonomia relevante:
RT09, RT10, RT11, RT13, RT15, RT17, RT18; implementar verifier de referência
realmente vinculado ao escopo/subject/ação/TTL e política de replay de operação.

P2 — antes de comercialização/escala:
RT19, RT20; ampliar quotas, cobertura de caches/tenant e ensaios de recovery.

P3:
Consolidar os testes independentes no CI sem transformar expected failures em
aprovação automática de release; manter contagem explícita de defeitos conhecidos.

Precisam do Cursor: correções de produção/contratos; não copiar o relatório como
prova de segurança e não duplicar motores existentes. RT12 exige coordenação com
a frente Developer/Security.

Precisam de decisão humana: fronteira autenticada dos verifiers/reviewers,
política de evidência para entitlement, required checks/ruleset, ambiente para
testes de concorrência/restore e autorização explícita de eventual integração.
Nenhuma dessas decisões foi tomada ou aplicada pela auditoria.

## Conclusão de validação

Base final ddff731: 53 testes independentes, 36 PASS e 17 EXPECTED FAIL.
Modo strict: 17 FAIL, sem erros de fixture. Suíte total: 3644 testes,
2 FAIL (coverage do arquivo novo e fronteira de freshness já observada),
4 ERROR previamente presentes no ambiente isolado, 1 SKIP, 17 EXPECTED FAIL.
compileall e git diff --check passaram.

As duas falhas e quatro erros da suíte não foram escondidos por skips novos,
patches de produção ou relaxamento do harness. Nenhum workflow foi alterado.
O commit e a Draft PR publicam apenas os três arquivos novos listados abaixo:

- test_atlasquant_aion_redteam_extended.py
- tools/aion_redteam_runner.py
- docs/aion/AION_CORE_CODEX_REDTEAM_2026-09-29.md

Não integrar executor nem declarar maturidade 95+ até fechar os P0 e obter
validação independente no ambiente de CI suportado. Esta auditoria não autoriza
merge, deploy, pagamento, publicação ou execução real.
