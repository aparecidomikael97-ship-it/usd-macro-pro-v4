# BUSINESS Specialist Certification Package V1 — 2026-09-30

## Missão

Preparar o AION Business Expert para certificação formal sem ativar runtime.

## Base

- PR #394: hardening do Núcleo;
- PR #395: validation gates e BUSINESS certification readiness;
- este bloco: pacote verificável de produto + prova técnica + CI + revisão humana.

## Resultado esperado

O BUSINESS pode evoluir:

`NOT_READY → READY_FOR_CERTIFICATION_REVIEW → TESTED → CERTIFIED`

A passagem para `TESTED` exige CI atestado e fingerprint exato.
A passagem para `CERTIFIED` exige revisão humana booleana exata.

Nenhuma dessas transições ativa runtime.

## Escopo de Negócios consolidado

Cinco motores:

- Automação B2B / Agentes de IA;
- Micro-SaaS AION;
- Serviços de IA;
- Revenue Ops / Captação;
- Produtos Digitais próprios.

Oferta de entrada: AION Presença & Conversão, com conteúdo, atendimento inicial,
follow-up e relatório. Modelo preferido: implantação + recorrência.

Camada de entrega: diagnóstico, Radar do Negócio, Portal do Cliente, onboarding,
SLA, Saúde do Cliente, financeiro/margem, LGPD, auditoria, integrações,
Demo/Sandbox, quotas e treinamento do administrador.

## Legado

Marketplace e e-commerce histórico permanecem somente como compatibilidade até
limpeza segura. Não fazem parte da certificação atual do Business Expert.

## Bloqueios preservados

- runtime BUSINESS: OFF;
- envio de contato: OFF;
- assinatura de contrato: OFF;
- pagamento/cobrança: OFF;
- publicação: OFF;
- gasto: OFF;
- merge/deploy automático: OFF;
- trading real: OFF.

## Próxima evidência

Depois de CI verde deste bloco, registrar a atestação real do HEAD e levar o
BUSINESS até `TESTED`. A promoção para `CERTIFIED` continua aguardando revisão
humana explícita e não liga runtime.


## CI e atestação

A execução de CI desta branch valida o contrato e os testes, mas o resultado só
vira atestação de certificação quando SHA, suíte, refs e fingerprint forem
registrados de forma vinculada. CI verde genérico não certifica o BUSINESS.
