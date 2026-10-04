# AION V2.7 — Health Evidence Attestation + Readiness Red-Team

Base exata: `56d6e8a79806d93507f6b3e9e6ad4e11dc9de7ae`.
Branch: `agent/codex-aion-v27-health-attestation-readiness-20261004`.
Base da Draft PR: `integration/aion-core-v26-status-truth-20261004`.

## Resultado e limite de prontidão

Claims verified=True, complete=True, source_ref bonito, timestamp ou digest presente
não comprovam conteúdo canônico. O red-team inicial reproduziu receipt de recovery
fabricado que virava VERIFIED e inventário vazio sem scope próprio que virava
contadores verificados; ambos chegavam a integrity OK / board CONFIRMED nas fixtures.
Flags de execução continuavam False. As duas rotas foram endurecidas no adapter.

**Prontidão restrita a callers Python confiáveis e ao builder Admin existente.**
Não há assinatura, chave secreta, autenticação de origem física ou attestation de
persistência. Um hash público prova consistência, não autenticidade. Código Python
arbitrário no mesmo processo pode construir estruturas canonicamente válidas ou
substituir validadores; não é possível prometer impossibilidade criptográfica de
falsificação por esse atacante usando somente os contratos existentes.
Um teste executável preserva essa distinção: fixtures canonicamente válidas produzem
CONFIRMED, mas não produzem origin_authenticated=True nem permissão de execução.

Não foi criada segunda autoridade, signer, collector, loader, schema paralelo de
health ou tentativa de eliminar UNKNOWN. O builder Admin não mudou e continua
substituindo claims do caller usando apenas o checkpoint bruto já carregado.
Journal/audit, recovery e memory permanecem UNKNOWN sem conteúdo canônico residente;
mission counters permanecem não comprovados sem inventário canônico residente.

## Fluxo READ ONLY

```
LoadedEvidence (nome atual do conceito EvidenceSource)
 -> scope explícito / scope intrínseco do conteúdo
 -> contrato temporal explícito, quando houver
 -> validador canônico puro do domínio
 -> evidência normalizada bounded, provenance e contadores
 -> core_health_snapshot (classificador existente)
 -> Status Board (integridade + bloqueios operacionais)
```

verified claim != trusted evidence
source_ref != authority
health observation != authorization
CONFIRMED health != execution permission

A ordem real no código valida conteúdo/scope e depois freshness; não há I/O nessa
cadeia. Invalidade de conteúdo não é resgatada por metadados positivos. Eventos sem
created_at não recebem relógio inventado; now temporal é aware e explícito.

## APIs públicas próprias

| API | Entrada | Normalização/validação | Scope e tempo | Saída |
|---|---|---|---|---|
| LoadedEvidence | source_ref/value/kind/scope/complete/temporal/as_of | dataclass frozen, sem assinatura; validação acontece no builder | metadados declarados pelo caller confiável | wrapper; não possui campo verified |
| HealthEvidenceError | erro de bounds/tipo/scope | ValueError fail-closed | não aplica | rejeição do contrato |
| build_core_health_evidence | seis entradas de domínio explícitas, events/versions/now/expected_scope | tipos exatos, bounds, cópia, redaction, validadores existentes | vínculo de escopo, sem mistura; sem TTL genérico | cinco statuses, quatro contadores, provenance/completude, flags; não decide integrity_state |
| build_loaded_runtime_health_evidence | resultado residente do loader runtime existente | seleciona checkpoint bruto, revalida conteúdo; ignora claims de health/counters | não inventa identidade ou frescor | payload parcial; demais domínios UNKNOWN |

Helpers/validadores importados são acessíveis pelo namespace Python (não há __all__),
mas não constituem novas APIs de attestation: Scope, verify_request_journal,
journal_digest, reconstruct_checkpoint, checkpoint_integrity_report,
MemoryContractRecord, create_memory_record, operational_decision, validate_taskgraph,
normalize_evidence_record, core_health_snapshot, normalize_events, redact_text.
Nenhuma função de persistência/recovery é usada como coletor de saúde.

## Validação por domínio

| Domínio | Conteúdo e validação | Escopo/completude | Comportamento |
|---|---|---|---|
| journal / audit_chain | verify_request_journal: schema, sequence, links, digest, revision, head | owner/tenant/workspace/request intrínsecos; conflitos rejeitados | claims/status/listas arbitrárias não ficam bons; mesmo journal pode justificar os dois domínios |
| checkpoint master | reconstruct_checkpoint: base/state/head/event/patch digests, revision e safety | envelope global não ganha owner inventado; scopes fornecidos vinculados | verified=True não contorna reconstrução |
| checkpoint legado | checkpoint_integrity_report sobre bruto | caminho Admin já existente, sem seed/working copy como prova | transporte ou claim integrity não substitui validador |
| recovery | flags estritas + journal canônico residente no receipt, validado por verify_request_journal | fingerprint/request/scope vinculados; head/revision do report devem concordar com o journal e ter tipo exato | receipt só com flags/hash público fica UNKNOWN; conteúdo adulterado fica negativo |
| memory | MemoryContractRecord real, recriação e operational_decision | namespace/scope/id/version/evidence refs; nenhum dict promovido | CONFLICTING/QUARANTINED/REJECTED negativos; OUTDATED/UNVERIFIED não positivos |
| mission counters | validate_taskgraph em cada plano V2.4 | inventário complete=True e scope próprio owner/tenant/workspace; legacy não certifica | ausência/incompletude/tamper não certificam; lista vazia com scope correto prova zero apenas no contrato do caller confiável |

