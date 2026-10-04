# AION V2.6 — Canonical Health Evidence Adapter

Base obrigatória: `31bd32565c52fb0806a2eae2854fad80f6b08359`, PR #566,
`integration/aion-core-v23-v25-reconciliation-20261004`.

## Gap comprovado e fluxo READ ONLY

A varredura da Fase 1 analisou 774 arquivos Python versionados, sem erros de AST.
A chave `aion_core_health` era lida pelo status board e fornecida por fixtures;
o builder real do Admin não produzia esse contexto. Não havia produtor canônico.
O snapshot e o Master Status Board existentes são preservados.

```
evidência canônica já residente, com procedência fornecida pelo código confiável
 -> LoadedEvidence + build_core_health_evidence (validação pura, bounded)
 -> system_context.aion_core_health
 -> core_health_snapshot (classificador existente, fail-closed)
 -> Master Status Board (integridade + bloqueios operacionais)
```

`render_aion_admin_console` usa `build_loaded_runtime_health_evidence` imediatamente
antes do board. Usa somente o resultado bruto da chamada de checkpoint já existente;
não usa seed estático, checkpoint normalizado ou working copy como prova.
Substitui alegações de saúde vindas do contexto do cliente. Não adiciona loader.
O contexto original do chamador e as evidências não são modificados.

## Fontes e limites de confiança

| Domínio | Evidência residente | Validação pura | Integração atual no Admin |
|---|---|---|---|
| journal | journal completo por request/escopo | verify_request_journal | UNKNOWN: não carregado |
| checkpoint | master V2.3 ou checkpoint legado bruto | reconstruct_checkpoint / checkpoint_integrity_report | bruto já carregado; validação antes de VERIFIED |
| recovery | relatório canônico já produzido, com flags estritas e fingerprint | receipt explícito + vocabulário negativo existente | UNKNOWN: relatório não carregado |
| memory | MemoryContractRecord, vista completa explicitamente declarada | create_memory_record + operational_decision | UNKNOWN: vista não carregada |
| audit_chain | journal da cadeia já residente | verify_request_journal + comparação de head/revision | UNKNOWN: não carregado |
| contadores | lista completa de taskgraphs V2.4 selados | validate_taskgraph | não comprovados |

`LoadedEvidence` é um contrato de procedência do código da aplicação, não uma
assinatura criptográfica ou envelope JSON aceito do cliente. Um chamador confiável
é responsável por declarar a origem e a completude da vista. Dicts arbitrários com
status OK/VERIFIED não são evidência. Não há descoberta de arquivos, persistência,
store aberto, scan ou validação remota. Futuros builders devem fornecer objetos
residentes somente depois da autenticação/escopo já existentes.

Journal, checkpoint, memory e taskgraph podem ter sido persistidos pelos respectivos
componentes; o adapter recebe apenas seus valores carregados e deriva uma nova
projeção. Essa projeção não é persistida. Os wrappers congelados não tornam os valores
aninhados imutáveis; o adapter copia estruturas simples e não altera entradas.
Scope owner/tenant/workspace/ecosystem/sector/project/request conflitante rejeita a
composição. Aliases conflitantes também são rejeitados. Journal exige identidade
owner/tenant/workspace/request; relatório recovery exige fingerprint compatível.
Scopes ausentes não são inventados. O builder Admin não infere tenant do usuário.

## Semântica fail-closed

Só validação positiva explícita de uma vista completa permite status bom. Ausência,
procedência ausente, estrutura ambígua ou freshness não comprovada permanecem UNKNOWN.
Falhas de integridade preservam status negativo e dominam UNKNOWN/incompletude.
CONFLICTING e REJECTED são projetados em MISMATCH/INVALID; QUARANTINED permanece ruim;
OUTDATED/STALE/UNVERIFIED/UNKNOWN nunca tornam memory saudável. A classificação final
continua exclusivamente em core_health_snapshot. Erros e mismatch explícitos do loader
já residente são preservados como checkpoint negativo; indisponibilidade é UNKNOWN.

Freshness usa a semântica temporal existente e `now` aware explícito. Não há TTL novo
nem relógio implícito. Registros de memória sem created_at não são recriados: o construtor canônico
poderia acionar seu relógio implícito. Permanecem UNKNOWN. Eventos sem created_at são omitidos para evitar timestamp
inventado pelo normalizador. Sem indicação temporal, registra NOT_EVALUATED;
isso não declara freshness de um componente que não forneceu esse contrato.

