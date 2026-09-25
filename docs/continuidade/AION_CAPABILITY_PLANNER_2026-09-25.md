# AION — Capability Registry + Agentic Mission Planner

Data: 2026-09-25

## Objetivo

Adicionar ao AION uma camada explícita de planejamento agentivo sem permitir
execução silenciosa.

O planejador responde, antes de qualquer ação:

- qual capacidade seria necessária;
- se ela está disponível localmente;
- se falta evidência fresca;
- se existe dependência externa;
- se uma feature flag está desligada;
- se é necessária aprovação explícita;
- se a ação permanece bloqueada por desenho.

## Estados

- AVAILABLE_LOCAL
- EVIDENCE_REQUIRED
- EXTERNAL_DEPENDENCY
- FEATURE_DISABLED
- APPROVAL_REQUIRED
- BLOCKED

## Regra de segurança

O plano nunca é autorização.

O módulo não chama web, modelos, conectores, GitHub, Render, redes sociais,
marketplaces, pagamentos ou corretoras. Ele apenas cria o mapa da missão e
consulta o Guardian em modo sem aprovação.

Trading real permanece BLOCKED mesmo se uma flag/conector forem apresentados
como ativos.

## Exemplos

"Analise o Forex agora" pode exigir:
1. Conselho Cognitivo local;
2. snapshot de mercado;
3. se mercado ao vivo não estiver confirmado, EVIDENCE_REQUIRED.

"Corrija a interface e faça deploy":
1. memória/repositório;
2. planejamento local de código;
3. testes;
4. produção fica FEATURE_DISABLED/APPROVAL_REQUIRED/EXTERNAL_DEPENDENCY conforme
   o estado real; nunca é executada pelo planner.

"Publique no Instagram":
1. trabalho de Studio pode ser preparado;
2. publicação externa depende de conexão, flag e aprovação.

## Relação com o Guardian

O Capability Planner não substitui o Guardian. Ele o consulta para produzir uma
prévia segura. A aprovação real continua no ponto da ação.

## Relação com o Cognitive Engine

- Cognitive Orchestrator decide quais especialistas/evidências são necessários.
- Capability Planner decide quais capacidades e gates operacionais seriam
  necessários.
- Critic verifica as afirmações.
- Wisdom Journal fornece conhecimento revisável.
- Guardian protege ações.
