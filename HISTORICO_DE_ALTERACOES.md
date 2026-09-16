# Histórico de continuidade

## 16/09/2026 UTC — retomada documentada

- Conferido o Word e preservado seu conteúdo em `docs/continuidade/REGISTRO_ORIGINAL_2026-09-15.md`.
- Verificados GitHub Actions, log de 471 testes e SHAs DEV/main/runtime; diferenças registradas em `CONTEXTO_DO_PROJETO.md`.
- Revisados workflows de coleta e Autopilot, política de branch runtime e gravação de Quota Shadow.
- Preparado plano de ativação, reconciliação, critérios de aceite e rollback, sem executá-lo.
- Entrega exclusivamente documental. A suíte existente pertence a `d6d7779458dbd93735090d1eba45d44418fa672f`; não foi reexecutada para documentação. O filtro de caminhos do workflow não inclui Markdown.
- Pendência imediata: ferramenta de inventário/reconciliação somente leitura em DEV. Promoção continua dependente de autorização específica.

O histórico de desenvolvimento anterior está no registro original e no histórico Git. Não reconstruir commits ou resultados ausentes por suposição.

## 16/09/2026 UTC — auditoria de migração somente leitura

- Ferramenta CLI offline para inventário Git, hashes, presença em cada lado e bloqueios de revisão.
- JSON estrito, detecção de IDs duplicados/conflitantes em registros de primeiro nível, CSV com cabeçalho/largura/linhas repetidas, proteção contra refs locais alteradas.
- Nenhum mecanismo de cópia, remoção, promoção ou chamada ao provedor.
- Nove testes novos aprovados localmente; incluídos no workflow para execução conjunta com os 471 anteriores.
- Auditoria real: nove arquivos, seis diferenças, sete revisões obrigatórias. Resultado preservado em JSON.
- Contexto cumulativo preservado; próxima etapa e limitações descritas em CONTEXTO_DO_PROJETO.md.


## 16/09/2026 UTC — BOS/CHOCH, Order Block e checkpoint ZIP

- Criado workflow \`AtlasQuant DEV Checkpoint\` para produzir ZIP automático do commit exato em cada push da DEV, sem chamadas a provedores e sem tocar runtime.
- Implementado \`ict_structure_v111.py\` com BOS, CHOCH e Order Block rule-based auditável.
- BOS/CHOCH diferencia continuação, mudança de caráter e estrutura mista; não força classificação quando a evidência estrutural é ambígua.
- Order Block exige quebra + displacement + candle oposto de origem; rastreia mitigação/invalidação.
- Integrado ao Institutional Engine, Data Readiness e Central dos 7 pares como camada observacional.
- Pesos do readiness/Gate foram preservados; os componentes novos ainda não autorizam execução por si mesmos.
- Adicionados 5 testes específicos e integração ao Quality workflow.
- GitHub Actions run \`35092388237\`: **485/485 testes OK**, compile gate verde.
- Checkpoint ZIP run \`35092388358\`: sucesso.
- Runtime permaneceu em \`7a2ad3e53055fb1ef6091c39442c4c0f5212c3c1\`.
- Main observada em \`b36ba5c457b446ea8b2dfd76f1157ba4af6c52d5\`; nenhuma alteração foi feita nela nesta etapa.