Os contadores são derivados de taskgraphs V2.4 validados; mission_state V2.2 não está
vinculado ao digest e portanto não certifica contadores. A lista vazia só prova zero
quando o chamador confiável declara vista completa. pending_missions conta os planos
pendentes; ready_handoffs conta missões READY_FOR_GUARDED_HANDOFF, não autorizações de
execução. Qualquer blocked_missions ou waiting_approval positivo mantém BLOCKED.
Contadores não comprovados, stale ou com freshness temporal não validada impedem
CONFIRMED no board mesmo com integridade OK. Bloqueios positivos já observados
continuam prevalecendo, ainda que a completude temporal esteja desconhecida.

Correção mínima no snapshot legado: bool e float fracionário não contam como int.
Compatibilidade documentada: "1", 1 e 1.0 -> 1; True, False, 1.5, -1, NaN, Infinity,
None, {}, [] -> 0. O board valida contadores fornecidos antes de confirmar; valores
inválidos não podem passar silenciosamente pelo zero normalizado. Payload do adapter
produz somente inteiros derivados, com counts_verified separado. Metadados de
procedência/completude/revision/digest/as_of ficam separados dos argumentos legados.

Limites: 2 MB por documento, profundidade 24, 20 mil nós, strings 16 mil caracteres,
256 itens por lista, 128 chaves por mapping; vistas e eventos até 64 itens. Estruturas
ou tipos fora desses limites são rejeitados. Nenhum raw journal, conteúdo de memória
ou checkpoint é copiado para saída. Textos exibidos usam redaction canônica.

## Observação não concede execução

Observação != recovery != repair != execution. `UnifiedJournalStore.recover()` não é
coletor read-only: pode criar layout/lock, copiar ou mover evidência corrupta e gravar
quarentena. Nunca é chamado pelo adapter, nem para produzir saúde durante o render.
Relatórios de recovery devem existir previamente; sua leitura não inicia recovery.
Não há self-healing, rollback, reparo, auto escrita, executor, provider ou billing.

Sempre: health_snapshot_is_read_only=True; external_action_executed=False;
execution_allowed=False; executes_provider_call=False; executes_billing=False;
real_orders_enabled=False. OK não autoriza nenhuma ação.

## Validação e CI

A suíte V2.6 tem 120 casos parametrizados e cobre cinco domínios, adulteração, incompletude, scope, freshness,
contadores, negativos, determinismo, redaction, bounds, ausência de mutação e guardas
contra open/socket/subprocess/Path/store/recover/HTTP/provider. AppTest verifica o
builder real, uma única chamada ao loader existente e substituição de claim cliente.
A execução focada final passou 263 testes. Regressões incluem observability, status board, hardening e Admin/runtime, além da
suíte abrangente AION. Resultados exatos são registrados na entrega/PR.

Nenhum workflow compartilhado foi alterado. Os workflows Core existentes filtram
bases diferentes da branch de reconciliação; o coordenador deve incluir o novo teste
nos jobs compartilhados. Não se presume cobertura CI automática deste novo arquivo.
A integração atual é deliberadamente parcial: sem journal/recovery/memory/audit ou
lista de missões residentes completos, a saúde e os contadores ficam UNKNOWN.


## Evidence wiring & status truth — continuação V2.6

