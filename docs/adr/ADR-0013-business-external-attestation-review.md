# ADR-0013 — Evidência externa de CI e revisão humana formal do AION Business Expert

- Título: Evidência externa de CI e revisão humana formal do AION Business Expert
- Data: 2026-09-30
- Status: ACCEPTED

## Contexto

O pacote V1 do Business Expert já separa readiness, prova técnica, CI e revisão
humana, e mantém runtime desligado. Ainda existiam dois pontos em que o chamador
poderia apresentar uma declaração estruturalmente válida: o resultado de CI e o
booleano de revisão humana.

## Problema

Uma certificação formal precisa ser ligada a evidência independente. O payload
não pode verificar a própria proveniência, e `True` isolado não deve representar
uma revisão humana auditável.

## Decisão

A rota oficial de certificação BUSINESS passa a exigir duas verificações
independentes:

1. **CI externo**: leitor somente-leitura consulta GitHub Actions para o SHA exato
   e confirma os workflows obrigatórios por path, conclusão e repositório.
2. **Revisão humana formal**: registro estruturado ligado ao mesmo SHA e
   fingerprint precisa ser confirmado por verificador independente.

A revisão tem escopo estrito `CERTIFICATION_ONLY` e deve declarar
`runtime_activation_approved=false`.

## Workflows obrigatórios

- `.github/workflows/quality-tests.yml`
- `.github/workflows/aion-core-security-gate.yml`
- `.github/workflows/atlasquant-release-readiness.yml`

O último run considerado para cada path deve estar concluído com sucesso no SHA
exato.

## Consequências

Um payload autodeclarado deixa de ser suficiente para TESTED. Um booleano
autodeclarado deixa de ser suficiente para CERTIFIED. Falha ou indisponibilidade
de qualquer verificador fecha o gate.

## Segurança

Nenhuma evidência, revisão ou certificação ativa runtime ou concede contato,
contrato, dinheiro, publicação, gasto, merge, deploy ou trading real.

## Compatibilidade

O pacote da ADR-0012 continua como camada de escopo/readiness. Este ADR endurece
a proveniência dos gates externos e humanos sem alterar o escopo comercial.

## Rollback

A retirada deste mecanismo exige novo ADR e não pode converter payloads antigos
em prova confiável automaticamente.

## Supersedes

Nenhum.

## Superseded by

Nenhum.
