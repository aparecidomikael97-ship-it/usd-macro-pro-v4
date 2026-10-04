# AION V2.11 — Provenance Trust Lifecycle READINESS (replay / rotation / revocation)

**Tipo:** contrato de *readiness* — NÃO é implementação.
**Base:** `725956c7bd44afcde2ccd04721e70112159f6a19`
**Módulo:** `atlasquant_aion_provenance_trust_lifecycle.py` (novo, isolado)
**Teste:** `test_atlasquant_aion_v211_provenance_trust_lifecycle_redteam.py`

## O que este módulo É
Funções puras que avaliam um envelope de evidência de provenance e reportam
quais dimensões do ciclo de vida de confiança ainda estão ausentes. Estado global
`BLOCKED` até que TODAS as dimensões sejam configuradas E verificadas. Nada aqui
promove automaticamente para `READY`.

## O que este módulo NÃO É (por design)
- Não implementa assinatura real, chave real, KMS/HSM, FIDO/WebAuthn.
- Não cria trust root real. Não ativa nenhuma autoridade.
- Nenhum I/O, nenhuma rede, nenhum armazenamento persistente.
- Nenhuma criação/leitura de secret ou key material.
- Nenhuma execução externa. Nenhuma relação implícita readiness→approval.

## Dimensões fail-closed (todas default `False`)
`replay_policy_configured`, `nonce_registry_available`, `replay_window_configured`,
`signed_timestamp_policy_configured`, `key_rotation_policy_configured`,
`revocation_registry_available`, `compromise_recovery_policy_configured`,
`key_version_policy_configured`, `old_key_acceptance_policy_configured`,
`execution_allowed`.

## Matriz de estados
| Condição | state |
|---|---|
| Qualquer dimensão ausente | BLOCKED |
| Nonce ausente/malformado/duplicado | BLOCKED |
| Timestamp ausente/malformado/futuro | BLOCKED |
| Key version ausente/desconhecida/não-canônica | BLOCKED |
| Key revogada por registry real | BLOCKED |
| Claim de rotation/revocation/compromise sem autoridade/registry/política | BLOCKED |
| Payload fora de ordem / evento duplicado | BLOCKED |
| Objeto hostil / tipo não canônico / oversized | BLOCKED |
| TODAS as dimensões `True` + envelope válido | BLOCKED — flags do envelope são claims não verificadas |

## Matriz de ataques (24 cobertos)
1 replay da mesma evidência · 2 nonce ausente · 3 nonce duplicado ·
4 timestamp ausente/malformado/futuro/stale · 5 key version ausente ·
6 key version desconhecida · 7 revogação por claim não confiável vs registry ·
8 rotation sem autoridade · 9 revocation sem registry real ·
10 compromise recovery sem política · 11 payloads fora de ordem ·
12 duplicação de evento · 13 objetos hostis · 14 tipos não canônicos ·
15 oversized/bounds · 16 determinismo · 17 consistência thread ·
18 nenhum I/O · 19 nenhuma rede · 20 nenhum armazenamento persistente ·
21 nenhuma criação de secret/key material · 22 nenhuma promoção automática BLOCKED→READY ·
23 nenhuma relação implícita readiness↔approval · 24 nenhuma execução externa.

## Prova de zero I/O / zero side effect
- Guard global monkeypatcha `socket.socket` e `subprocess.Popen` durante a avaliação:
  qualquer uso real falha o teste. Resultado: 0 chamadas.
- `reads_persistent_storage=False`, `persistent_store_used=False`,
  `creates_secret_or_key_material=False`, `executes_action=False`,
  `network_called=False` em todos os reports.
- Determinismo byte-for-byte: mesmo input → mesmo JSON (sha256 estável).
- Consistência thread: 8 threads, resultados idênticos.

## Pré-condições futuras para qualquer estado READY
Para que um envelope chegue a `READY`, uma autoridade confiável PRECISA fornecer:
1. Política de replay configurada + janela de replay definida.
2. Registry de nonces disponível (persistente e autoritativo) — hoje ausente.
3. Política de timestamp assinado configurada.
4. Política de rotação de chaves + política de aceitação de chave antiga.
5. Registry de revogação REAL (claims sozinhas não bastam).
6. Política de recuperação por comprometimento configurada.
7. Política de versão de chave + conjunto de versões conhecidas.
8. `execution_allowed=True` somente quando todas as acima + envelope válido.
Até essas existirem, o estado permanece `BLOCKED` — este módulo só declara a lacuna.

### Hardening de autoridade do coordenador
Na reconciliação integrada, flags de readiness presentes no próprio envelope são tratadas apenas como claims do chamador. Sem uma autoridade de readiness confiável e separada, `dimensions_verified=False`, `state=BLOCKED` e `execution_allowed=False` permanecem obrigatórios. Nenhum payload pode auto-promover confiança ou autoridade de execução.

## Limitações
- Staleness de timestamp exige `replay_window_configured`; sem ela o módulo
  declara `REPLAY_WINDOW_NOT_CONFIGURED` em vez de estimar.
- Nonce registry é in-memory por avaliação (sem store persistente) — deduplicação
  vale apenas dentro do lote avaliado; persistência cross-lote é pré-condição futura.
- Multiprocess consistency: NOT PROVEN (thread provado; processo real não exercitado).
- TOCTOU: NOT APPLICABLE (nenhum I/O para racear).

## Contagens exatas
- Testes: **35** · PASS: **35** · FAIL: **0** · SKIP: **0**.
- Ataques cobertos: **24/24**.
