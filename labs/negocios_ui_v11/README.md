# AtlasQuant Negócios — CRM V1.1, protótipo visual offline

**Status:** LAB / DESIGN / NÃO HOMOLOGADO / HARD NO-GO. Criado em 16/10/2026. **Não integrado ao aplicativo AtlasQuant.**

## Como visualizar

1. Abra `index.html` no navegador do computador ou celular (o arquivo funciona sem serviço HTTP, sem instalação e sem internet).
2. Navegue pelas cinco telas: **Triagem, Oportunidades, Rotina, Propostas, Privacidade**.
3. Experimente exclusivamente dados fictícios. O arquivo não salva alterações em disco nem mantém estado entre sessões.
4. Para o celular, se o navegador não abrir diretamente o HTML do gerenciador de arquivos, abra pelo navegador do computador ou extraia o ZIP em pasta local e abra `index.html`. **Nenhum servidor público foi ativado.**

## Comportamentos exemplificados

- Triagem: sem os quatro critérios, `Simular avanço` recusa mudar o estágio. Com todos marcados, a mudança é **somente visual**.
- Estoque: 2 unidades observadas para 4 solicitadas gera alerta. Igualar quantidades significa apenas `SUFICIENTE NO EXEMPLO`, não reserva/entrega confirmada.
- Finanças: valor previsto R$ 800,00 e recebido no cenário R$ 350,00 gera saldo hipotético de R$ 450,00. Mesmo valor igual ao devido mostra **não verificado externamente**.
- Rotina: três pendências fictícias, revisão local sem follow-up, sem alterações persistidas.
- Propostas: alerta simples para algumas frases de garantia indevida; **não é revisor jurídico ou semântico confiável**. Não há botão de envio habilitado.
- Privacidade: seis verificações educativas; marcar as seis **não** equivale a adequação à LGPD. Nenhuma comunicação sobre incidentes é enviada.

## Segurança e limitações

- Todo conteúdo HTML, CSS e JavaScript reside no único `index.html`; nenhuma biblioteca, fonte, CDN, API, pixel, analytics, form submission ou integração externa.
- CSP embutida: `default-src 'none'`, `connect-src 'none'`, `form-action 'none'`. Navegação local não requer credenciais.
- O conteúdo é estático e executa em memória. Não há `fetch`, `XMLHttpRequest`, `WebSocket`, `localStorage`, `indexedDB`, service worker ou chamadas de fornecedor.
- Marcadores `tenant`, `responsável`, `pedido`, `estoque`, `pagamento` e `LGPD` são apenas ilustrativos, **não autenticados, conciliados ou auditados**.
- Não há isolamento multiempresa, RBAC, backend, versionamento CAS, consentimento verdadeiro, fornecedores, pagamento bancário ou conexão com AION.
- Não duplicar o domínio existente em `atlasquant_aion_business.py` e não misturar com `atlasquant_sales_center.py`; esta UI corresponde ao módulo operacional B2B **ainda proposto**.
- Os 45 testes locais anteriores (`labs/negocios_operational_v11`) **não** foram reexecutados nesta etapa; eles testam contrato, não este navegador.
- Comportamento visual testado com Chromium/Playwright em Linux, cenários de desktop e mobile; não foi feita validação física Android/iOS, Windows ou pipeline CI.
- HARD NO-GO: nenhum merge, deploy, Worker, CRM real, dados reais, mensagens, quotas, compra, cobrança ou publicação.

## Teste opcional (ambiente de desenvolvimento)

Requer Python e Playwright com Chromium instalado. O script injeta o HTML diretamente no navegador em modo offline e verifica navegação, campos, validações, responsividade e ausência de erros ou pedidos de rede:

```bash
python test_ui.py
```

As 34 verificações informadas são grupos/assertivas de smoke test no script, **não** 34 casos unitários independentes nem homologação.

## Rastreabilidade

- Manual Negócios V1.0 (51 páginas) e Complemento V1.1 (13 páginas) permanecem intactos.
- Contrato de regras V1.1: `labs/negocios_operational_v11/ESPECIFICACAO_TECNICA_V1_1.md` na branch de laboratório anterior.
- Negócios #1225; arquitetura #1158; checkpoint #1190; Core HARD NO-GO.
