# AION Core Independence V1

Data: 2026-09-29
Leitura por AST dos arquivos `atlasquant_aion*.py` presentes neste branch.

## Classificação

PURE CORE, allowlist testada:

- `atlasquant_aion_core`
- `atlasquant_aion_fortress`
- `atlasquant_aion_resilience`
- `atlasquant_aion_durable_tasks`
- `atlasquant_aion_critical_review`
- `atlasquant_aion_memory_quarantine`
- `atlasquant_aion_memory_layers`
- `atlasquant_aion_tenant`
- `atlasquant_aion_knowledge_graph`
- `atlasquant_aion_vault`
- `atlasquant_aion_observability`
- `atlasquant_aion_evaluation_lab`
- `atlasquant_aion_model_router`
- `atlasquant_aion_model_registry`
- `atlasquant_aion_loop_governor`

O fecho de import desses módulos não inclui Trader, Radar, Investimentos, Negócios, Streamlit nem `requests`. O teste importa a allowlist num processo com esses módulos bloqueados e sem variáveis de segredo.

`atlasquant_access_control`, usado por tenant, importa `secrets` da biblioteca padrão para HMAC. Isso não lê um segredo de ambiente.

## Acoplamento observado, não escondido

PARCIAL. Estes imports existem e não foram removidos:

- UI: `atlasquant_aion_admin.py` e `atlasquant_aion_replay_panel.py` importam Streamlit. Admin também importa `atlasquant_aion_business`.
- Negócios: `atlasquant_aion_memory.py`, `atlasquant_aion_approval_inbox.py`, `atlasquant_aion_specialist_evidence.py` e `atlasquant_aion_specialist_session.py` importam `atlasquant_aion_business`.
- Investimentos: os dois módulos de specialist importam `atlasquant_investment_ecosystem`.
- Infra: `atlasquant_aion_memory.py`, `atlasquant_aion_recovery.py`, `atlasquant_aion_provider.py` e os módulos de global worker importam `requests`.

Não há import direto de `atlasquant_home_radar.py`, `paper_trading_v112.py` ou `atlasquant_tradingview_parity.py` dentro de `atlasquant_aion*.py` nesta leitura.

## Caminho de desacoplamento, sem refactor nesta sessão

1. `atlasquant_aion_memory.py` deve receber métricas de negócio por um registro/adapter, não por import do módulo de negócio.
2. Specialist evidence/session deve depender de um contrato de evidência, não de `atlasquant_investment_ecosystem`.
3. Admin e replay panel permanecem UI e fora da allowlist pura.
4. Recovery, provider e worker permanecem infra e fora da allowlist pura.

O teste `test_known_domain_couplings_stay_explicit` falha se essa lista mudar. Remover um acoplamento exige atualizar o inventário no mesmo commit.
