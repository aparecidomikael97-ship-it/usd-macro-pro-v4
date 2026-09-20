# AtlasQuant — Fundação do Ecossistema Operar + Investir

Atualizado em 20/09/2026.

Este documento fixa a expansão de produto definida para o AtlasQuant sem ligar broker, ordens reais ou promessas de retorno. A implementação deve continuar em fases, preservando o núcleo já validado.

## 1. Três caminhos de entrada

O onboarding futuro deve permitir:

- **Operar** — day trade, swing trade e position trade;
- **Investir** — preservação de capital, renda e crescimento patrimonial;
- **Os dois** — integração entre resultado operacional e construção de patrimônio.

A interface pode adaptar profundidade para Iniciante e Avançado sem esconder riscos.

## 2. Área Investir

Cobertura planejada:

- CDB;
- Tesouro;
- LCI/LCA;
- outros produtos de renda fixa elegíveis;
- fundos imobiliários;
- ações de dividendos;
- ações/empresas em crescimento para lista de observação de longo prazo.

Cada ativo/produto deve mostrar, quando aplicável:

- preço/cota;
- rendimento histórico e atual;
- liquidez;
- prazo/carência;
- tributação;
- risco de crédito/mercado;
- proteção do FGC quando realmente aplicável e dentro das regras vigentes;
- histórico de dividendos/distribuições;
- consistência;
- payout;
- dívida;
- lucro/FFO;
- fluxo de caixa;
- vacância e contratos para FIIs;
- principais riscos e limitações dos dados.

O AtlasQuant compara; não deve escrever que ganho, dividendo ou valorização são certos.

## 3. Planejador de Patrimônio dentro do app

Substitui a necessidade de Excel para a maioria dos usuários.

Entradas:

- valor inicial;
- aporte mensal;
- horizonte;
- cenário de rentabilidade;
- objetivo de renda mensal;
- opção de usar ou reinvestir rendimentos.

Saídas:

- total aportado;
- patrimônio projetado;
- ganho projetado separado do dinheiro aportado;
- renda projetada;
- evolução anual;
- comparação de cenários;
- real × projetado quando houver histórico real.

Horizontes rápidos: 1, 3, 5, 10, 20 e 30 anos.

Deve existir a experiência **Comece com pouco**, permitindo testar aportes como R$ 50, R$ 100, R$ 200 e valores livres, para visualizar o efeito de constância + tempo sem prometer desempenho.

## 4. Radar de Renda e Dividendos

Comparar ativos lado a lado com foco em qualidade e sustentabilidade, não somente maior dividend yield.

O radar deve distinguir:

- valor distribuído;
- consistência;
- crescimento de lucro/FFO;
- fluxo de caixa;
- payout;
- dívida;
- vacância/contratos quando aplicável;
- concentração;
- riscos;
- mudanças recentes.

Qualquer índice interno deve ser chamado de índice de qualidade/consistência, nunca probabilidade de lucro ou pagamento garantido.

## 5. Radar de Crescimento

Objetivo: descobrir empresas que merecem estudo e acompanhamento de longo prazo, inclusive menores/em expansão.

Analisar fatores como:

- crescimento de receita;
- crescimento de lucro;
- fluxo de caixa;
- margens;
- dívida;
- diluição;
- retorno sobre capital;
- tamanho e expansão do mercado;
- vantagens competitivas quando suportadas por evidência;
- riscos.

Linguagem permitida: "fatores que favorecem crescimento" / "merece acompanhamento".
Linguagem proibida: "vai crescer", "vai valorizar", "é certeza".

## 6. Educação financeira integrada

A trilha deve poder começar antes do investimento:

- organização financeira;
- dívidas;
- reserva de emergência;
- objetivos;
- risco × retorno;
- liquidez;
- inflação;
- juros compostos;
- diversificação;
- tributação;
- renda fixa;
- FIIs;
- dividendos;
- crescimento patrimonial;
- prevenção a golpes.

A pessoa aprende no mesmo lugar em que simula e acompanha.

## 7. Agente de Comportamento Financeiro

Não se apresentar como psicólogo ou terapia profissional.

Funções planejadas:

