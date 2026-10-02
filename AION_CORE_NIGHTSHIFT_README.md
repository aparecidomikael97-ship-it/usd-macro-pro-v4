# AION Core — Night Shift (trabalho local)

Base original: bdad9b49a58e754c4fe8c1c1c5429f7b44974aff
Sessoes: retomada-01 .. retomada-04 (2026-10-01)

## Conteudo

Pacote `aion_core/` (fundacao AION Core, pure/offline, sem rede, sem provider):

- `domain_registry.py` — ONDA A: 9 dominios oficiais com politicas de dados,
  memoria, compartilhamento, offline/online e risco. Fail-closed.
- `memory_architecture.py` — ONDA B: 7 camadas (WORKING/EPISODIC/SEMANTIC/
  PROCEDURAL/TENANT/ADMIN/DOMAIN), 7 estados, state machine explicita,
  isolamento tenant/domínio, promocao so por transicao explicita.
- `provenance.py` — ONDA C: origem, versao, autoridade, validacao, tenant e
  dominio de todo conhecimento; digest deterministico sobre campos materiais;
  lineage derivada.
- `trust_engine.py` — ONDA D: avaliacao de qualidade de evidencia (nao e
  verdade absoluta). Duplicatas da mesma origem contam como UMA origem;
  100 copias nao vencem 1 fonte primaria independente (teste adversarial).
- `evidence_pack.py` — ONDA E: pacote transportavel de evidencias entre
  retrieval -> especialista -> validacao. Nunca concede permissao; conteudo
  documental e DADO, nunca instrucao privilegiada; sem segredos.

## Testes (92 passed / 0 failed)

- test_aion_core_domain_registry.py (14)
- test_aion_core_memory_architecture.py (19)
- test_aion_core_provenance.py (18)
- test_aion_core_trust_engine.py (17)
- test_aion_core_evidence_pack.py (15)
- test_aion_core_security_audit.py (9)

Rodar: python -m pytest -q test_aion_core_*.py

## Estado

- Sem push, merge, deploy ou producao.
- Ledger protegido (#472) byte-for-byte inalterado (verificado por SHA-256).
- Proximas ondas: LIBRARY_FOUNDATION em diante (plano de 80 ondas).
- Checkpoint: AION_CORE_NIGHTSHIFT_CHECKPOINT.json
