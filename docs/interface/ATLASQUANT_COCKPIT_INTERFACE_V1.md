# AtlasQuant Cockpit Interface V1

## Direção oficial

A interface aprovada segue a metáfora de **cockpit de espaçonave / hangar digital**: profundidade visual, painéis flutuantes, neon controlado, sensação 3D e alta densidade de informação, sem sacrificar leitura.

O princípio visual e de produto é permanente:

> **Poderoso por dentro. Simples por fora.**

O bordão deve permanecer visível na experiência principal, não escondido em rodapé.

## Navegação

Todos os grandes blocos do ecossistema aparecem como cards clicáveis e levam diretamente ao tema correspondente: Radar, Macroeconomia, Microeconomia, Geopolítica, Fundamentalista, ICT/SMC, Calendário Econômico, Pré-Notícia, Laboratório, Paper Trading, Guardião de Risco, Investimentos, Central AION, Administração, Studio/Vídeos, Negócios, Memória/Checkpoint, Segurança, Academy e Treasury & Growth.

A navegação superior pode usar abas flutuantes contextuais. Para o fluxo editorial de mercado, ficam reservadas:

- Visão Geral
- Análise da Semana
- Análise do Dia
- Fechamento do Dia
- Fechamento Semanal

## Central de vídeos

A interface deve tratar vídeos como parte nativa do cockpit, não como uma página externa.

- **Segunda cedo:** vídeo mais longo com leitura da semana para Forex, cripto, índices e macro.
- **Segunda a sexta cedo:** vídeo curto com expectativa do dia.
- **Segunda a sexta no fim do dia:** fechamento comparando o previsto com o realizado.
- **Sexta no fim do dia:** fechamento semanal completo comparando o cenário da segunda com o que realmente aconteceu.

A regra editorial é transparência explícita: mostrar acertos, erros, cenário que não se confirmou e mudança de contexto sem maquiar resultado.

## Integração técnica

A primeira implementação fica isolada em `atlasquant_cockpit_ui.py`. Ela é declarativa e **não está conectada automaticamente à produção**. Isso permite desenvolver a interface em paralelo sem alterar autoridade, runtime, memória, Recovery ou workers do AION/Núcleo.

A integração com a aplicação principal só deve ocorrer depois da validação do AION/Core correspondente e com testes de regressão da UI.
