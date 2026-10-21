# AION P0 A136 — Inventário dos caminhos de gravação do Checkpoint Mestre

21/10/2026. Apenas LAB Draft, baseada na PR #1419. Sem merge, deploy, restauração real, Worker ou serviços pagos.

## Escopo

A134 bloqueou o restore histórico sem witness independente; A135 bloqueou a função geral save_runtime_checkpoint. Porém, outros programas podem escrever diretamente na API GitHub Contents. Esta rodada inspeciona esse risco sem ativar o núcleo.

O scanner AST stdlib-only percorreu 589 arquivos Python de produção e registrou chamadas de persistência e o formato sintático da barreira A135. Não executa módulos nem fornece prova de cobertura total de aliases, imports dinâmicos, código gerado, scripts shell e outros aplicativos.

## Falhas RED-first reproduzidas em simulações

1. A136a: o auxiliar _github_put_bytes_v104 para anexos e GitHubStore de orçamento Twelve Data permitiam especificar caminho de arquivo arbitrário. Onze dos treze casos adversariais falharam antes da correção; dois eram legítimos.
2. A136b: os escritores de CSV das notícias V10.6.1, V10.6.2 e V10.7 e o gh_put_bytes do Autopilot também aceitavam destino dinâmico. Onze dos treze casos adversariais falharam antes do bloqueio.
3. Todas as funções foram extraídas por AST e executadas contra mocks de requests. Nenhum GitHub PUT de produto foi realizado; não foi demonstrada gravação real indevida.

## Correções de escopo

- usd_macro_pro_v4_cloud: somente anexos com formato dados/feedback_anexos/AAAAmmddTHHMMSSZ_8hex.(png|jpg|jpeg|webp).
- twelve_budget_v1108: constructor, load e save exigem BUDGET_PATH exato, mesmo após mudança de atributo.
- currency_news_v1061, v1062 e v107: escritor CSV aceita somente _NEWS_VALIDATION_PATH.
- autopilot_v107: escritor genérico admite apenas caminhos simples relativos sob dados/, sem escapes, codificação, query, fragmentos nem o Checkpoint Mestre.

Testes incluem caminhos válidos para evitar desligar anexos, orçamento, notícias e status de mercado por acidente.

## Outras rotas observadas

O scanner identificou três candidatos contextualizados: a rotina residual PUT do Global Worker já retorna BLOCKED de forma incondicional antes da rede; o PATCH de ativação é específico para desligamento de variável do repositório; e o Flight Recorder grava seu próprio JSONL. Isso foi checado por código, não apenas pelo nome.

O relatório separa ainda dez módulos com mutadores GitHub sem menção direta ao Checkpoint Mestre, para revisão manual. Entre eles: research evidence store, shadow store, market map, master panel, currency news, Autopilot, Twelve Data e cloud UI. Não é prova de que caminhos dinâmicos em outras linguagens ou integrações sejam seguros.

## Critérios

- 13 testes A136a + 13 A136b + 17 testes do inventário AST por sistema, no workflow novo Ubuntu/Windows.
- Reexecutar Quality canônica original (588 módulos, 6.895 testes), Security A74 original (365) e H0 A79 (64), sem dispensa.
- Comparar os 85 identificadores históricos, sem inferir que stack traces são iguais.
- Não declarar witness matriculada, último HEAD monotônico, HUMAN_OWNER comprovado nem efeito externo verificado: essas provas não existem neste pacote.

HARD NO-GO · 0/6 P0 homologados · Worker OFF · ZERO_AUTO_RESEND · sem merge/deploy/restore real.