# AION Core Model Registry V1

Data: 2026-09-29
Base: `cursor/aion-core-action-receipt-v1` @ `2e9c01fe8c65956dcc5f3a58d16c3bc801b27a29`

`atlasquant_aion_model_registry.py` é um portão de promoção offline. A rota continua em `route_intelligence`. A evidência continua em `evaluate_run`. Este módulo não chama provedor, não cadastra chave e não gasta orçamento.

Estados: CANDIDATE, BENCHMARKED, CANARY_READY, APPROVED, DEGRADED, REJECTED, ROLLBACK_REQUIRED.

Sem suíte e run do laboratório, o estado permanece CANDIDATE. Uma string em `benchmark_refs` não é benchmark. O estado gravado no payload é ignorado. O laboratório é recalculado; um `HUMAN_REVIEW_CANDIDATE` forjado não passa.

APPROVED exige, ao mesmo tempo: resultado `HUMAN_REVIEW_CANDIDATE`, `canary_passed is True`, `review_approved is True`, papel confiável ADMIN, `security_failure is False`, provedor disponível com `is True`, e custo zero ou `budget_decision` permitido. Custo booleano não entra no router, porque `float(True)` seria 1.0. `allow_paid` e `request_approved` só valem se forem `True`.

Falha de segurança em modelo que já estava APPROVED pede ROLLBACK_REQUIRED somente com alvo de rollback diferente do próprio modelo. Sem alvo, a decisão fica REJECTED.

Provedor indisponível devolve DEGRADED e a faixa `LOCAL_DETERMINISTIC` já calculada pelo router. Isso não liga um cliente externo.

O fingerprint é SHA-256 canônico. Não é assinatura. `executes_provider_call`, `executes_billing` e `activates_paid_api` ficam falsos.
