# AION FinOps — Live Cost Ledger V1

## Objetivo

Transformar custos externos verificados em um ledger íntegro para orçamento e
unit economics do Business.

## Fontes de custo

- AI Provider
- Hosting
- Market Data
- Integration
- Voice
- Video
- Messaging
- Storage
- Observability
- Payment Fees
- Other

## Regra de origem

Custos só entram quando a fonte está atestada em leitura.

O módulo não faz login no provider e não recebe segredo.

## Custo direto x compartilhado

### Direto
Precisa de `tenant_id`.

### Compartilhado
Não pode nomear tenant. A distribuição posterior usa percentual administrativo
explícito e fica registrada como estimativa de alocação.

## Ledger

Modelo: **append-only hash-chain**.

Cada entrada contém:
- posição;
- digest anterior;
- dados canônicos do custo;
- entry digest.

O conjunto também contém:
- snapshot digest;
- tail digest;
- ledger digest.

Se qualquer custo histórico for alterado, a verificação falha.

## Budget Governor

O ledger verificado pode ser agregado por categoria e enviado ao Budget Governor,
mantendo o teto atual de R$200/mês.

## Custo por tenant

O AION pode mostrar:
- custos diretos;
- pool de custos compartilhados;
- percentual administrativo de alocação;
- custo total estimado do tenant.

Isso não altera preço automaticamente.

## Persistência

A versão atual prepara `FINOPS_LEDGER_READY_FOR_PERSISTENCE_REVIEW`.

Ela não grava o ledger em storage. Persistência real precisa de gate separado.

## Autoridade

Sem:
- pagamentos;
- assinatura de provider;
- mudança de plano;
- cobrança;
- transferência;
- preço automático.
