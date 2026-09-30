# AION BUSINESS — Equipe & Acessos · Autorização & Ledger do Lifecycle V1

## Objetivo

Separar três coisas que não podem ser confundidas:

1. plano de teste;
2. decisão humana explícita;
3. evidência do que realmente aconteceu em cada etapa.

## Autorização

O contrato
atlasquant_aion_business_team_access_sandbox_lifecycle_authorization.py
valida uma decisão formal vinculada ao plan digest e ao baseline digest.

O sistema não cria um registro automaticamente e não transforma mensagens
genéricas em autorização.

## Ledger

O contrato
atlasquant_aion_business_team_access_sandbox_lifecycle_evidence_ledger.py
mantém a sequência lógica das dez etapas por recibos hash-chain.

Cada recibo contém apenas:
- digest da evidência sanitizada;
- step id e ordem;
- timestamp;
- digest do registro de autorização;
- digest do recibo anterior;
- indicação factual se aquela etapa observou uma mutação sandbox.

## Estado máximo

Uma cadeia completa chega somente a:

SANDBOX_LIFECYCLE_EVIDENCE_COMPLETE_REVIEW_REQUIRED

Isso não promove nada para produção.

## Fluxo

baseline real
→ plano
→ autorização explícita
→ step 1 + receipt
→ revisão
→ step 2 + receipt
→ ...
→ step 10 + receipt
→ revisão final do lifecycle
→ eventual decisão futura separada.

## Fail-closed

Qualquer drift, salto de etapa, hash inválido, duplicação ou binding divergente
bloqueia a cadeia e interrompe o avanço.
