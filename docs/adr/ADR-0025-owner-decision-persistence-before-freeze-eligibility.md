# ADR-0025 — Decision record precisa ser persistido antes da elegibilidade de Core Freeze

- Título: Decision record precisa ser persistido antes da elegibilidade de Core Freeze
- Data: 2026-10-04
- Status: ACCEPTED

## Contexto

V2.25 verifica criptograficamente APPROVE/DENY, mas deliberadamente mantém
`owner_decision_recorded=false` até que o record seja persistido.

## Problema

Uma assinatura válida não prova que o sistema durável guardou a decisão.

Sem uma camada separada seria possível:

- confundir decisão verificada com decisão registrada;
- abrir freeze com um objeto apenas em memória;
- usar conteúdo igual sem provar autoria da escrita;
- escrever sobre runtime que mudou depois da decisão;
- aceitar receipt de repo/branch/path errado;
- aceitar nonce pertencente a outro request de decisão.

## Alternativas rejeitadas

- `owner_decision_recorded=true` imediatamente após assinatura;
- freeze elegível antes de persistência;
- confiar em objeto `verified_decision` do caller;
- confiar somente no conteúdo final sem write attribution;
- persistência sem CAS;
- receipt sem SHA/read-after-write;
- nonce sem binding ao digest exato V2.25.

## Decisão

V2.26 reconstrói e reverifica a decisão V2.25 usando:

- request;
- assinatura;
- trust root;
- nonce durável do request exato;
- evidência V2.24/V2.23.

Depois prepara um record de runtime em memória.

Persistência só é atestada quando o runtime oficial confirma:

- destino oficial;
- CAS sobre o SHA anterior;
- novo SHA;
- digest exato;
- record exato;
- receipt íntegro;
- write attribution;
- read-after-write.

## APPROVE

Somente attestation positiva de APPROVE permite:

`core_freeze_ceremony_eligible=true`

Ela não permite:

- executar freeze;
- merge;
- deploy;
- armar Worker;
- ação externa.

## DENY

Attestation positiva de DENY torna a negativa durável e mantém:

`core_freeze_ceremony_eligible=false`

## Segurança

V2.26 é read-only em relação ao runtime.

Ela não chama save, não chama rede, não executa freeze e não modifica feature flags.

## Compatibilidade

Compõe ADR-0002, ADR-0007, ADR-0012, ADR-0019, ADR-0020, ADR-0021, ADR-0022,
ADR-0023 e ADR-0024.

## PR/commit relacionado

Branch `integration/aion-v226-owner-decision-persistence-attestation-20261004`.

## Supersedes

Nenhum.

## Superseded by

Nenhum.
