# AION Core Validation & BUSINESS Certification Readiness V1 — 2026-09-30

## Objetivo

Fechar a próxima camada de validação do Núcleo sem promover runtime, produção ou
especialistas por presença de código.

## Estado de entrada

- base técnica: hardening da PR #394;
- Trader: registrado, runtime desligado, `NOT_CERTIFIED`;
- Business: registrado, runtime desligado, `NOT_CERTIFIED`;
- Investments: registrado, runtime desligado, `NOT_CERTIFIED`;
- SHA servido em produção: ainda não comprovado por este bloco;
- Checkpoint Mestre: não promovido automaticamente para `VALIDADO`;
- merge/deploy/publicação/pagamento/trading real: desligados.

## Entregas

1. `production_identity_gate()`: exige SHA esperado e observado iguais em alvo
   não local, com ambiente conhecido. Não faz chamada de rede.
2. `sandbox_checkpoint_restore_drill()`: restaura uma cópia em memória,
   compara digest e não grava runtime.
3. `checkpoint_master_validation_gate()`: só retorna `VALIDADO` com todos os
   gates explícitos, inclusive aprovação humana booleana exata.
4. `business_certification_readiness()`: prepara o BUSINESS para revisão de
   certificação, sem certificar e sem ativar runtime.
5. `core_validation_summary()`: consolida postura e mantém ações sensíveis
   desligadas.
6. ADR-0011 registra a decisão arquitetural.

## Checklist BUSINESS

O readiness exige evidência explícita de:

- pacote/oferta definido;
- escopo de entrega definido;
- demo/sandbox aprovado;
- treinamento do administrador pronto;
- contrato do portal do cliente definido;
- LGPD/privacidade definida;
- modelo financeiro/margem definido;
- suporte/SLA definido;
- fronteiras de aprovação humana definidas;
- pacote de prova técnica do especialista pronto;
- referências de evidência presentes e não truncadas.

Mesmo com todos os itens acima, o estado técnico continua
`NOT_CERTIFIED`. A etapa seguinte é Specialist Certification Review.

## O que este bloco não faz

- não lê Render nem produção;
- não declara qual SHA está servido em produção;
- não promove o Checkpoint Mestre sem evidência real;
- não restaura checkpoint persistido;
- não ativa BUSINESS;
- não envia contato;
- não assina contrato;
- não cobra;
- não publica;
- não faz deploy;
- não faz merge;
- não opera trading real.

## Próximo fechamento

Depois de CI verde, o próximo passo é coletar a identidade real de produção e
montar o pacote de evidências do BUSINESS para entrar na certificação formal.
