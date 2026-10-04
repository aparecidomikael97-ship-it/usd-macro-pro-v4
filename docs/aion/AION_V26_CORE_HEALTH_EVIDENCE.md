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
