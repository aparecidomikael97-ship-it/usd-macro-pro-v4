# AION Parallel Command Center — 2026-10-03

Base canônica: `main` @ `e0ae719ee4b66403ea86e66fe4a308dcccd923f5`

## Prioridade oficial desta fase

1. AION Core operacional
2. AION Negócios em paralelo
3. Investimentos em paralelo, com escopo controlado
4. Trader congelado até conclusão desta fase

O Trader não deve receber refatoração, migração visual ou expansão funcional neste ciclo, exceto correção bloqueante que impeça o Core, Negócios ou Investimentos.

## Regra de integração

- Nenhum agente trabalha diretamente em `main`.
- Cada frente usa branch própria baseada na SHA canônica acima.
- Cada entrega deve terminar em Draft PR.
- Nada de merge, deploy, gasto externo, segredo real ou ação irreversível sem autorização explícita do proprietário.
- Não duplicar módulos já existentes; primeiro reutilizar os contratos e bridges atuais.
- Toda alteração precisa de testes, evidência e descrição do risco residual.
- Se descobrir dependência cruzada, registrar e parar naquele limite em vez de alterar outra frente silenciosamente.

## Frente A — Cortex: AION Execution Bridge

Objetivo: transformar o estado `READY_FOR_GUARDED_HANDOFF` da missão unificada em execução guardada e auditável, sem enfraquecer os gates existentes.

Arquivos-base a revisar antes de editar:
- `atlasquant_aion_unified_mission.py`
- `atlasquant_aion_unified_runtime.py`
- `atlasquant_aion_capability_planner.py`
- `atlasquant_aion_durable_tasks.py`
- `atlasquant_aion_unified_durable_bridge.py`
- `atlasquant_aion_action_receipt.py`
- `atlasquant_aion_tool_hub.py`
- `atlasquant_aion_local_executor.py`
- `atlasquant_aion_worker_runtime.py`

Primeira entrega esperada:
- um executor guardado mínimo;
- registry/allowlist de ferramentas;
- separação read-only vs write/side-effect;
- recusa de missão que não esteja pronta;
- scope/workspace/tenant vinculados;
- approval exata para ações privilegiadas;
- receipt idempotente e auditável;
- sem auto-merge, auto-deploy, trading real ou billing.

## Frente B — Drael: Core Consolidation + Checkpoint

Objetivo: reduzir duplicação e fechar lacunas reais do Core usando `main` atual como verdade, sem criar um segundo núcleo.

Foco:
- varredura do Checkpoint Mestre e compromissos históricos;
- confrontar lacunas antigas com o que já está efetivamente em `main`;
- identificar módulos duplicados, órfãos ou contraditórios;
- consolidar segurança, recuperação, journal, durable state e role authority;
- preparar uma matriz curta: CONFIRMADO / PARCIAL / AUSENTE / OBSOLETO;
- nenhuma execução externa.

Primeira entrega esperada:
- relatório de reconciliação atual;
- lista priorizada de no máximo 10 lacunas reais;
- correções pequenas e independentes apenas onde houver evidência clara;
- testes correspondentes;
- Draft PR separado.

## Frente C — Grok: revisão independente de Negócios + Investimentos

Objetivo: revisar arquitetura e produto, não tocar no Core de execução.

Negócios:
- validar o caminho Diagnóstico → Proposta → Contrato/Pagamento → Implantação → Operação → ROI/SLA;
- revisar isolamento por tenant, RBAC, LGPD, capacidade/quotas, FinOps e portal do cliente;
- separar demo, sandbox, preview e produção;
- identificar o menor pacote vendável sem prometer automação que ainda não existe.

Investimentos:
- revisar o que já existe em `atlasquant_investment_ecosystem.py` e módulos associados;
- manter caráter educacional/descritivo;
- não emitir recomendação personalizada automática nem ordem de compra/venda;
- priorizar simuladores, renda fixa, dividendos, risco, objetivos e acompanhamento.

Primeira entrega esperada:
- relatório crítico com evidências no código;
- backlog pequeno, ordenado por dependência técnica;
- proposta de 1º pacote funcional de Negócios e 1º pacote funcional de Investimentos;
- nenhuma alteração no Trader.

## Critério de pronto desta fase

A fase só avança para o Trader quando:
- Core recebe missão e chega a execução guardada com receipt;
- continuação/recovery não executa automaticamente tarefa pendente;
- aprovação crítica continua fail-closed;
- Negócios possui fluxo demonstrável ponta a ponta sem alegar produção onde é preview;
- Investimentos possui jornada coerente e educacional;
- Checkpoint Mestre está reconciliado com a `main`;
- testes das três frentes passam;
- nenhuma frente depende de PR antiga aberta sem justificativa explícita.

## Política para PRs antigas

PRs antigas abertas servem como fonte de evidência, não como verdade operacional. A `main` atual tem precedência. Reutilizar uma PR antiga exige provar:
1. que ainda é compatível com a base atual;
2. que não duplica algo já integrado;
3. que seus testes continuam válidos;
4. que sua integração reduz, e não aumenta, o número de caminhos concorrentes.
