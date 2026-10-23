# Trader SMC Limpo LAB v0.5 — requisitos de visualização 22/10/2026

**Origem:** proprietário solicitou atualização do indicador Pine v0.4 após testes visuais com capturas do TradingView. **Estado:** requisito implementado somente em artefato experimental local para teste manual; não compilado no editor TradingView, não homologado.

## Requisitos validados em conversa
- **OB:** a caixa traz `OB` no canto direito, priorizando os ativos não mitigados; os últimos mitigados podem persistir claros e sem extensão à direita. Zonas invalidadas removidas.
- **FVG:** mesmas regras para `FVG`, sem deixar a tela cheia.
- **BOS / CHOCH / MSS:** linhas horizontais de estrutura e nomes na ponta direita. Linha verde tracejada antes do rompimento = **possibilidade**; ao fechar e romper o pivô confirmado, exibir linha vermelha = **evento confirmado**. Setas ↑/↓ deixam claro o sentido. Limitar por padrão ao último evento de cada tipo.
- **Candidatos:** como a classificação entre BOS, CHOCH e MSS depende da direção anterior e do impulso na quebra, a linha verde deve se chamar `Possível BOS` ou `Possível CHOCH/MSS`, sem fingir evento já confirmado.
- **Liquidez:** linhas discretas rotuladas `Topo do dia`, `Fundo do dia`, `Topo da semana`, `Fundo da semana`, `Topo do mês`, `Fundo do mês`; atualizar **os extremos em formação** conforme candles observados no timeframe intradiário. Cores separadas dia/semana/mês, texto no canto direito.
- Os extremos D/W/M são **referências de preço e possíveis pools de liquidez**, não identificação comprovada de ordens pendentes. Respeitar fronteiras de sessão do símbolo e divergências de fuso/timeframe.

## Implementação provisória
Artefatos disponibilizados em conversa: `AtlasQuant_SMC_Limpo_v05.pine` e ZIP com README. Código Pine v6 estático; não executa operações nem integra Worker.
- Defaults: 1 BOS, 1 CHOCH, 1 MSS; 2 OB ativos + 1 OB mitigado; 2 FVG ativos + 1 FVG mitigado; linhas diárias, semanais e mensais ativas, etiquetas à direita; OB primeiro toque, FVG preenchimento completo. Controles separados por grupo.
- **Limitações:** definição de MSS como reversão com corpo ≥ limiar de ATR é experimental; OB candidato é última vela oposta antes da quebra; pivôs confirmados exigem N barras e não preveem o futuro. Expectativa de zero falsos positivos não demonstrada.
- Não há compilação na TradingView nem QA visual comprovados; solicitar captura do Editor Pine/resultado em DXY M15 e H2 antes de promover qualquer coisa.
- Nenhuma alteração de `main`, deploy, Worker, corretora, compra de dados ou mudança de P0. **HARD NO-GO: 0/6 homologados.**
