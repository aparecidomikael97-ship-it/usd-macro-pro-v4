# ADR-0020 — Implantação do AION Business deve ser sandbox-first e least-privilege

- Título: Implantação do AION Business deve ser sandbox-first e least-privilege
- Data: 2026-09-30
- Status: ACCEPTED

## Contexto

O AION Business já possui diagnóstico, proposta e Portal Executivo em modo demo.
Era necessário fechar o caminho de entrega ao cliente.

## Problema

Pular diretamente da proposta para integrações reais aumentaria risco de acesso
excessivo, credenciais expostas, fluxos incorretos e ativação prematura.

## Decisão

Toda futura implantação segue:

Escopo → Dados & Acessos → Integrações → Sandbox → Validação → Entrega Assistida.

Acesso segue least privilege e credenciais reais não pertencem ao demo.

O fim do demo pode apenas produzir um pedido separado de revisão de go-live.
Não existe ativação automática de runtime.

## Consequências

O processo de implantação fica ensinável, auditável e compatível com clientes
futuros sem abrir integrações antes da hora.

## Segurança

Nenhuma fase deste ADR autoriza runtime, contato, pagamento, publicação, gasto
ou deploy. Credenciais reais são explicitamente excluídas do demo.

## Compatibilidade

ADR-0019 define o Portal do Cliente. Este ADR define o processo posterior à
proposta e anterior a qualquer eventual operação real.

## Rollback

O módulo é apenas planejamento/session state. Sua remoção não exige compensação
externa.

## Supersedes

Nenhum.

## Superseded by

Nenhum.
