# ADR-0058 — Custos reais entram por fonte atestada e ledger FinOps usa hash-chain append-only

Título: Custos reais entram por fonte atestada e ledger FinOps usa hash-chain append-only  
Data: 2026-09-30  
Status: ACCEPTED

## Contexto

Preço sustentável, margem por cliente e limite de R$200 dependem de custos reais
de IA, hosting, dados, integrações, voz, vídeo, mensagens e demais providers.

## Problema

Sem origem verificável e histórico íntegro, um custo pode ser alterado, duplicado
ou atribuído ao tenant errado. Ao mesmo tempo, persistir ou pagar automaticamente
a partir do ledger aumentaria autoridade desnecessária.

## Alternativas consideradas

1. Custos digitados manualmente sem prova.
2. Provider direto alterando o ledger.
3. Snapshot read-only atestado + ledger hash-chained append-only.

## Decisão

Adotar a alternativa 3.

Cada provider precisa de atestação:
- provider_ref;
- connection_ref;
- autenticação verificada externamente;
- escopo read-only;
- write scope ausente;
- credencial ausente;
- observed_at.

Cada custo precisa de:
- entry_id único;
- provider/source refs;
- categoria;
- tenant_id para custo direto ou shared_cost sem tenant;
- amount_brl;
- período;
- observed_at.

O ledger:
- ordena entradas deterministicamente;
- encadeia cada entrada ao digest anterior;
- possui tail digest;
- possui ledger digest;
- detecta alteração retroativa.

## Consequências

O AION pode:
- calcular custo mensal real observado;
- alimentar Budget Governor;
- estimar custo por tenant;
- revisar margem e capacidade.

Não pode:
- persistir ledger automaticamente;
- pagar provider;
- alterar assinatura;
- mover dinheiro;
- alterar preço.

## Segurança

Persistência física, connectors reais e pagamentos permanecem gates separados.

## Compatibilidade

Complementa ADR-0050 FinOps/Tesouraria e a camada de pricing B2B.

## Rollback/migração

Pure/read-only. Remoção não altera faturas, saldo ou provider.

## PR/commit relacionado

Draft PR AION FinOps Live Cost Ledger V1.

## Supersedes

Nenhum.

## Superseded by

Nenhum.