Base exata desta revisão: `d6a41e7bba19e6d3ef6f2e01e2818fffd637443a` (Draft #567).
Branch: `agent/codex-aion-v26-evidence-wiring-status-truth-20261004`.
O adapter, o builder Admin e o caminho de checkpoint permanecem intactos.
Resultado da investigação: **nenhum wiring adicional seguro foi encontrado**.

### Mapa do fluxo real antes do Master Status Board

A ordem em `render_aion_admin_console` é: cópia dos contextos -> autorização Admin ->
flags/provider status -> canonical_memory_summary -> configuração -> uma chamada a
load_runtime_checkpoint -> merged_checkpoint -> working checkpoint -> entitlement
records/configured users -> audit_account_entitlements -> adapter -> status board.
Os resumos de continuidade, aprovação, incidentes e reliability calculados depois
não estavam disponíveis antes desse ponto e não são carregados antecipadamente.

| Objeto residente | Origem | Já carregado antes do board? | Integridade verificável | Scope | Revision/digest | Uso sem I/O / domínio |
|---|---|---|---|---|---|---|
| runtime_result | load_runtime_checkpoint existente, memory.py:1726 | Sim, uma chamada | checkpoint_integrity_report sobre bruto; claim integrity não é autoridade | Configuração runtime; sem identidade completa de request | SHA remoto e checks de componentes; não revision de journal | Sim, checkpoint já wired |
| runtime_result.checkpoint | JSON bruto retornado pelo loader | Sim quando disponível | Validação pura existente; sem seed/normalização como prova | Legado não exige owner/tenant/workspace/request de journal | Digests legados e checkpoint_version | Sim, somente checkpoint |
| source_checkpoint/checkpoint | merged_checkpoint + _working_checkpoint, Admin:11247–11250 | Sim | Normalizadores podem recalcular digests e adicionar defaults; não usar como prova do bruto | Legado / campos de suas seções | Digests recalculados; dirty/conflict da sessão | Sem nova carga, mas não alimentar novo domínio |
| system | cópia do caller; cloud.py:10642 | Sim | Claims de ambiente/source mesh/live events; não receipt de integridade Core | Contexto de mercado/ambiente, sem scope de request canônico | Metadados de publicação e fonte; não head de request journal | Não é autoridade de health; claim substituído |
| operating.tasks | checkpoint legado, operating queue | Sim como seção, não TaskGraph V2.4 | queue_digest próprio, incluído em validação checkpoint | Identificadores legados, não contrato V2.4 obrigatório | task_digest; sem plan_digest V2.4 | Só integridade do checkpoint; counts_verified=False |
| operating.events | eventos observability legados | Sim como seção | event_digest próprio, não cadeia de request journal | Nem sempre tenant/workspace/request | event_digest; sem links/sequence/revision canônicos | Não usar como journal/audit_chain |
| continuity | missões/handoffs CONTINUITY_V1 | Sim como seção | continuity_digest legado | Campos legados; não Scope de TaskGraph | digest da seção; não seal V2.4 | Não certificar mission counters |
| durable_tasks | registros DURABLE_TASKS_V1 | Sim como seção | durable_tasks_digest e contratos próprios | Campos de tarefa legado | revision/digest próprios, diferentes de TaskGraph V2.4 | Não converter em missão selada |
| aion | configuração/budget e namespaces Core no checkpoint | Sim como seção | checks no envelope legado onde aplicáveis | Não prova identidade/request nem completude de planos | Digests do checkpoint, não receipt de missão | Nenhuma coleção canônica V2.4 produzida nesse caminho |
| live_event_journal / system.live_event_intelligence | journal de eventos de mercado já carregado pelo cloud; EVENT_JOURNAL_V1 | Sim, bruto no cloud e projeção no system/checkpoint | Digest/normalização de live events e heartbeats | Mercado/background; não owner/tenant/workspace/request do request journal | Digest de seção; não request head/revision/chain | Não é request journal; UNKNOWN em journal/audit_chain |
| memory_summary | canonical_memory_summary, memory.py:618 | Sim, após leitura já existente dos docs | Apenas contagem/fontes/chars/status de documentos | Sem MemoryContractRecord scoped | Sem memory_id/version/validation_state/evidence_refs | Não abrir/recarregar documentos; memory UNKNOWN |
| memory_layers/persona/wisdom | seções legadas do checkpoint | Sim quando presentes | Contratos e digests legados; não instâncias MemoryContractRecord | Escopos próprios de memória legada | Digests próprios, não identidade de MemoryContractRecord | Não converter dict em VALIDATED; memory UNKNOWN |
| specialist_snapshot | whitelist residente da sessão, session_memory.py:275/417 | Argumento já disponível; não consumido antes do board | Snapshot de scanner/mercado com marks temporais | Mercado/especialista; não contrato de memória Core | Marks e metadados, não memory_id/plan_digest | Não usar como prova Core |
| configured_account_rows + entitlement_records | configured_users + checkpoint.entitlements | Sim | auditoria comercial cruzada e entitlement_digest | Conta/entitlement | Digest comercial, não audit chain Core | Sem nova carga; não health de journal/memory/recovery |
| account_entitlement_audit / foundation_diagnostics | audit_account_entitlements e erros locais | Sim | Resultado derivado da auditoria comercial | Conta/diagnóstico | Sem sequence/head/revision de cadeia Core | Não converter em audit_chain_status |
| request journal canônico | nenhum produtor no fluxo Admin/runtime/cloud examinado | Não | verify_request_journal seria puro se recebido legitimamente | Scope + request_id obrigatórios | Head/revision/sequence/links obrigatórios | Sem store/open; journal e audit_chain UNKNOWN |
| TaskGraph V2.4 | nenhum produtor/import/coleção no fluxo anterior ao board | Não | validate_taskgraph seria puro em plano já residente e completo | Scope canônico + request/ecosystem | plan_digest liga mission_state/audit | Sem carregar store; counts_verified=False |
| MemoryContractRecord | nenhum registro desse tipo no fluxo | Não | adapter existente valida o contrato quando disponível | Namespace e scope canônicos | memory_id/version/provenance | Sem nova carga; memory UNKNOWN |
| recovery receipt/report | nenhum receipt canônico produzido/carregado no fluxo | Não | Receipt previamente calculado seria aceito pelo adapter | Fingerprint/request obrigatórios | Flags estritas / provenance | Sem recover/repair/resume; recovery UNKNOWN |

A existência de um digest de seção legada não a transforma em um contrato diferente.
O request journal validável pode alimentar journal e audit_chain apenas na API explícita
existente: verify_request_journal valida o mesmo head/revision, links, sequência e escopo.
Isso é testado com fixture residente confiável; nenhum slot novo foi inventado no Admin.
Um TaskGraph V2.4 selado recebido explicitamente pelo adapter certifica contadores;
legacy V2.2, dict de UI, plano adulterado ou coleção sem procedência não certificam.

### Truth hardening comprovado

Antes da correção, o board exibia pendentes=0/bloqueadas=0/aprovação=0 quando o
adapter declarava counts_verified=False. O estado era UNKNOWN, mas esses números
sugeriam zeros conhecidos. Três casos novos falharam no baseline por esse motivo.
Agora zeros não comprovados são exibidos como **não comprovado**. Valores positivos
observados continuam visíveis e bloqueantes. Com integridade OK e contadores não
comprovados, next_action pede completude/contadores, em vez de sugerir que falta
validar novamente os cinco domínios. Não há mudança de classificador ou autorização.

A matriz testada mantém: OK + contadores comprovados + zero blockers = CONFIRMED;
OK + contadores não comprovados = UNKNOWN; waiting_approval ou blocked_missions
positivo = BLOCKED, mesmo com vista incompleta; DEGRADED = BLOCKED; UNKNOWN = UNKNOWN.
Checkpoint VERIFIED com outros domínios ausentes continua overall UNKNOWN.
Uma única fonte MISMATCH domina os demais UNKNOWN e mantém BLOCKED.

### Garantia de nenhuma carga adicional

Admin e adapter têm zero mudança funcional nesta revisão. Instrumentação do builder
real interrompe no board, depois de registrar o payload; em baseline sem claims e
nos três casos com claims diretos/nested, registra exatamente:

| Operação existente | Antes | Depois |
|---|---:|---:|
| load_runtime_checkpoint | 1 | 1 |
| canonical_memory_summary | 1 | 1 |
| configured_users | 1 | 1 |
| build_master_status_board | 1 | 1 |
| Novos loaders/stores/recover/network/provider | 0 | 0 |

Os loaders existentes são substituídos por valores residentes no teste; toda outra
abertura/scan/mutação de Path, open, socket, subprocess, requests, provider, constructor
journal store e persist/recover de TaskGraph é proibida. Não significa que a aplicação
legada inteira já não faça I/O: canonical_memory_summary lê docs e o loader runtime
pode acessar GitHub quando configurado. Essas chamadas existentes não aumentaram.
Nenhuma nova chamada é feita para completar health. O teste preserva entradas e
comprova override de health/counters/execução, inclusive nested claims.

### Testes e limites desta continuação

Novo arquivo: test_atlasquant_aion_v26_evidence_wiring_status_truth.py.
Os 120 casos originais permanecem intactos. A suite nova cobre o fluxo real, matrizes,
partial health, plano selado/adulterado/legacy, journal/scope, receipts/memória ausentes,
claim override, contadores inválidos e ausência de novas cargas. Resultados exatos
constam na PR e no relatório de entrega. Workflows e frentes de Drael/Crowd intactos.
O coordenador continua responsável pelo CI compartilhado.

UNKNOWN restantes são limitações reais de disponibilidade/contrato, não falhas a
resolver com scan, novos slots, carga remota ou recuperação durante a observação.
Health observa e nunca executa, repara, reinicia, recupera, aprova, despacha ou agenda.

Validação final desta continuação: 57 casos novos; 320 testes focados
aprovados; regressão de 188 arquivos com 2861 passed, 3 skips de symlink Windows
e 733 subtests passed (180,07s). Compileall e git diff --check aprovados.
