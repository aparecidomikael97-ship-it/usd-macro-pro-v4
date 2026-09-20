# AtlasQuant — Matriz de Aceite da Release

Atualizada para a preparação interna final da release.

| Área | Evidência interna | Estado |
|---|---|---|
| Interface responsiva | UI Smoke desktop/mobile | PRONTO |
| Produção web | Health + Browser Smoke | PRONTO |
| PWA | manifest, service worker, ícones | PRONTO |
| Macro / força / pares / Fed | suíte Quality | PRONTO |
| Scanner H4/H1/M15 | gates + freshness | PRONTO |
| ICT/SMC / Market Map | módulos + testes | PRONTO |
| Safety Core / Decision Integrity | contratos fail-closed | PRONTO |
| Backtest / Walk-Forward / robustez | módulos + evidência | PRONTO |
| Paper Trading | simulação + fricção | PRONTO |
| USER / SALES / ADMIN | RBAC + revogação + auditoria | PRONTO |
| Central de Suporte | catálogo operacional ampliado | PRONTO |
| Guia de Corretoras | informativo, sem conexão real | PRONTO |
| Academy textual | currículo completo | PRONTO |
| Academy mídia | roteiros/storyboards | PREPARAÇÃO PRONTA |
| Assistente de voz | contrato/UX TTS | PREPARAÇÃO PRONTA |
| Billing | checklist + contrato técnico fail-closed | PREPARAÇÃO PRONTA |
| Licenciamento de dados | inventário + checklist | PREPARAÇÃO PRONTA |
| Termos/Privacidade/Riscos | rascunhos internos | PREPARAÇÃO PRONTA |
| Lojas nativas | metadados + checklists | PREPARAÇÃO PRONTA |
| Administrador de produção | secret + primeiro ADMIN configurados manualmente | PENDENTE |
| Revisão jurídica final | evidência externa | PENDENTE |
| Licenças comerciais dos dados | evidência externa | PENDENTE |
| Provedor real de pagamentos | conta/integração externa | PENDENTE |
| Provedor TTS | conta/integração externa | PENDENTE |
| Vídeos renderizados/publicados | mídia externa | PENDENTE |
| Pacotes assinados/lojas | assinatura/submissão externa | PENDENTE |
| Broker real / ordens reais | fora desta release | DESATIVADO |

## Critério de conclusão interna

A preparação interna é considerada completa somente quando o `atlasquant_finalization_audit.finalization_audit()` retorna `internal_release_preparation_complete=True`.

Isso **não** transforma o produto em lançamento público aprovado. O estado público continua bloqueado enquanto dependências externas permanecerem pendentes.

## Critério de segurança

- `real_orders_enabled=False`;
- `broker_execution_enabled=False`;
- `automatic_public_launch=False`;
- revisão humana permanece obrigatória.
