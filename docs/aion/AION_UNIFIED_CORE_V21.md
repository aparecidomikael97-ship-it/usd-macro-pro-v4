# AION Unified Core V2.1 — hardening, adapters e continuidade

## Base

Esta etapa permanece stacked sobre a Draft PR #550, branch `integration/aion-unified-core-v2-20261003`.

Ela continua separada da PR #551 da interface. Não liga o Chat AION ao app principal, não faz merge, deploy, chamada de provider externo, transação financeira nem trade real.

## Bloco V2.1A — Chat, Checkpoint Mestre e Biblioteca

### Browser reduced-motion

O contrato Chromium foi estabilizado para o fluxo em que `chat.js` reconstrói os cards `.conversation` com `replaceChildren()`. O teste re-resolve o elemento conectado e usa retry nativo do Playwright sem afrouxar o contrato:

- `prefers-reduced-motion: reduce` confirmado;
- elemento anexado;
- `transition-duration: 0s`;
- `transform: none`.

O gate específico executa o browser cinco vezes em sequência.

### Chat -> Checkpoint Mestre

`atlasquant_aion_chat_checkpoint_adapter.py` implementa o bridge sobre o `CheckpointCoreStore` existente:

- scope owner/tenant/workspace validado;
- export canônico com digest;
- nenhuma gravação automática;
- receipt de aprovação obrigatório e vinculado ao digest;
- replay para payload diferente rejeitado;
- repetição idêntica idempotente;
- conversa não vira decisão ou fato oficial automaticamente;
- Core recebe apenas âncora de export aprovado;
- nenhuma promoção automática para memória.

### Chat -> Biblioteca AION

`atlasquant_aion_chat_library_adapter.py` mantém anexos como dados não confiáveis:

- quarentena por padrão;
- hash, tamanho, nome e MIME real validados;
- PDF reutiliza pipeline existente;
- TXT entra somente como documento staged/reviewável;
- nenhum index, review, provider ou memory promotion automático;
- retrieval permanece isolado por tenant/workspace.

O bridge agora também rejeita índices forjados como "revisados" quando o schema, estado do documento, estado da passagem ou vínculo documento/passagem não satisfazem o contrato real da Library.

## Bloco V2.1B — continuidade do núcleo

### Unified Request Event Journal

`atlasquant_aion_unified_journal.py` cria uma trilha específica do lifecycle do request unificado, separada do journal de eventos de mercado.

Características:

- scope owner/tenant/workspace/request;
- cadeia de hash por evento;
- revision/head digest verificáveis;
- metadata limitada e secret-redacted;
- detecção de tamper e replay cross-tenant;
- journal não autoriza execução, não promove memória e não grava Checkpoint Mestre.

### Durable / Recovery

`atlasquant_aion_unified_durable_bridge.py` liga o preflight unificado ao `atlasquant_aion_durable_tasks.py` existente sem criar um segundo motor de tarefas.

O handoff registra o preflight já concluído e preserva a continuação como `PAUSED`, `WAITING_APPROVAL` ou `BLOCKED`.

Recovery:

- exige journal íntegro e mesmo request/scope;
- respeita digest do checkpoint e optimistic revision;
- restaura cursor/contexto somente;
- não executa próximo passo;
- não limpa aprovação pendente;
- não faz restore externo automático.

### Matriz dos 8 papéis

`atlasquant_aion_role_authority.py` formaliza os oito papéis oficiais:

1. Orquestrador / Núcleo;
2. Arquiteto / Estrategista;
3. Guardião / Auditor;
4. Prime / Execução;
5. Shadow / Pesquisa e Triagem;
6. Sentinel / Monitoramento;
7. Comercial / Leads e CRM;
8. Educador / Treinamento.

Todos continuam responsabilidades do mesmo AION Core. Nenhum papel pode sozinho:

- conceder aprovação crítica;
- executar ação externa sem gates;
- promover memória automaticamente;
- gravar checkpoint automaticamente;
- mergear `main`;
- deployar produção;
- gastar dinheiro;
- ler credenciais;
- habilitar trade real.

Aprovação crítica permanece com o proprietário humano. Mesmo uma aprovação humana explícita não equivale, por si só, à execução: o downstream execution gate continua obrigatório.

### Truth / Knowledge mapping

`atlasquant_aion_truth_mapping.py` reconcilia, de forma fail-closed, os estados do evidence engine com os estados da Biblioteca.

Regras centrais:

