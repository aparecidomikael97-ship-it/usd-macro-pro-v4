# AtlasQuant DEV — Pre-release readiness 2026-09-16

Status: **DEV_VALIDATED_PENDING_RUNTIME_ACTIVATION**

Esta evidência descreve a branch DEV. Ela não promove Runtime/Main e não certifica produção.

## Referências verificadas

- DEV candidata: `f3bf849a21f213464e0d6f59e0fbc15c775f93de`
- Quality run: `35111419129`
- Resultado: **650/650 testes OK**
- Compile gate: **verde**
- Runtime observada: `7a2ad3e53055fb1ef6091c39442c4c0f5212c3c1`
- Main observada: `513d0afd85df80640a2c0ed635783f46b4c3df7d`
- Main mudou fora desta etapa; nenhuma alteração foi feita nela.

## Preflight DEV

O módulo `atlasquant_dev_preflight.py` executa uma auditoria offline/read-only antes de qualquer
ativação Runtime.

A suíte validou que o preflight atual retorna `DEV_PREFLIGHT_OK` e mantém:

- arquivos essenciais dos cinco operacionais e do Backtest presentes;
- Backtest avançado integrado ao app DEV;
- painel de Backtest sem chamadas diretas a provedores;
- política de branch aceitando escrita operacional somente em branch dedicada e rejeitando main/DEV;
- workflow do Autopilot apontando para `atlasquant-runtime`;
- histórico local de pesquisa isolado de `dados/` e ignorado pelo Git;
- paridade estática TradingView ↔ Python sem drift detectado.

## O que este selo NÃO significa

Ainda permanecem pendentes para ativação real:

1. autorização específica para promover/ativar Runtime;
2. health check pós-deploy;
3. confirmação do destino real de leitura/escrita após ativação;
4. validação das credenciais/configurações efetivas do ambiente;
5. compilação final das Pine Strategies dentro do TradingView;
6. verificação de UI em ambiente Runtime, não apenas contratos/CI da DEV.

O preflight não chama provedores live, não altera Gate, não muda pesos e não executa promoção.

## Estado de promoção

- `manual_runtime_activation_required = true`
- `runtime_health_check_pending = true`
- `runtime_promotion_performed = false`

A DEV está validada para **revisão de ativação Runtime**, não para promoção automática.
