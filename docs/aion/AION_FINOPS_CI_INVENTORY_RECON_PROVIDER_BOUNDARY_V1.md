# AION FinOps — Inventário, conferência de faturas declaradas e barreira de provedor V1

**Data:** 08/10/2026  
**Base:** PR #1071 — reserva atômica SQLite efêmera; PR #1070 — teto pessoal de R$ 200  
**Status:** Draft, apenas CI; não conectar contas ou fazer compras.

## Objetivo

Antes de integrar o controle de custos do AION a qualquer provedor pago,
existem três perguntas diferentes:

1. Quais são as **despesas recorrentes declaradas** e quem é o prestador?
2. Há uma **cobrança informada** para cada obrigação e os valores coincidem?
3. Existe uma **reserva de orçamento identificável** para a solicitação antes
   de tentar executar uma ação paga?

Este módulo responde às três perguntas somente com dados sintéticos de teste.
**Não consulta extrato, cartão, plataforma de hospedagem, OpenAI, API de
pagamentos, faturas reais ou credenciais.** Um campo denominado
`USER_REVIEWED_DOCUMENT` não equivale a autenticação independente.

## A. Inventário declarado

`build_declared_owner_inventory` recebe obrigações com ID, prestador,
escopo de proprietário/mês, categoria, periodicidade, estado, custo em
centavos BRL e indicação de procedência declarada.

- O conjunto de prestadores esperados é fornecido pelo chamador; o módulo
  bloqueia prestadores desconhecidos e ausentes **nesse conjunto**.
- Custos desconhecidos não são zero; item gratuito exige declaração de
  `FREE` e valor zero.
- Obrigações mensais contam integralmente. Obrigações anuais são
  provisionadas mensalmente com arredondamento para cima: `ceil(valor/12)`.
- Impede duplicação de identificadores, datas/escopos incompatíveis,
  falsas declarações de autorização e orçamento declarado superior a
  R$ 200/mês.

**Ressalva importante:** provisionar anuidade por 12 meses ajuda na
economia anual, mas NÃO garante fluxo de caixa de um único mês. Uma
anuidade cobrada à vista pode exigir dinheiro acima de R$ 200 naquele
mês. É obrigatório levantar a **data real de renovação** e planejar
reserva de caixa separada antes de contratar/renovar.

O inventário também não descobre automaticamente prestadores omitidos:
a lista de provedores é fornecida pelo chamador e não autenticada.

## B. Conciliação de cobranças *alegadas*

`reconcile_claimed_owner_invoices` associa identificador da fatura,
obrigação, prestador, proprietário, mês e valor declarado. Requer uma
cobrança alegada por obrigação, valores exatos, nenhum prestador trocado
e nenhuma obrigação ausente. Todos os dados são fictícios.

A exigência de correspondência exata é uma política conservadora de
teste. Descontos, créditos, impostos, variação cambial, pagamento anual
e cobranças por uso exigirão reconciliação mais detalhada e controle
específico de desvios na versão real. Não liberar orçamento com base em
alegação de desconto/reembolso.

**Estado máximo:** `CI_CLAIMED_INVOICES_EXACT_MATCH_UNTRUSTED`.
Mesmo que os valores coincidam, não foi provado que a fatura é verdadeira,
que foi paga ou que todos os contratos foram listados.

## C. Fronteira de execução — simulação SEM chamar provedor

`dry_run_ci_provider_execution_boundary` cruza o inventário e a
conciliação declarada com a reserva existente na SQLite efêmera da #1071.
Exige reserva real no banco *de testes*, status ainda `RESERVED`,
mesmo ID, proprietário, mês, prestador, tenant e preço, e baseline
compatível com as despesas inventariadas.

O código lê a reserva pelo backend de teste, em vez de confiar apenas
na resposta textual anteriormente retornada pelo sistema. A própria
#1071 controla o caminho permitido no `RUNNER_TEMP` do GitHub e
reverifica a soma de todas as reservas.

Mesmo quando tudo bate, o estado máximo é apenas
`CI_PROVIDER_BOUNDARY_DRY_RUN_UNTRUSTED`, e todas as bandeiras de
`paid_provider_call_authorized`, `paid_call_executed`,
`owner_approval_consumed` e `real_financial_enforcement_deployed`
continuam **falsas**.

Uma SQLite de runner de CI não deve ser confundida com reserva bancária,
fatura real ou autorização do proprietário. Variáveis de CI podem ser
falsificadas e não são um limite de segurança de produção.

## Testes adversariais

Executar casos em GitHub Actions Windows e Ubuntu: custos ausentes,
prestadores omitidos, anuidades, valores divergentes, falsa gratuidade,
faturas duplicadas, erros de escopo, adulteração de hash, troca de
prestador/tenant, reserva inexistente, banco adulterado, reserva já
liquidada e campos inventados de aprovação financeira.

Nenhuma solicitação realiza tráfego de API de um provedor pago, compra,
cobrança, assinatura ou envio de credenciais.

## Ainda falta para cumprir o objetivo do proprietário

- Inventário **real** e completo, com renovações, custos anuais, débito
  efetivo, taxas/impostos e assinatura de cada serviço.
- Fontes de faturamento confiáveis e conciliadas com cobranças bancárias;
  o usuário precisará autorizar conectar esses dados.
- Fila/limite real antes de cada chamada paga do AION, com orçamento
  de clientes, idempotência junto ao provedor e proteção para retries.
- Autorização forte de gasto, limitada por valor, escopo, fornecedor,
  período, nonce e revogação; nenhuma assinatura implícita.
- Capacidade real do computador medida em RAM, VRAM, CPU, armazenamento
  e latência para testar modelos locais sem custo recorrente de API.
- Controle da cobrança de serviços externos: **um limite dentro do AION
  não impede que uma assinatura de hospedagem/API cobre fora dele**.
  A proteção real exige também configurar hard limits nos próprios
  provedores, quando existirem, e desativar renovação/compromissos
  com aprovação explícita do proprietário.
- Revisão de margem por cliente, incluindo impostos, suporte, falhas
  e custos fixos proporcionais, antes de escalar o AION Negócios.

**Teto-meta inicial:** R$ 200 mensais de despesas operacionais recorrentes
pagas pelo proprietário, excluindo hardware, internet e energia. Não
promete custo zero e não garante capacidade para centenas de empresas
24h por dia.

**Sem merge, deploy, Worker, compra, nova assinatura, leitura de faturas
reais ou acesso ao computador do proprietário nesta PR.**
