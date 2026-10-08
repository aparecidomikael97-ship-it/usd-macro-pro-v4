# AION FinOps — Política de Teto Provisório e Crescimento V1 (08/10/2026)

## Regra oficial do HUMAN_OWNER

O teto **inicial de R$ 200/mês (20.000 centavos de BRL)** é **provisório** e financiado do bolso do proprietário. Não é um teto perpétuo da empresa, nem um orçamento a ser integralmente gasto. Antes de existir receita recorrente e comprovada, priorizar opções gratuitas/locais, não contratar serviços pagos e não aumentar o teto.

A prioridade muda quando o AION Negócios já possui clientes pagantes, os pagamentos foram efetivamente recebidos e há capital de giro suficiente. **Dois meses consecutivos e encerrados** de receitas recebidas são pré-condição para *propor revisão*, não autorização de aumento. Para o exemplo do proprietário, poderá ser sugerido **R$ 200 → R$ 400**, seguido de incrementos posteriores proporcionais à demanda e à capacidade financeira. Não existe promessa de elevar o teto apenas porque o número de clientes cresceu.

## Condições mínimas para proposta de revisão

1. Dois meses contábeis **fechados, consecutivos e mais recentes**, cada um com recebimentos de clientes registrados, reconciliados e efetivamente liquidados; ao menos um cliente recorrente entre ambos.
2. Resultado líquido operacional **positivo em cada mês**, considerando custos integrais e impostos, não só faturamento bruto.
3. Capital de giro disponível identificado e conciliado, preservando compromissos, impostos, reembolsos e reservas de segurança. No protótipo, exige-se pelo menos o **valor de um mês do teto proposto**; isso **não prova suficiência do caixa** nem substitui avaliação financeira.
4. Proposta de aumento em passos controlados; V1 limita a proposta a **no máximo o dobro do teto atual** por avaliação (sem determinar que sempre aumentará).
5. Justificativa de capacidade, custo marginal, ganhos esperados, alternativas gratuitas/locais e gasto real dos provedores, sempre comparando com receita recorrente e margem conservadora.
6. **Autorização expressa e separada do HUMAN_OWNER** para mudar o teto. Alterar teto não autoriza uma assinatura, uma compra ou uma chamada de API: cada ação continua exigindo as aprovações cabíveis.

## Implementação atual: planejamento somente

O módulo `atlasquant_aion_owner_provisional_cap_growth_policy_v1.py` recebe dados declarados em centavos (BRL) e chaves opacas de clientes. Ele verifica formato, meses, entradas duplicadas, receita positiva, custos/impostos reconciliados, resultado positivo, recorrência declarada, capital declarado e proposta incremental. Retorna `ELIGIBLE_FOR_OWNER_REVIEW_ONLY` ou `NOT_ELIGIBLE_FOR_REVIEW`.

**Limitações inegociáveis:**

- Entradas ainda não são autenticadas a partir de banco/contas fiscais/financeiras: a checagem `payments_reconciled=true` é apenas uma *declaração*, não prova de recebimento; chaves de clientes não são prova de identidade.
- Não muda o valor `HARD_CAP_CENTS=20000` do planejamento existente, não grava em banco e não altera saldo real.
- Não está acoplado ao adaptador real `execute_openai_answer`, a fornecedores, ao caixa ou à produção.
- O resultado nunca aprova gastos, assinaturas, alterações de teto, execução externa ou deploy; falhas de validação impedem até a proposta.
- Não guardar nomes, contatos, faturas ou outros dados sensíveis nos resultados de testes e CI; só usar fixtures fictícias.
- Mudança futura do teto de produção deve exigir evidências verificadas, ledger confiável, ato explícito de aprovação do proprietário, rastreabilidade e testes de não regressão. O mecanismo real de bloqueio deverá respeitar o teto **vigente aprovado**, não apenas números declarados.

## Escalonamento e ponto final

Escalar somente quando o negócio puder custear o aumento com recursos próprios e houver necessidade concreta de infraestrutura. Parar de elevar despesas no ponto em que desempenho, capacidade, segurança e disponibilidade atendam à operação, mantendo caixa prudente. Se receita cair, houver custos desconhecidos ou a conciliação falhar, **suspender novos aumentos** e revisar o orçamento com o proprietário.

## Proibições neste bloco

Sem compras, assinatura, uso pago de provedores, alteração de contas, cobrança de clientes, merge, deploy/Render/Worker, acesso ao PC, aumento de teto real ou importação de evidências financeiras privadas. CI usa Python padrão e dados sintéticos.
