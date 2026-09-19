# AtlasQuant — Visão Mestre e Backlog de Produto

Atualizado em 18/09/2026.

Este documento consolida decisões de produto que devem ser preservadas para as fases futuras sem interromper o núcleo atual. Ele não autoriza trading real, merge para main, publicação em lojas, alteração de secrets ou ativação automática de estratégias.

## 1. Experiência principal

A tela principal deve responder rapidamente:

1. O que está acontecendo no mercado.
2. Qual é o viés por moeda e por par.
3. Qual horizonte está sendo analisado: intraday, diário e semanal.
4. Qual a confiança/qualidade do cenário.
5. Por que o AtlasQuant chegou ao viés.
6. O que é evidência a favor, contra e neutra.
7. O que pode invalidar o cenário.
8. Quais eventos podem alterar o viés.
9. Quando o melhor estado é NEUTRO / NÃO OPERAR.

O usuário não deve precisar montar o quebra-cabeça manualmente. A interface deve permanecer enxuta; a complexidade fica por trás.

## 2. Viés detalhado — núcleo do produto

Cada viés deve poder exibir:

- COMPRA / VENDA / NEUTRO / NÃO OPERAR;
- horizonte diário e semanal;
- força relativa base × cotada;
- macroeconomia;
- juros e expectativas de bancos centrais;
- inflação, emprego, atividade e crescimento;
- notícias e geopolítica;
- cross-asset/intermarket;
- regime de mercado;
- técnico ICT/SMC;
- qualidade e frescor dos dados;
- principais motivos;
- evidências contrárias;
- gatilhos de invalidação;
- próximos catalisadores;
- histórico de mudança do viés;
- explicação em linguagem simples;
- versão falada pelo assistente de voz.

Score interno não deve ser chamado de probabilidade de lucro sem calibração válida.

## 3. Educação / Academy

A Academy é entrega obrigatória depois que as telas estabilizarem. Deve ter texto, exemplos e vídeos curtos.

Conteúdos mínimos:

- fundamentos de macroeconomia;
- microeconomia aplicada ao mercado quando relevante;
- inflação;
- juros;
- PIB;
- CPI/IPC;
- Core CPI;
- PCE/Core PCE;
- PPI/IPP;
- Payroll/NFP;
- desemprego;
- salários;
- PMI/ISM;
- bancos centrais;
- Federal Reserve / FOMC / dot plot;
- ECB, BoE, BoJ e outros G8;
- hawkish × dovish;
- calendário econômico;
- surpresa atual × consenso × anterior;
- DXY e cross-asset;
- geopolítica aplicada ao mercado;
- força relativa das 8 moedas;
- ICT/SMC;
- liquidez, BOS/CHOCH, FVG, OTE, CRT, AMD;
- leitura das telas do AtlasQuant;
- como interpretar BUY/SELL/NEUTRAL/NÃO OPERAR;
- gestão de risco e limites do modelo.

Elliott fica fora do motor por subjetividade. Wyckoff pode ser referência conceitual futura, sem prioridade; AMD já cobre parte do raciocínio de acumulação/manipulação/distribuição.

## 4. Assistente de voz

Entrega futura obrigatória:

- Resumo de Hoje;
- Visão da Semana;
- Explique meu Viés;
- próximos eventos;
- moedas fortes/fracas;
- riscos e invalidações;
- leitura do briefing já calculado pelo motor.

A voz não deve inventar dados nem contradizer o motor.

## 5. Posicionamento institucional / COT — fase final

Não implementar no núcleo agora.

Fase final planejada:

- CFTC COT;
- posicionamento líquido;
- COT Index normalizado;
- variação semanal;
- extremos;
- open interest;
- futuros CME quando disponível/licenciado;
- volume/VWAP;
- volatilidade/opções quando a fonte permitir;
- divergência preço × posicionamento;
- score institucional por moeda;
- comparação base × cotada;
- painel visual;
- histórico e backtest.

Primeiro observacional, depois validação. Não recebe peso automático antes de provar valor.

## 6. Instituições / fluxo

Objetivo futuro: evidência de posicionamento institucional, sem afirmar que um banco específico entrou em determinado preço.

Sinais possíveis:

- execução fragmentada;
- volume;
- open interest;
- VWAP;
- liquidez;
- deslocamento;
- FVG;
- futuros;
- opções;
- volatilidade;
- COT;
- cross-asset.

## 7. Fontes e custo

Princípios:

- fontes oficiais primeiro;
- custo mínimo;
- cache central;
- atualização de acordo com a frequência real do dado;
- não consultar CPI/PIB/COT a cada minuto;
- pagar por dados/licenciamento apenas quando necessário para escala comercial;
- UI não força chamadas de mercado.

Fontes-alvo incluem bancos centrais, agências oficiais, FRED e CFTC. Fontes comerciais devem respeitar licenças antes de revenda.

## 8. Corretoras & Plataformas

Aba futura obrigatória com comparação objetiva e tutorial.

Requisitos:

- explicar corretora × plataforma;
- abertura de conta;
- KYC;
- depósito/saque;
- MetaTrader/cTrader/TradingView quando aplicável;
- spreads;
- comissões;
- alavancagem;
- proteção de saldo;
- regulação;
- riscos;
- disponibilidade para residentes do Brasil;
- vídeos passo a passo.

A lista de corretoras deve ser pesquisada novamente próximo ao lançamento; não congelar nomes antigos como recomendação permanente.

## 9. Backtest / forward / TradingView

Objetivo:

- motor próprio AtlasQuant rodando independente da tela;
- Pine/TradingView como camada paralela de validação/alerta;
- histórico por operacional;
- forward test;
- walk-forward;
- out-of-sample;
- shadow;
- paper;
- custos/slippage;
- Champion × Challenger;
- estabilidade por sessão/regime/par;
- sem alteração automática de estratégia por amostra pequena.

Operacionais adicionais só entram se forem objetivos e programáveis. Candidatos futuros: liquidity sweep + displacement + FVG return, SMT, estrutura HTF e killzones.

## 10. Automação de execução — somente fase posterior

Sequência obrigatória:

Backtest → Walk-forward/OOS → Shadow → Paper → revisão humana → execução real limitada.

Mesmo no futuro, execução real precisa de:

- limite de perda diária;
- drawdown máximo;
- exposição por moeda;
- limite de trades;
- kill switch;
- integridade/frescor;
- eventos;
- conexão com broker;
- reconciliação de ordens;
- auditoria.

Estado atual continua:

- real_orders=false;
- broker_connection=false;
- automatic_gate_change=false;
- automatic_promotion=false.

## 11. Produto comercial

Antes de venda:

- login;
- USER / SALES / ADMIN;
- portal administrativo;
- instalação/PWA;
- onboarding;
- Academy;
- suporte;
- termos/riscos;
- licenciamento de dados;
- observabilidade;
- backup/rollback;
- testes ponta a ponta;
- política de privacidade e segurança.

## 12. Regra de desenvolvimento

Trabalhar em blocos grandes sem atropelar validação.

Cada bloco deve preferir:

Implementar → testar → corrigir → confirmar CI → congelar checkpoint → gerar ZIP em marcos relevantes.

Nada neste backlog é justificativa para misturar todas as features de uma vez. A ordem deve preservar o núcleo estável e a rastreabilidade.
