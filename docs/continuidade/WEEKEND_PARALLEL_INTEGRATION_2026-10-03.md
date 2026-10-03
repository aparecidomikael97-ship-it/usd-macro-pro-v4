# AtlasQuant/AION — Plano de Integração Paralela do fim de semana

Base de coordenação: `main@f0ce8af00357e09b17d092ea70218258ecdd3426`.

## Objetivo

Executar três frentes em paralelo sem colisão:

1. **Codex — Interface**: fidelidade compacta do Trader, hover, ticker, PT-BR, Negócios sem ticker, responsividade.
2. **Drael — AION Core**: consolidação do núcleo unificado, reaproveitamento seguro da fundação da PR #543, memória/checkpoint, 8 papéis, autorização, evidência, biblioteca e testes backend.
3. **Coordenação — ChatGPT**: vigiar drift/conflitos, comparar PRs com a main, revisar CI, controlar ordem de integração e impedir merge de branches antigas/superseded por engano.

## Regras de isolamento

### Codex
Pode alterar arquivos de interface necessários ao pacote visual, em branch criada da main atual. Evitar AION Core/backend profundo.

### Drael
Não alterar, enquanto o Codex estiver ativo:
- `atlasquant_reference_ui.py`
- `atlasquant_premium_shell.py`
- `atlasquant_ecosystem_workspace_ui.py`
- `atlasquant_central_hub_ui.py`
- `assets/ecosystem_reference/*`
- CSS da interface de referência
- `usd_macro_pro_v4_cloud.py` salvo necessidade documentada e adiada

Pode atuar em `aion_core/*`, `aion_chat/*`, módulos AION backend e testes correlatos.

### Coordenação
Somente documentação, comparação, auditoria de branches/PRs, CI e plano de integração. Nenhuma alteração concorrente em código funcional.

## PRs antigas / cuidado

- **#545** — Interface V4: Draft antiga. Não usar como base de nova interface.
- **#543** — AION Chat Foundation: útil como fonte de arquivos/arquitetura, mas branch antiga e divergida. Não mergear diretamente; portar/reaproveitar sobre main atual.
- **#540** — Checkpoint reconciliation V2: não misturar automaticamente com interface nem com a consolidação do núcleo; revisar isoladamente antes de qualquer merge.

## Ordem de integração recomendada

1. Codex termina interface em Draft PR.
2. Revisar diff, screenshots e gates.
3. Somente com autorização explícita: merge da interface.
4. Atualizar/rebasear a branch do Drael sobre a nova main se necessário.
5. Resolver qualquer conflito de integração do AION Core.
6. Rodar gates AION + regressão geral.
7. Somente com autorização explícita: merge do núcleo.
8. Depois disso, os dois agentes podem trabalhar em paralelo no núcleo com divisão formal:
   - agente A: orquestração, memória, checkpoint, autorização;
   - agente B: biblioteca, conhecimento, validação, provenance.

## Critérios de aceite — Interface

- referência compacta preservada;
- hover/focus sem segundo quadrado deslocado;
- ticker Trader rolável e sem dados inventados;
- bandeiras/ícones coerentes;
- Negócios sem ticker e sem gap;
- Investimentos coerente;
- PT-BR;
- desktop/tablet/mobile;
- screenshots;
- UI Smoke + Mobile DOM + checks relevantes verdes.

## Critérios de aceite — AION Core

- um único AION Core;
- 8 papéis internos sem soberania independente;
- chat persistente reaproveitado sem regressão;
- memória de conversa não substitui Checkpoint Mestre;
- promoção de memória governada por verdade/proveniência;
- autorização READ_ONLY/LOW_RISK/REQUIRES_APPROVAL/BLOCKED;
- tenant/workspace isolation;
- action receipts + event journal;
- recovery/replay;
- biblioteca integrada por contrato, sem auto-promover anexos;
- provider ausente retorna estado explícito;
- sem execução externa, merge, deploy ou trade real;
- testes e security gates verdes.

## Gate anti-conflito antes de qualquer merge

Antes de qualquer merge:
- confirmar head SHA exato;
- comparar com `main`;
- exigir `behind_by = 0` ou reconciliar;
- revisar arquivos sobrepostos entre PRs;
- revisar CI no head final;
- confirmar ausência de alterações em auth/RBAC/secrets fora do escopo;
- não aceitar auto-merge;
- não aceitar deploy sem autorização explícita.

## Estado atual

- `main`: `f0ce8af00357e09b17d092ea70218258ecdd3426`
- Interface V7 (#549): já mergeada.
- Codex: trabalhando no refinamento V8/compacto.
- Drael: trabalhando na consolidação do AION Core.
- Coordenação: monitoramento e integração em andamento.