A validação lógica de um recovery journal não autentica sua leitura do disco, nem
prova por si só ack/idempotency/quarentena físicos. Flags desses fatos continuam
procedência do produtor confiável. O Admin não tem esse receipt residente e não o
fabrica. A coleção parcial declarada complete=False não certifica contadores; uma
coleção parcial falsamente declarada completa por código Python confiável abusivo
não pode ser descoberta sem um contrato externo de inventário autenticado.

A fixture positiva V2.6 foi fortalecida com o journal canônico no receipt. Nenhum dos
120 testes/asserts originais foi removido, relaxado ou transformado em xfail.

## Tempo e freshness

Sem contrato temporal: NOT_EVALUATED, sem TTL inventado. as_of do wrapper é metadata
observacional; não concede freshness. Contratos temporais são temporal.timestamp,
temporal.as_of, ttl/ttl_seconds e expires_at explicitamente fornecidos.

Timestamps temporais exigem string ISO aware; naive/invalid/vazio/None são
UNVERIFIED. Futuro respeita FUTURE_TOLERANCE_SECONDS já existente no truth module;
expiry não contorna o teste do timestamp. TTL exige int/float exato finito e não
negativo: bool/Decimal/NaN/Infinity não são duração válida. expires_at exige aware;
expiry anterior a as_of é incoerente e expiry <= now é STALE. Nenhum stale/expired
pode confirmar saúde. Limites numéricos e de documento continuam bounded.

## Ataques executáveis

Arquivo: test_atlasquant_aion_v27_health_attestation_redteam.py.

- seis domínios com verified=True e None/vazio/dict/status/digest falso;
- dezesseis nomes/formas de source_ref: trusted/canonical/admin/root/github/production,
  Unicode confusable, case, whitespace, NUL, caminhos/URL e múltiplos slash; nunca
  abrem caminho/URL nem concedem autoridade só pelo nome;
- datas futuras/antigas/naive/invalid/vazias, expiry incoerente/igual a now,
  TTL negativo/booleano/nonfinite;
- checkpoint/event chain/revision/event_id/safety adulterados;
- journal e audit removidos/duplicados/reordenados, head antigo, links/sequence,
  digest/request/scope errados;
- planos V2.4 legítimos/adulterados, UI dict, lista parcial, contadores caller,
  cross-tenant/workspace e legacy V2.2 (também nas regressões V2.6);
- memória real, dict falso e estados não positivos;
- receipt de recovery sem conteúdo, journal/report head/revision adulterados,
  revision booleana, cross-scope e stale;
- múltiplas evidências por domínio: API não aceita merge; listas de wrappers são
  UNKNOWN, sem selecionar candidato conveniente;
- mutações posteriores do dict/list/scope/status/digest não alteram saída calculada;
  entradas preservadas e repetição 100 vezes determinística;
- bool/int/IntEnum/Decimal/float/NaN/Infinity/bytes/custom Mapping/subclasses/objeto
  truthy com str/int hostis não são coercidos em evidência boa;
- claims diretos/aninhados no builder Admin real; loader continua 1 -> 1;
- toda cadeia com open/Path/socket/subprocess/HTTP/store/recover/persistence/provider
  proibidos. Sem write/network/recovery/repair/execution.

Matriz existente preservada: cinco domínios bons + counts_verified=True + zero
blockers -> CONFIRMED; counts_verified=False -> UNKNOWN e zeros não comprovados;
blocker positivo permanece visível/BLOCKED; DEGRADED -> BLOCKED; UNKNOWN não confirma.

## Defeitos e falsos positivos

Reproduzidos antes de patch: recovery apenas declarativo; inventário sem scope;
expiry mascarando timestamp futuro; naive aceito como UTC; TTL bool aceito como 1;
expiry == now tratado como FRESH; expires_at de tipo inválido lançando AttributeError;
revision True igual a 1 no report. Patches mínimos apenas no adapter.
Metadados hostis não acionam conversão e scope não chama igualdade de objeto hostil.

Descartados: testes de mutabilidade iniciais contaminavam a constante SCOPE entre
casos por alias de fixture. As fixtures red-team agora são cópias independentes.
Substituir arbitrary value por uma estrutura canônica genuína validável não é
bypass do validador; é o limite entre integridade lógica e autenticidade de origem.
Uma data antiga sem TTL contratual não autoriza inventar expiração universal.

## Verificação e entrega

Regressões obrigatórias: V2.7, V2.6 adapter/wiring, observability, Status Board,
hardening V2.4, Admin/runtime; depois regressão ampla AION. Contagens finais na PR.
Nenhum workflow ou arquivo protegido Drael/Crowd alterado. Nenhum núcleo novo.

ZERO MERGE / ZERO DEPLOY. No Core: ZERO PROVIDER, BILLING, PAID API, EXTERNAL
COMMUNICATION, REAL ORDER, AUTO-REPAIR, EXTERNAL EXECUTION.
GitHub somente para publicar branch e Draft PR autorizados.

Também reproduzido e corrigido: expected_scope não usa mais coerção por truthiness.
False, 0, dict subclass vazio e objeto hostil são rejeitados sem chamar __bool__.

Validação final: 437 casos V2.7; 757 testes focados aprovados.
Regressão de 190 arquivos: 3307 passed, 3 skips de symlink Windows,
737 subtests passed (186,30s). Compileall e git diff --check aprovados.
