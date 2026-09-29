# AION Core Hardening P1 V1

Data: 2026-09-29
Base: `cursor/aion-core-hardening-p0-v1` @ `332554ab075279f9a90b993c7a8c8f8ca67e00e6`
Issue: #325

## O que este bloco é

Contrato offline para revisão de tarefa e mensagem entre agentes.

- Tarefa simples: Prime.
- Tarefa importante: Prime + Shadow.
- Tarefa crítica: Prime + Shadow + Sentinel.
- Divergência relevante termina em `ESCALATE` ou `BLOCK`.
- Nenhum veredito executa ação, altera Guardian, aprova a si mesmo, forja receipt ou promove `UNKNOWN` para `CONFIRMED`.
- A identidade da mensagem vem do contexto confiável. O payload não escolhe o próprio papel.
- Blast radius usa fatores de impacto. O nome da ação não reduz a classe. `CRITICAL` não é automático.

## O que este bloco não é

Não substitui `guardian_decision`, `proof_of_safety` ou `agent_firewall`.
Não liga worker global, provider pago, tenant real, restore real ou trading.
`protocol_shadow_probe` do global worker permanece um contrato separado de readiness.

## Aceite

- Draft empilhado sobre a branch P0.
- Testes em `test_atlasquant_aion_critical_review.py`.
- O arquivo entra no workflow de qualidade e no security gate.
