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


## 16/09/2026 UTC — hardening do novo motor ICT estrutural

- Cobertura adicional para SELL em BOS/CHOCH.
- Cobertura de invalidação de Order Block.
- Cobertura fail-closed para dados insuficientes.
- Regressões de integração de frescor M15 no Data Readiness.
- GitHub Actions run \`35092846046\`: **491/491 testes OK** e compile gate verde.
- Checkpoint ZIP run \`35092846140\`: sucesso.
- Pesos de decisão e Gate permanecem inalterados.


## 16/09/2026 UTC — estrutura resiliente a range/ruído

- ICT Structure Engine atualizado para V1.1.2.
- Tolerância por ATR aplicada a viés estrutural e quebra por fechamento.
- Mesmo swing não pode gerar eventos duplicados após recruzamento.
- Adicionados metadados auditáveis de margem da quebra e tolerância de ruído.
- Novos testes: lateralização, equal-ish pivots, mesmo swing reutilizado e break marginal.
- GitHub Actions run \`35093251163\`: **495/495 testes OK**, compile gate verde.
- Checkpoint ZIP run \`35093251055\`: sucesso.
- Gate/readiness permanecem sem novos pesos nesta etapa.
