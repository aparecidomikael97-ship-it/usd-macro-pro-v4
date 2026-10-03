# AION Unified Core V2.1 — hardening e adapters

## Base

Esta etapa é stacked sobre a Draft PR #550, branch `integration/aion-unified-core-v2-20261003`.

Ela não toca na PR #551 da interface e não liga o Chat AION ao app principal.

## Objetivos implementados nesta etapa

### Browser reduced-motion

O teste do Chat verificava `transitionDuration` com uma avaliação crua imediatamente após abrir uma conversa. O fluxo `open()` chama `list()`, que reconstrói os botões `.conversation` via `replaceChildren()`. Isso permite que uma avaliação pontual alcance um nó durante a substituição do DOM.

O contrato foi mantido, mas agora usa assertions Playwright com retry sobre o locator re-resolvido:

- `matchMedia('(prefers-reduced-motion: reduce)') == true`;
- elemento anexado;
- `transition-duration: 0s`;
- `transform: none`.

O gate específico executa o browser cinco vezes em sequência para expor flakiness.

### Chat -> Checkpoint Mestre

`atlasquant_aion_chat_checkpoint_adapter.py` implementa o contrato `CheckpointMasterAdapter` sobre o `CheckpointCoreStore` existente.

Princípios:

- scope owner/tenant/workspace validado;
- export canônico com digest;
- nenhuma gravação automática;
- receipt de aprovação obrigatório;
- receipt vinculado ao digest do payload;
- replay para payload diferente é rejeitado;
- repetição idêntica é idempotente;
- o conteúdo da conversa não é promovido para fato/decisão;
- o Core recebe somente uma âncora `CURRENT_STATE` com digest, conversa e sequência;
- a âncora usa `Origin.UNKNOWN`, portanto não se disfarça de memória aprovada;
- o bundle produzido continua no fluxo explícito do Checkpoint Mestre.

### Chat -> Biblioteca AION

`atlasquant_aion_chat_library_adapter.py` reutiliza:

- validação de anexos do Chat;
- `stage_pdf_document`;
- `ingest_document`;
- `search_library_index`.

Princípios:

- anexo começa em quarentena;
- hash, tamanho, nome e MIME real devem coincidir com os metadados;
- análise requer ação explícita;
- PDF usa o pipeline PDF existente;
- TXT pode ser staged na Library Foundation;
- outros MIME permanecem `REVIEW_REQUIRED`;
- nenhuma revisão administrativa automática;
- nenhum index automático;
- nenhum provider;
- nenhuma promoção para memória;
- retrieval aceita somente índice já revisado instalado para o mesmo tenant/workspace.

## Segurança / isolamento

Testes novos cobrem:

- cross-tenant no checkpoint;
- payload de checkpoint alterado após aprovação;
- receipt ausente;
- replay do mesmo receipt para payload diferente;
- idempotência;
- digest/tamanho/MIME de anexo;
- path traversal;
- quarentena sem análise explícita;
- retrieval isolado por tenant/workspace.

## CI stacked

Durante esta Draft PR, os workflows relevantes aceitam também a branch-base da #550 para validar o delta V2.1 antes da integração:

- AION Unified Core;
- AION Core Security Gate;
- Quality tests;
- AtlasQuant Release Readiness.

Os testes de browser do Chat rodam cinco vezes no gate específico.

## Limites desta etapa

Ainda não implementado nesta revisão:

- journal genérico do request unificado;
- bridge para durable/recovery;
- matriz aprofundada de autoridade dos oito papéis;
- truth/knowledge state adapter;
- provider runtime real;
- ligação do Chat à UI principal.

Nada nesta etapa executa ação externa, provider real, trade, merge ou deploy.