- identificar FOMO, vingança de mercado, medo, ganância e excesso de confiança;
- revisar se a decisão respeita plano e risco;
- diário emocional;
- perguntas de checagem antes/depois de decisões;
- ajudar a revisar objetivo e horizonte quando houver pânico;
- encaminhar para ajuda profissional quando a questão ultrapassar educação/comportamento financeiro.

## 8. Guardião de Risco — obrigatório antes de ordens reais

Se execução real existir no futuro, não pode nascer sem:

- perda máxima diária;
- risco máximo por operação;
- máximo de operações;
- máximo de perdas consecutivas;
- limite de exposição simultânea;
- kill switch;
- bloqueio após limite;
- cooldown para aumentar limites;
- auditoria das alterações.

Exemplo de regra suportada: banca de R$ 1.000 e perda diária máxima de R$ 200 → novas operações bloqueadas ao atingir R$ 200 de perda.

Reduzir risco pode ser imediato. Aumentar risco no impulso deve exigir período de espera configurado.

## 9. Day, Swing, Position e Gestor de Posição por Evento

Horizontes:

- day trade: posição normalmente encerrada no mesmo dia;
- swing: dias/semanas;
- position: semanas/meses;
- investimento: horizonte patrimonial de longo prazo.

O **Gestor de Posição por Evento** deve acompanhar posições abertas antes e depois de eventos relevantes, incluindo:

- decisões de juros e comunicação de bancos centrais;
- CPI/Core CPI;
- PCE/Core PCE;
- Payroll/NFP;
- desemprego e salários;
- PPI;
- PMI/ISM;
- PIB;
- vendas no varejo;
- discursos e eventos equivalentes das moedas acompanhadas.

Antes: expectativa, consenso, precificação, risco de volatilidade e cenários.
Depois: realizado × consenso × anterior, mudança da tese, riscos e invalidações.

O sistema apresenta cenários; não presume que uma notícia "favorável" produzirá movimento garantido.

## 10. Motor 24/7

Arquitetura alvo:

- coleta e processamento no servidor;
- workers separados;
- filas;
- cache;
- banco histórico;
- logs;
- health checks;
- reinício automático;
- fallback de fonte;
- alertas somente quando houver mudança relevante;
- funcionamento independente de o app/celular estar aberto.

A meta é alta disponibilidade e atualização contínua, sem prometer ausência absoluta de indisponibilidade.

## 11. Copiloto do Administrador

O Admin deve receber relatórios automáticos e poder perguntar sob demanda:

- resumo do dia/semana/mês;
- comportamento do mercado;
- operacionais mais consistentes por regime/sessão/par;
- losses, gains, drawdown e custos;
- divergência backtest × paper;
- onde o sistema está piorando;
- quais dados/fontes falharam;
- quais melhorias merecem teste;
- quais setups têm evidência suficiente para avaliação no modo Iniciante.

Critério de Iniciante continua sendo robustez + clareza + risco controlado + evidência suficiente, não apenas "deu mais lucro esta semana".

## 12. Modelo comercial futuro

Preferência de produto: **assinatura/mensalidade**, não venda única.

Valor deve ser justificado por ferramentas, análise, educação, automação, monitoramento e economia de tempo; nunca por promessa de lucro.

Antes de contratar dados em tempo real, comparar:

- preço;
- latência;
- cobertura;
- confiabilidade;
- SLA;
- limites;
- histórico;
- atribuição;
- licença para exibição/redistribuição;
- custo por usuário;
- impacto na margem.

Durante a validação privada, priorizar fontes oficiais e tiers gratuitos quando tecnicamente/licencialmente adequados.

## 13. Segurança, simulação, backup e portabilidade

- ambiente de simulação/paper separado da conta real;
- exportação dos dados do usuário;
- backups e recuperação;
- logs/auditoria;
- nenhuma mudança destrutiva silenciosa;
- nenhuma promoção automática para real por resultado curto.

## 14. Estado de ativação

Esta fundação NÃO ativa:

- broker;
- ordens reais;
- assinatura pública;
- cobrança;
- redistribuição comercial de dados;
- recomendações com promessa de retorno.

Continua valendo a sequência:
**backtest → walk-forward/OOS → shadow → paper → revisão humana → execução real limitada**.
