# AION Core Memory Quarantine V1

Data: 2026-09-29
Base: `cursor/aion-core-hardening-p2-v1` @ `ddff7312b04925c8d5b909dedca35fcb12cc159d`

## O que este bloco faz

`atlasquant_aion_memory_quarantine.py` é a porta de admissão. A memória permanente continua em `atlasquant_aion_memory_layers.py`.

- Conteúdo novo não entra direto na camada permanente.
- Tenant e workspace vêm do contexto confiável.
- Web, documento, e-mail, tool output e IA externa ficam `QUARANTINED`.
- Livro e opinião não viram fato automático.
- Fonte inválida fica `REVIEW_REQUIRED`.
- Conteúdo vencido ou futuro fica `STALE`.
- Mesmo texto com outra procedência ou versão fica `CONFLICT`, sem escolher um vencedor.
- Segredo é rejeitado e o valor não é ecoado.
- Frases que pedem Guardian, ADMIN, Constitution, credencial ou trading real não ganham autoridade quando relidas.
- Promoção exige review `True` no contexto confiável e verifier de evidência. A entrada gravada permanece `truth_state=UNKNOWN`.

## O que continua fora

`atlasquant_aion_memory.py` e o checkpoint persistente ainda não chamam este gate.
Não houve escrita de produção.
