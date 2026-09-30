# AION BUSINESS Onboarding + Implementation Demo V1

Schema: `ATLASQUANT_AION_BUSINESS_ONBOARDING_IMPLEMENTATION_DEMO_V1`

## Objetivo

Ensinar como um cliente aprovado sai da proposta para a implantação sem pular
escopo, segurança, sandbox ou validação.

## Fases

1. Escopo
2. Dados & Acessos
3. Integrações
4. Sandbox
5. Validação
6. Entrega Assistida

## Escopo

Antes de qualquer integração, ficam definidos:

- problema;
- pacote;
- objetivo;
- responsável;
- métricas;
- exclusões.

## Dados e acessos

A regra é **least privilege**.

O demo registra apenas quais categorias de acesso poderiam ser necessárias.
Ele não solicita nem armazena senha, token, chave ou credencial real.

## Integrações

WhatsApp Business, e-mail, calendário, CRM, formulários, pagamentos, redes
sociais e analytics aparecem somente como categorias de planejamento.

Nenhuma conexão externa é realizada nesta versão.

## Sandbox

Toda implantação começa em sandbox. O objetivo é validar fluxo, dados, permissões
e comportamento antes de qualquer possível go-live.

## Validação

Checklist obrigatório:

- escopo;
- dados mínimos;
- permissões;
- integrações em sandbox;
- fluxos;
- rollback;
- suporte/SLA;
- métricas/fonte de verdade.

## Entrega assistida

Concluir o demo não liga produção.

O máximo que o fluxo pode gerar é um
`LIVE_REVIEW_REQUIRED` para futura revisão humana específica.

## Segurança

- runtime OFF;
- nenhuma credencial real;
- nenhuma conexão externa;
- nenhum contato;
- nenhum pagamento;
- nenhuma publicação;
- nenhum deploy.
