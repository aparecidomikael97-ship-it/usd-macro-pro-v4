# AION BUSINESS Certification Package V1

Schema: `ATLASQUANT_AION_BUSINESS_CERTIFICATION_PACKAGE_V1`

## Finalidade

Este pacote transforma o escopo atual da aba Negócios em evidência verificável
para o AION Business Expert. Ele não ativa runtime e não autoriza contato,
contrato, cobrança, publicação, gasto, merge ou deploy.

A sequência oficial é:

`NOT_READY → READY_FOR_CERTIFICATION_REVIEW → TESTED → CERTIFIED`

Mesmo `CERTIFIED` não significa runtime ligado. Ativação é um gate separado.

## Escopo principal atual

Os cinco motores da aba Negócios são:

1. Automação B2B e Agentes de IA.
2. Micro-SaaS / software próprio com AION.
3. Serviços de IA.
4. Revenue Operations e Captação.
5. Produtos Digitais próprios.

O primeiro pacote gerenciado sugerido permanece **AION Presença & Conversão**
(nome provisório), combinando:

- conteúdo e criativos;
- atendimento inicial / FAQ;
- reativação e follow-up de leads;
- relatório simples de resultados.

O modelo comercial preferido é pacote fechado com implantação + manutenção /
recorrência. Isso não promete faturamento, lucro nem resultado ao cliente.

## Camada operacional do cliente

O pacote considera como estrutura necessária:

- diagnóstico da empresa;
- Radar do Negócio;
- Portal do Cliente;
- onboarding e checklist;
- suporte e SLA;
- Saúde do Cliente;
- Central Financeira e margem;
- LGPD, privacidade e consentimento;
- auditoria e rollback;
- Hub de Integrações;
- Demo/Sandbox;
- capacidade e quotas por cliente;
- treinamento do administrador.

## Legado de marketplace

Dropshipping, afiliados, Shopee, Mercado Livre, TikTok Shop como motor principal
e e-commerce genérico não pertencem ao escopo principal atual.

Código histórico de marketplace pode continuar no repositório por
compatibilidade até uma limpeza segura. A presença desse código não recoloca
marketplace como frente principal e não entra na prova de certificação do
BUSINESS atual.

## Readiness de produto

Antes da revisão de certificação, todos os gates abaixo precisam ser evidenciados
com booleano real `True` e referências:

- oferta/pacote definido;
- escopo de entrega definido;
- Demo/Sandbox aprovado;
- treinamento do administrador pronto;
- contrato do Portal do Cliente definido;
- LGPD/privacidade definida;
- modelo financeiro e margem definidos;
- suporte/SLA definido;
- fronteiras de aprovação humana definidas;
- pacote técnico de prova do especialista pronto.

Qualquer ausência deixa o estado em `NOT_READY`.

## Prova técnica

`business_technical_probe()` verifica de forma local e determinística:

- BUSINESS seleciona `BUSINESS_EXPERT`;
- contexto ambíguo não seleciona silenciosamente;
- evidência de outro domínio não vaza para BUSINESS;
- Core só vê cruzamento quando explícito e não promove verdade;
- roles, tools, scopes e ações não escalam;
- `UNKNOWN`, `STALE`, `CONFLICT` e `INCOMPLETE` não são promovidos;
- trading real, pagamento, publicação, deploy e efeitos externos permanecem
  desligados.

Essa prova sozinha não certifica.

## Atestação de CI

A evidência de testes exige
`ATLASQUANT_AION_BUSINESS_TEST_ATTESTATION_V1`, fornecida pelo chamador e
ligada a:

- especialista BUSINESS;
- versão;
- suíte;
- proveniência;
- evidence_id;
- SHA;
- refs;
- fingerprint exato do corpo da prova.

Um CI verde genérico ou fingerprint divergente não produz `TESTED`. Além disso, a atestação estrutural não verifica a si mesma: um verificador independente e confiável precisa confirmar proveniência, SHA, refs e fingerprint. Sem esse verificador, o estado técnico permanece `CANDIDATE`.

## Revisão humana

Com produto pronto e prova técnica atestada, o estado pode chegar a `TESTED`.
Somente `human_review_approved=True`, booleano exato, permite `CERTIFIED`.

Strings como `"true"`, `"approved"` ou o número `1` não contam.

## Limites

Nenhum estado deste pacote:

- ativa runtime;
- envia mensagem a cliente;
- assina contrato;
- movimenta dinheiro;
- cobra;
- publica;
- compra mídia;
- faz deploy;
- faz merge;
- habilita trading real.
