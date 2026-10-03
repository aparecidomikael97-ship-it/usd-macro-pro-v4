# Interface Reference Lock — 03/10/2026

## Status

Contrato visual aprovado pelo administrador para a fase atual de fechamento da Interface.

Este documento não autoriza merge, deploy, publicação, gasto, alteração de credenciais ou trading real.

## Fluxo congelado

1. Login atual aprovado — não redesenhar.
2. Após autenticação, abrir a Central AtlasQuant com quatro ambientes:
   - Trader
   - Negócios
   - Investimentos
   - AION
3. Cada ambiente abre um cockpit próprio com a mesma linguagem visual premium.
4. Trader segue a referência visual aprovada do cockpit financeiro.
5. Negócios, Investimentos e AION reutilizam o mesmo design system, com conteúdo específico.

## Central pós-login

A Central deve manter:
- quatro cards grandes;
- ordem Trader → Negócios → Investimentos → AION;
- CTA autenticado para cada ambiente;
- fundo escuro, profundidade, glassmorphism, brilho controlado e alto contraste;
- slogan “Poderoso por dentro. Simples por fora.”;
- nenhuma rota HTML falsa.

## Trader

Preservar o cockpit visual aprovado como referência, com navegação funcional no próprio desenho:
- ticker/contexto;
- núcleo visual central;
- Macro, Micro, Geopolítica, Fundamentalista, ICT/SMC, Calendário, Pré-Notícia e Painel Mestre;
- Radar Mestre, Radar, Painel Mestre, Laboratório/Backtests, Paper Trading, Guardião de Risco, Academia, Diário, Vídeo/Conteúdo, AION e Perfil/Configurações acessíveis no ambiente Trader;
- cards, atalhos e itens laterais clicáveis no próprio elemento visual, sem faixa duplicada de botões abaixo;
- o conteúdo selecionado deve abrir como workspace principal, evitando rolagem longa para localizar a função;
- Trader não exibe atalhos de Negócios nem Investimentos; troca de ecossistema ocorre somente pela Central;
- AION permanece transversal e pode existir como assistente especializado no Trader;
- estados e força sem inventar preço ou probabilidade;
- ordens reais bloqueadas.

### Regra funcional posterior

Após o fechamento visual, indicadores e itens analíticos detalhados (por exemplo CPI/IPC anual, desemprego e séries mensais) devem abrir em clique próprio com explicação, cálculo, histórico e relatórios já disponíveis. Essa etapa funcional não deve bloquear o fechamento atual da interface.

## Negócios

Escopo atual:
1. Automação empresarial B2B
2. Captação de clientes / Revenue Ops com IA
3. Micro-SaaS próprio
4. Serviços de IA para clientes internacionais
5. Produtos digitais próprios

A interface atual não deve reintroduzir como frentes principais:
- dropshipping;
- afiliados;
- TikTok Shop;
- Mercado Livre;
- e-commerce genérico;
- white label genérico.

Governança prevista:
- FinOps;
- Saúde do Cliente;
- SLA / Suporte;
- Auditoria / LGPD;
- Equipe & Acessos;
- Hub de Integrações;
- Demo / Sandbox;
- isolamento por tenant.

## Investimentos

Cockpit patrimonial no mesmo padrão visual:
- Renda Fixa;
- Renda Variável;
- Fundos e Produtos;
- Carteira & Alocação;
- Análise de Risco;
- Planejamento;
- Renda & Dividendos;
- Crescimento;
- Relatórios;
- Educação Financeira;
- AION Investimentos.

Sem execução automática e sem promessa de rentabilidade.

## AION

Cockpit do único AION Core:
- Chat do AION (#537);
- Histórico;
- Memória;
- Tarefas;
- Biblioteca;
- Pesquisa;
- Checkpoint Mestre;
- Núcleo / Orquestração;
- 8 papéis internos;
- Auditoria / Guardião;
- Academy;
- AION English (#483).

Os oito papéis não são oito IAs independentes.

## Movimento

Cards:
- hover-lift discreto entre 3 e 7 px;
- brilho e sombra suaves;
- sem pulsação agressiva;
- sem piscar;
- sem movimento que prejudique leitura;
- respeitar `prefers-reduced-motion`.

## Estados de verdade

Usar rótulos explícitos como:
- CONECTADO
- PRÉVIA
- EM CONSTRUÇÃO
- EM EVOLUÇÃO
- PLANEJADO
- BLOQUEADO

Aparência pronta não significa funcionalidade pronta.

## Não regressão

Não alterar o login aprovado.
Não restaurar “AION IA” como nome da porta principal.
Não restaurar “Renda Fixa / Investimentos” como nome da porta principal.
Não restaurar marketplace/dropshipping como escopo atual de Negócios.
Não enfraquecer autenticação, RBAC, Safety Core, SAFE_WAIT, providers ou gates de autorização.
