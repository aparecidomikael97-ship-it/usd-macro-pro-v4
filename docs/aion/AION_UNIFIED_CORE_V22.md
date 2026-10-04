## AION Core V2.2A — Unified Mission Orchestration / Handoff Contract

Camada fina que transforma um `AionRequest` validado em uma especificação de
missão (`AionMission`) durável, auditável e fail-closed. **Mission != Execution**:
a missão nunca executa — no máximo prepara handoff para uma futura camada de
execução guardada.

### Fluxo

```
User Request
   ↓
Unified Runtime (process_aion_request — visão canônica de papel/truth/autorização/model lane)
   ↓
Mission Planner (atlasquant_aion_unified_mission.prepare_aion_mission)
   ├── Capability Planner (plan_agentic_mission — reutilizado, não duplicado)
   ├── Role Authority (official_role_authority_matrix — 8 papéis, independent_ai=False)
   ├── Truth (via runtime; EVIDENCE_CONFLICT → blocker truth:CONFLICT)
   ├── Quarantine (detecção explícita na mission layer: QUARANTINED/REJECTED/DOUBTFUL/INVALID)
   └── Budget/Model (provider_state ZERO_COST_LOCAL por padrão)
   ↓
Durable Task Handoff (new_durable_task — estado PLANNED, nunca RUNNING)
   ↓
PREPARED / WAITING_EVIDENCE / WAITING_APPROVAL / BLOCKED / READY_FOR_GUARDED_HANDOFF
   ↓
[future execution layer — NOT V2.2A]
```

### Regras de segurança centrais

- **Authorization é fonte independente**: `authorization_class == REQUIRES_APPROVAL`
  impede `PREPARED` mesmo quando o capability plan é local/vazio;
  `authorization_class == BLOCKED` força `BLOCKED`.
- **EVIDENCE_CONFLICT**: quando o runtime sinaliza conflito de evidência canônica,
  a missão adiciona o blocker `truth:CONFLICT` e fica `BLOCKED`. A mission layer
  NÃO reexecuta `assess_truth()` — compõe o resultado canônico do runtime.
- **Quarantine detectado na mission layer**: estados QUARANTINED/REJECTED/DOUBTFUL/INVALID
  em registros de evidência → hard blocker (o truth module não possui QUARANTINED como state).
- **Aprovação estritamente booleana**: somente `approved is True`. `1`, `"yes"`,
  `"true"`, `"sim"`, `[]`, `{}` não são aprovação.
- **Approval não executa**: mesmo com `approved=True`, `execution_allowed=False` e
  `external_action_executed=False`; no máximo `READY_FOR_GUARDED_HANDOFF` com
  `requires_downstream_execution_gate=True`.
- **Durable Task inicia PLANNED**: nenhum step RUNNING automático; nenhum executor chamado.
- **Recovery state-only**: `restores_state_only=True`, `automatic_resume_executes=False`,
  `checkpoint_written=False`, `external_action_executed=False`, `memory_promoted=False`.
- **Memória PROPOSED_ONLY**: candidatos nunca são promovidos automaticamente.
- **Checkpoint não automático**: `checkpoint_candidate` é metadata de intenção;
  `checkpoint_written=False` sempre nesta etapa.
- **Provider/billing**: `executes_provider_call=False`, `executes_billing=False`,
  `real_orders_enabled=False` em toda saída.

### Mission states (precedência determinística)

1. BLOCKED — capability bloqueada, authorization BLOCKED, truth conflict, quarantine, scope
2. WAITING_EVIDENCE — evidência obrigatória ausente, truth stale/unknown
3. WAITING_APPROVAL — ação REQUIRES_APPROVAL sem `approved is True`
4. READY_FOR_GUARDED_HANDOFF — aprovada ou com side effects futuros, pronta para gate de execução
5. PREPARED — local/read-only, sem pendências

### Idempotência e tamper

- `request_digest`: SHA-256 canônico da identidade lógica do request (sem timestamps voláteis).
- `mission_id`: determinístico a partir de request_id + request_digest + scope fingerprint.
- `mission_digest`: SHA-256 do spec canônico (scope, objective, capabilities, steps,
  evidence requirements, authorization, approval requirements, recovery policy).
- Replay: mesmo request_id + mesmo digest → `idempotent_replay=True`;
  mesmo request_id + digest diferente → `REQUEST_PAYLOAD_MISMATCH`;
  prior mission adulterada → `PRIOR_MISSION_DIGEST_MISMATCH`;
  cross-tenant/workspace → `CROSS_TENANT_REPLAY`.
- `validate_aion_mission` recomputa o digest: divergência → `MISSION_DIGEST_MISMATCH`;
  step ids duplicados → `DUPLICATE_STEP_ID`.

### Limites

MAX_OBJECTIVE_CHARS=2000, MAX_STEPS=32, MAX_EVIDENCE_REFS=64, MAX_WARNINGS=32,
MAX_BLOCKERS=32, MAX_ATTACHMENTS=16, MAX_CAPABILITIES=32. Objetivo vazio/excessivo
e anexos excessivos falham fechado (`OBJECTIVE_EMPTY`, `OBJECTIVE_TOO_LARGE`,
`ATTACHMENTS_TOO_MANY`).

### O que a V2.2A NÃO faz

provider real, tool execution, email, WhatsApp, GitHub write, deploy, trade, billing,
memory promotion, checkpoint write automático, merge, execução externa de qualquer espécie.