- `VALIDATED + SUPPORTED` pode ser mapeado a `CONFIRMED`, sem ganhar autoridade de decisão e sem promoção automática de memória;
- `CONFLICTING`, `STALE`, `QUARANTINED`, `REVIEW_REQUIRED` e `REJECTED` nunca viram fato operacional confirmado;
- conflito preserva retrieval para revisão quando permitido, mas o runtime recebe `UNKNOWN`;
- conhecimento revisado ainda passa por quarantine/policy antes de memória.

### Aprovação estritamente booleana

O runtime unificado agora considera aprovação somente quando `approved is True`. Valores truthy como `"yes"`, `"true"` ou `1` não liberam o gate nem entram como approval receipt.

## Bloco V2.1C — Journal store físico e recovery

\`atlasquant_aion_unified_journal_store.py\` adiciona persistência física fail-closed ao journal lógico sem mover autoridade, truth mapping, aprovação ou execução para a camada de armazenamento.

### Layout e atomicidade

A persistência usa IDs derivados por digest e separação por scope/request:

\`\`\`text
root/
  <scope-safe-id>/
    requests/
      <request-safe-id>/
        events/
          00000001_<event-digest>.json
        head.json
        metadata.json
        idempotency.json
        acks.json
        quarantine/
\`\`\`

Cada evento durável é imutável. A escrita usa arquivo temporário, \`flush\`, \`fsync\` do arquivo, \`os.replace\` atômico e \`fsync\` do diretório quando a plataforma suporta. O \`head.json\`, o índice de idempotência e o ledger de ACK são atualizados por substituição atômica.

Identificadores externos nunca viram paths brutos. Owner, tenant, workspace e request passam por validação, normalização e derivação por digest. Traversal, paths absolutos, drive letters, UNC, NUL e symlink escape são rejeitados.

### Estados de persistência

O ciclo físico é:

- \`STAGED\`: request conhecido, sem evento confirmado em disco;
- \`JOURNALED\`: evento já pertence ao journal lógico verificado;
- \`DURABLE\`: registro imutável confirmado no spool;
- \`ACKNOWLEDGED\`: ACK físico confirmado depois do commit;
- \`QUARANTINED\`: corrupção, conflito ou integridade insuficiente para recovery seguro;
- \`REJECTED\`: entrada rejeitada antes de virar estado durável confiável.

Não existem \`VALIDATED\`, \`TRUSTED\` ou \`APPROVED_BY_RECOVERY\` nessa camada. Persistência não equivale a verdade, aprovação nem permissão de execução.

### Idempotência, replay e causation

A chave de idempotência é persistida somente por digest, vinculada ao digest estável do payload. Após restart:

- mesma chave + mesmo payload retorna resultado idempotente;
- mesma chave + payload diferente falha fechado;
- sequence ocupada por outro digest falha fechado;
- quebra de \`prev_digest\` ou digest do payload falha fechado.

\`correlation_id\` e \`causation_id\` são metadados explícitos da camada de persistência V2; o schema V1 do journal lógico não é alterado.

### Recovery

O recovery reabre somente o scope autorizado, valida metadata/version, sequência, cadeia de digest, scope fingerprint, índice de idempotência, head e ACK. Arquivos temporários órfãos são isolados em \`quarantine/\` e nunca tratados como eventos duráveis.

Janelas de crash cobertas:

- antes do durable commit;
- depois do fsync do temp e antes do rename;
- depois do commit do evento e antes do head/ACK;
- depois do head e antes do ACK;
- depois do ACK.

O recovery reconstrói somente estado. Ele não chama provider, não envia mensagem externa, não executa trade, não executa ação financeira, não escreve Checkpoint Mestre, não remove aprovação pendente e não promove memória.

### Concorrência e limites

O locking é por request/scope, com timeout e sem lock global. Escritas concorrentes com a mesma idempotency key são deduplicadas; tenants/workspaces distintos usam storage e lock scopes distintos.

Há limites para tamanho de evento, metadata, índice, chave de idempotência e número máximo de eventos recuperados. Estados acima desses limites falham fechado.


## Testes adversariais V2.1

`test_atlasquant_aion_unified_hardening_v21.py` cobre:

- tamper da cadeia do journal;
- replay cross-tenant;
- metadata secreta;
- checkpoint drift;
- recovery com journal alterado;
- preservação de `WAITING_APPROVAL`;
- fake approvals truthy;
- autoridade crítica dos oito papéis;
- truth mapping conflitante/stale/quarentena/rejeitado;
- índice revisado forjado;
- retrieval conflitante sem promoção para fato confirmado.

## CI

Os gates específicos do AION aceitam a branch-base da #550 enquanto esta PR stacked está em revisão:

- AION Unified Core;
- AION Core Security Gate.

Os workflows globais `Quality tests` e `AtlasQuant - Release Readiness` permanecem `main`-only, preservando o contrato de produção. O Quality completo será exercitado quando a cadeia chegar à integração normal contra `main`.

## Limites remanescentes

Continuam fora desta revisão:

- provider runtime real;
- ligação do Chat AION à UI principal;
- merge/deploy;
- execução externa;
- trade real;
- ação financeira.

Nada nesta etapa executa ação externa, provider real, trade, merge ou deploy.


## AION Core V2.1D — Integrity / Recovery Governance

Escopo desta seção: governança de integridade e recuperação do unified journal store
(`atlasquant_aion_unified_journal_store.py`). Não executa provider, ação externa, trade,
merge ou deploy. Recovery é state-only.

### Reason codes estáveis (19)

A API de integridade não depende mais de `str(exc).upper().replace(" ", "_")`.
Cada falha carrega `reason_code` estruturado e `reason_detail` bounded/redacted:

| Code | Classe | Significado |
|---|---|---|
| CORRUPT_JSON | HARD | JSON/estrutura ilegível ou schema inválido |
| RECORD_DIGEST_MISMATCH | HARD | envelope digest do record diverge (sem causa semântica específica) |
| EVENT_DIGEST_MISMATCH | HARD | digest do evento lógico diverge |
| PREV_DIGEST_MISMATCH | HARD | chain prev_digest diverge |
| SEQUENCE_MISMATCH | HARD | sequence persistida diverge da esperada |
| SCOPE_MISMATCH | HARD | identidade de scope (owner/tenant/workspace/fingerprint) diverge |
| REQUEST_MISMATCH | HARD | request_id/conversation diverge |
| PERSISTENCE_VERSION_MISMATCH | HARD | versão de persistência não aceita |
| HEAD_POINTS_TO_MISSING_EVENT | HARD | head aponta para evento inexistente |
| ACK_INVALID | HARD | ACK futuro, digest errado, downgrade ou inválido |
| IDEMPOTENCY_INDEX_MISMATCH | HARD | índice de idempotência contraditório (hard corruption) |
| SYMLINK_ESCAPE | HARD | symlink fora do root do store |
| UNSAFE_PATH | HARD | path escapa do root do store |
| ORPHAN_TEMP | WARNING/HARD | temp órfão: MOVED = warning; PENDING = bloqueia resume |
| STALE_HEAD | WARNING | head ausente/antigo (não é corrupção hard) |
| LOCK_TIMEOUT | HARD | lock excedeu o timeout configurado |
| RECOVERY_LIMIT_EXCEEDED | HARD | limite de bytes/eventos excedido |
| IDEMPOTENCY_INDEX_STALE | WARNING | janela de crash conhecida: evento commitado, índice ausente |
| REQUEST_QUARANTINED | REJECTED | nova operação em request com evidência de quarantine |

### Prioridade causal do diagnóstico

Quando uma adulteração específica também invalida o envelope `record_digest`,
o code semântico específico tem precedência. Ordem de validação em
`_validate_event_record` e `_validate_metadata`: estrutura → version → scope →
request → sequence → prev_digest → event_digest → record_digest (envelope por último).

Exemplos: scope adulterado → SCOPE_MISMATCH; request adulterado → REQUEST_MISMATCH;
sequence adulterada → SEQUENCE_MISMATCH; event digest adulterado → EVENT_DIGEST_MISMATCH;
somente envelope adulterado → RECORD_DIGEST_MISMATCH.

O scan (`_scan_valid_records`) preserva reasons estruturados e levanta a exception via
`_scan_failure(reasons)`, que fixa `reason_code` no primeiro code causal — o scan nunca
se reduz a `UNSAFE_PATH` por default de classe.

### REJECTED × QUARANTINED

- **QUARANTINED**: evidência persistida com integridade comprometida. Corrupção descoberta
  em disco é detectada por `recover()`, copiada (COPY+VERIFY), original preservado,
  registrada no manifest, e o request fica QUARANTINED.
- **REJECTED**: operação recusada pelo contrato (ACK inválido, idempotency conflict,
  scope mismatch, request quarantined, unsafe path).
- **Ciclo quarantine**: corrupção → `recover()` → detecção → COPY+VERIFY → original
  preservado → manifest → request QUARANTINED → novas operações REJECTED/REQUEST_QUARANTINED.
- Sem `recover()` anterior, uma nova operação pode encontrar a corrupção diretamente e
  retornar o integrity reason original (ex.: CORRUPT_JSON).
- Manifest ilegível/inválido: nova operação → fail closed → REQUEST_QUARANTINED;
  recovery → reporta a corrupção estrutural real, safe_to_resume=False.

### Quarantine manifest

`quarantine/manifest.jsonl`, schema
`ATLASQUANT_AION_UNIFIED_JOURNAL_QUARANTINE_MANIFEST_V1`: schema, persistence_version,
timestamp_utc, scope_fingerprint, request_id_safe, original_relative_path,
quarantine_relative_path, reason_code, reason_detail (bounded), observed_digest,
expected_digest, sequence, event_digest, detection_phase, recovery_attempt_id,
previous_manifest_digest, manifest_record_digest. Encadeamento de digest (GENESIS no
primeiro record). Sem payload bruto; sem segredo (prova por teste com fixture
`token="secret-example"`). Append crash-aware: ler último digest → temp → fsync →
replace → fsync dir. Status: COPIED, MOVED, PENDING.

### ORPHAN_TEMP

- MOVED: warning; não é hard failure; não força QUARANTINED; pending=0.
- PENDING: quarantine_clear=False; safe_to_resume=False.

### Idempotency

- IDEMPOTENCY_INDEX_STALE: warning de crash window conhecida (evento commitado, índice
  ausente após crash AFTER_EVENT_COMMIT).
- IDEMPOTENCY_INDEX_MISMATCH: contradição real no índice persistido → hard failure.
- Same key + different payload → REJECTED / IDEMPOTENCY_INDEX_MISMATCH.

### ACK cumulativo

`acks.json` persiste aditivamente (mapping legado `entries` preservado):

```json
{
  "schema": "...", "kind": "acks", "persistence_version": 2,
  "acked_through_sequence": 10,
  "acked_head_digest": "sha256:...",
  "scope_fingerprint": "...", "request_id_safe": "...",
  "entries": {"1": {...}, "2": {...}}
}
```

- Advance: N=5 → N=8 persiste `acked_through_sequence=8` + `acked_head_digest=digest_8`,
  sem perder entries anteriores.
- Igual: idempotente.
- Downgrade (N < atual): REJECTED / ACK_INVALID, arquivo não alterado.
- Future (N > head): REJECTED / ACK_INVALID, arquivo não alterado.
- Bad digest: REJECTED / ACK_INVALID, arquivo não alterado.
- Cross-scope: LookupError quando o request dir do scope B não existe (dir derivado do
  scope fingerprint); SCOPE_MISMATCH quando metadata/event de outro scope é apresentado
  dentro de um request dir válido.
- Request quarantined: REJECTED / REQUEST_QUARANTINED.
- Leitura do formato legado: normaliza em memória (`_acked_through`) sem reescrever o
  arquivo apenas por leitura.

### safe_to_resume

Conjunção explícita: scope_valid ∧ request_valid ∧ chain_valid ∧ version_accepted ∧
head_consistent ∧ idempotency_consistent ∧ ack_consistent ∧ quarantine_clear ∧
deterministic_recovery ∧ sem hard failures. Na dúvida (ambíguo/UNKNOWN): False.
`automatic_resume_executes` sempre False.

### Recovery report

Campos novos: schema, persistence_version, scope_fingerprint, request_id_safe,
recovery_attempt_id, events_scanned, last_valid_sequence, recovered_head_digest,
scope_valid, request_valid, chain_valid, version_accepted, head_consistent,
idempotency_consistent, ack_consistent, quarantine_clear, deterministic_recovery,
quarantine_count, quarantine_pending_count, warnings, hard_failures, reason_codes,
safe_to_resume. Compatibilidade legada preservada: status, persistence_state,
event_count, journal_integrity, head_status, ack_status, quarantined_files, reasons.
`quarantine_count`/`quarantine_pending_count` vêm do manifest (fonte auditável), não de
contagem de arquivos.

### State-only invariants

Recovery nunca executa provider, envia ação externa, escreve checkpoint, promove memória
ou retoma tarefa externa automaticamente:

```
restores_state_only=True
automatic_resume_executes=False
checkpoint_written=False
external_action_executed=False
memory_promoted=False
```

### Crash windows

Fault injection cobre: AFTER_TEMP_FSYNC (ORPHAN_TEMP), AFTER_EVENT_COMMIT
(IDEMPOTENCY_INDEX_STALE), BEFORE/AFTER_QUARANTINE_FILE_MOVE, BEFORE/AFTER_QUARANTINE_MANIFEST_COMMIT.
Invariantes: evidência nunca desaparece; manifest nunca declara move concluído se o
arquivo não está lá; safe_to_resume continua False quando pendência existe.

### Limitações desta versão

- Content Attestation real ainda não existe (declaração ≠ prova).
- Symlink/hardlink/junction não são comprovados fisicamente além dos checks de path.
- Executor real ainda não está ligado; todos os campos de execução permanecem False.