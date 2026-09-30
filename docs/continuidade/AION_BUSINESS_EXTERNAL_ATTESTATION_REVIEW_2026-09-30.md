# BUSINESS External Attestation & Formal Review — 2026-09-30

## Continuidade

Este bloco sucede o pacote de certificação BUSINESS V1.

## Entregas

- ponte externa de GitHub Actions por leitor somente-leitura;
- validação dos três workflows obrigatórios no SHA exato;
- candidate attestation com fingerprint ligado a SHA + refs;
- revisão humana formal ligada ao mesmo SHA + fingerprint;
- verificador independente obrigatório também para a revisão humana;
- falha fechada para fonte ausente, malformada, divergente ou falha;
- runtime permanece OFF.

## Mudança importante

`human_review_approved=True` sozinho não é mais suficiente para CERTIFIED.
Sem registro formal e verificador independente, o máximo alcançável após CI
válido é `TESTED`.

## Próximo gate

Depois de CI verde deste bloco, a sequência operacional permanece:

1. estabilizar a pilha de PRs;
2. obter a evidência externa real do SHA candidato;
3. preparar o pacote de revisão humana;
4. revisão humana explícita;
5. somente depois registrar CERTIFIED;
6. runtime continua separado e desligado.
