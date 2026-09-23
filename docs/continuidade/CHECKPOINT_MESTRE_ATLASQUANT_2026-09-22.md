# AtlasQuant — Checkpoint Mestre Oficial

Atualizado em 22/09/2026.

Este documento é a fonte de continuidade de produto a partir de 22/09/2026.
Ele complementa:

- `docs/continuidade/REGISTRO_ORIGINAL_2026-09-15.md`
- `docs/continuidade/VISAO_MESTRE_BACKLOG_2026-09-18.md`
- demais documentos de `docs/continuidade/` e `docs/product/`

Em caso de conflito entre uma decisão antiga e uma decisão mais nova aprovada pelo
usuário, prevalece a decisão mais nova. Em caso de conflito entre documentação e
estado técnico, o repositório e os testes atuais prevalecem para dizer o que está
realmente implementado/validado.

## 1. Regra permanente do Checkpoint

Toda sugestão solicitada pelo usuário e aceita durante a conversa entra como
decisão oficial, salvo quando o usuário disser explicitamente "não gostei",
"não quero", "descarta" ou equivalente.

Estados obrigatórios:

- **APROVADO / PENDENTE** — decidido, ainda não implementado.
- **IMPLEMENTADO / EM VALIDAÇÃO** — código existe, mas falta prova completa.
- **VALIDADO** — passou pelos testes/gates definidos para a etapa.
- **DEPENDÊNCIA EXTERNA** — depende de credencial, conta, licença, loja, provedor
  ou ação do proprietário.
- **SUBSTITUÍDO** — decisão antiga preservada no histórico, mas uma decisão mais
  nova vale no produto.
- **DESCARTADO** — não entra no produto.

Nada desaparece quando concluído; apenas muda de estado.

## 2. Princípios centrais que não podem regredir

- Macro direciona; técnico/ICT/SMC confirma localização, timing e gatilho.
- Candle disponível não autoriza execução.
- Leitura + direção + filtros + gatilho + timeframe correto/fresco precisam
  estar alinhados.
- Falta, conflito, atraso, NaN, payload incompleto ou timeframe errado =>
  fail-closed.
- Score interno não é probabilidade de lucro.
- "NÃO OPERAR / AGUARDAR" é resultado válido.
- Ordens reais permanecem desligadas até a escada de validação ser cumprida.
- Não há promoção automática de estratégia, modelo, threshold ou Gate.
- Mudanças críticas precisam de rollback, auditoria e revisão humana.
- Qualidade > quantidade de operações.
- Filosofia operacional: poucas oportunidades, risco controlado e relação
  risco/retorno assimétrica quando a estrutura permitir; nunca fabricar trade
  para atingir meta de frequência.
- Regra de preservação aprovada: depois de 2 wins no mesmo dia UTC, novas
  operações Paper/Forward ficam bloqueadas pelo Risk Guardian até o novo dia.

## 3. Escada oficial de promoção

Fluxo obrigatório para qualquer operacional, ativo, timeframe ou motor novo:

**Laboratório/Testes → Backtest/OOS/Walk-Forward → Shadow → Paper/Forward →
Admin → validação prática do proprietário por alguns dias → revisão humana →
Público.**

Nenhuma etapa pode ser pulada apenas porque o resultado parece bom.

## 4. Interface AtlasQuant 2.0 — decisão aprovada

Objetivo: parecer futurística sem sacrificar clareza.

### 4.1 Navegação

- Poucas portas principais.
- Estrutura-base: **Radar, Painel Mestre, Agenda, Academia, Diário e Perfil**.
- Funções secundárias entram dentro dessas áreas para evitar dezenas de abas.
- Cards/carrosséis horizontais arrastáveis, inspirados no conceito mostrado pelo
  usuário em vídeo, sem copiar identidade visual de terceiros.
- Cada card tem ícone/ilustração simples + nome escrito; ícone nunca substitui
  texto.
- Cards bloqueados continuam visíveis no modo Iniciante, com cadeado e prévia do
  que existe dentro.
- Ao tocar em card bloqueado, mostrar explicação/previsão de conteúdo e forma de
  liberar, sem tela fria.
- Gestão de risco e conteúdo de segurança não ficam escondidos atrás de paywall.
- Interface adaptativa por perfil/nível.
- Layouts personalizáveis e restauráveis.

### 4.2 Legibilidade

- Texto principal grande, contraste alto e leitura imediata.
- Evitar cinza claro/baixa opacidade em cards escuros.
- Referência visual: corpo ~16–18 px e títulos maiores, respeitando responsividade.
- Alto contraste, fonte ampliável e acessibilidade para daltonismo.
- Mobile é requisito de primeira classe, não adaptação posterior.
- Nenhuma tela deve exigir "forçar a vista".

### 4.3 Personalização

Central **Personalizar AtlasQuant**:

- tema escuro, preto profundo, claro, alto contraste e tema Atlas;
- brilho/contraste/densidade/tamanho de fonte;
- seguir tema do dispositivo;
- cores configuráveis de gráfico dentro de limites seguros;
- salvar layouts por dispositivo;
- restaurar padrão;
- português, inglês e espanhol como idiomas iniciais;
- texto e voz no mesmo idioma;
- preferências de voz, velocidade e quantidade de fala;
- sincronização de perfil entre celular e computador.

## 5. Radar — porta de entrada do produto

Status: núcleo existe; experiência final ainda evoluindo.

Decisões aprovadas:

- **Radar é a aba principal**.
- Mostrar automaticamente **até 10 ativos em observação**; decisão mais nova
  substitui sugestões antigas de 3–5.
- Não exigir pesquisa manual de EUR/USD, GBP/CHF etc.
- Ranking pode usar força, contexto, qualidade e confiança dos dados, mas não
  pode ser apresentado como probabilidade de lucro.
- Um ativo estar no Top 10 não significa entrada autorizada.
- Se nada estiver alinhado, o Radar deve dizer isso explicitamente.

Cada card enxuto deve priorizar:

- ativo;
- viés;
- estado operacional;
- status temporal;
- qualidade/frescor;
- horário da leitura;
- bloqueio de risco quando existir.

Ao clicar:

- opção **Ler análise**;
- opção **Ouvir análise**;
- voz e texto devem contar a mesma leitura;
- motivo do viés;
- macro;
- técnico;
- notícias;
- confiança dos dados;
- riscos;
- invalidação;
- o que falta para liberar uma entrada;
- horário/idade/validade da leitura.

Áudio só toca por ação do usuário.

### 5.1 "Por que não?"

Recurso prioritário.

Exemplo de resposta:
"Macro alinhada; M15 ainda sem gatilho; evento relevante próximo; risco continua
bloqueado."

O recurso explica bloqueios e educa, sem tentar convencer o usuário a operar.

### 5.2 Central de Decisão

Dentro do Radar:

- viés;
- macro;
- técnico;
- risco;
- gatilho;
- validade;
- qualidade da fonte;
- o que falta;
- por que sim;
- por que não.

## 6. Painel Mestre

- visão profunda, separada do Radar rápido;
- Viés Macro ≠ Entrada;
- Estado Operacional separado da direção macro;
- hora da leitura;
- idade;
- validade;
- status temporal;
- autorização atual;
- revalidar quando dado estiver velho/sem horário;
- M15 vermelho = gatilho contra, nunca "quase pronto";
- M15 sem evidência = aguardar gatilho.

## 7. Assistentes do ecossistema

### 7.1 Assistente AtlasQuant do cliente

- texto + voz;
- saudação pelo **nome real do cadastro**;
- bom dia/tarde/noite;
- resumo do mercado;
- viés diário/semanal;
- explica o Radar;
- responde "por quê?" e "por que não?";
- muda linguagem conforme nível do usuário;
- não fala sozinho durante gráfico, salvo alerta crítico autorizado;
- modo silencioso;
- histórico voz + texto;
- continuidade entre dispositivos.

### 7.2 Copiloto do Admin

Assistente exclusivo do administrador, inspirado na dinâmica de um copiloto
inteligente de ficção, com identidade própria AtlasQuant.

Funções:

- mercado/oportunidades em observação;
- saúde do sistema;
- dados atrasados;
- falhas de provider;
- erros de tela/módulo;
- gestão;
- suporte;
- assinatura/clientes;
- prioridades técnicas;
- alertas de risco;
- resumo de reclamações/sugestões.

Pode observar, explicar e preparar ação; ações críticas continuam exigindo
confirmação/revisão.

### 7.3 Atendente virtual humanizada

Separada do assistente de mercado:

- pré-venda;
- cadastro;
- dúvidas;
- cobrança;
- suporte;
- reclamação;
- acompanhamento de protocolo.

### 7.4 Voz do Cliente

Assistente dedicado a:

- sugestões;
- reclamações;
- bugs;
- dúvidas recorrentes;
- agrupamento por tema;
- frequência;
- gravidade;
- prioridade;
- status recebido → análise → planejado → correção → resolvido;
- integração com Copiloto do Admin.

### 7.5 Orquestrador de assistentes

Um roteador entende intenção/contexto e chama o assistente correto.

Princípios:

- interrupção natural;
- níveis de urgência;
- modo silencioso;
- memória controlável;
- confirmação reforçada para ação sensível;
- fallback texto se voz cair;
- logs de por que cada assistente avisou algo.

## 8. Boas-vindas / vídeo inicial

- vídeo curto, humanizado e motivacional;
- nome dinâmico vindo do cadastro;
- convite para ver o mercado atual;
- sem promessa de lucro;
- CTA "Ver mercado de hoje" / "Explorar AtlasQuant";
- opção pular/não mostrar novamente;
- depois do vídeo, assistente oferece ajuda contextual.

## 9. Academia AtlasQuant

Modo Iniciante recebe formação do zero.

Trilhas:

- Mercado Financeiro do Zero;
- Forex;
- macroeconomia;
- bancos centrais;
- indicadores;
- leitura de notícias;
- força de moedas;
- ICT/SMC;
- AMD;
- FVG;
- Order Block;
- BOS/CHOCH/MSS;
- OTE;
- CRT;
- Quarterly/Weekly Profiles;
- gestão de risco;
- uso do próprio AtlasQuant;
- corretoras/plataformas;
- Paper/Forward/Backtest.

Formato:

- vídeo curto;
- texto;
- exemplo;
- gráfico;
- exercício;
- quiz;
- progresso;
- professor contextual;
- explicação "como criança / intermediário / profissional";
- glossário instantâneo;
- revisão espaçada;
- estudos de caso;
- desafios;
- certificados internos;
- laboratório sem dinheiro real;
- diário de aprendizado;
- conteúdo versionado/data de revisão;
- botão "não entendi, explique de outro jeito".

Modo Avançado aprofunda pesquisa, macro, institucional, backtest, evidências e
interpretação do sistema.

Academia promete entendimento/processo/risco, nunca lucro.

## 10. Agenda e dados macro

Agenda unificada deve reunir:

- calendário econômico dentro do AtlasQuant, estilo experiência de calendário
  econômico profissional, sem copiar produto de terceiros;
- anterior;
- consenso;
- atual;
- surpresa;
- revisões;
- horário/fuso;
- bancos centrais;
- geopolítica;
- eventos da semana;
- risco por evento;
- Macro Briefing diário/semanal escrito e falado.

Nowcast é diagnóstico/pesquisa e continua fail-closed quando provider falha.

## 11. Gráficos e TradingView

- gráfico integrado dentro do ecossistema;
- experiência semelhante a plataforma profissional de charts, sem copiar
  identidade;
- marcações próprias AtlasQuant no futuro;
- Backtest/Forward continuam motores auditáveis e independentes da tela;
- TradingView/Pine funciona como camada paralela quando aplicável.

## 12. Diário / Performance

Unificar:

- Paper;
- Forward;
- Backtest;
- ganhos/perdas;
- R bruto;
- custos;
- spread;
- slippage;
- R líquido;
- setup;
- sessão;
- timeframe;
- motivo da entrada;
- motivo do bloqueio;
- invalidação;
- comparação histórico × prospectivo;
- evolução por operacional;
- relatório simples de erros repetidos.

Checklist deve responder pelo menos:

1. Por que entrar neste cenário?
2. O que aconteceu para nascer essa leitura?
3. Como devo entrar/qual condição precisa ocorrer?
4. Por que não entrar agora?
5. O que invalida?

## 13. Qualidade das operações

Diretriz de produto:

- não aumentar número de trades artificialmente;
- buscar seletividade;
- priorizar oportunidades mais completas;
- reduzir perda quando cenário invalida;
- preservar ganho com regras de risco;
- medir expectativa e R líquido, não apenas win rate;
- nunca prometer proporção fixa de acertos.

## 14. Horários / perfis operacionais

O sistema deve contemplar pessoas que só podem operar:

- manhã;
- tarde;
- noite/madrugada;
- sessões específicas.

Perfil de horário reorganiza atenção e educação, mas não muda score/direção nem
fabrica oportunidade.

## 15. Índices e outros mercados

Motores específicos, sem copiar pesos Forex.

Roadmap inclui:

- Dow Jones;
- Nasdaq;
- S&P 500;
- WIN;
- WDO;
- Ibovespa;
- DXY.

Cada mercado passa por sua própria validação.

## 16. Cripto

Primeiro grupo aprovado:

- BTC/USD;
- ETH/USD;
- SOL/USD.

Cripto permanece separado do núcleo Forex e segue a escada
Laboratório → Shadow → Admin → validação prática → Público.

## 17. Ecossistema Investir

Entrada do produto deve permitir:

- Operar;
- Investir;
- Os dois.

Investimentos:

- CDB;
- Tesouro;
- LCI/LCA;
- FIIs;
- dividendos;
- crescimento;
- reserva;
- liquidez;
- diversificação;
- risco;
- tributação;
- FGC quando aplicável;
- educação financeira.

Planejador de Patrimônio:

- metas;
- aportes;
- reinvestimento;
- projeção;
- real × projetado;
- "Comece com pouco";
- perfis e suitability contínuo;
- eventual Open Finance somente com autorização explícita.

## 18. Impostos e documentação

Centro educacional/fiscal futuro:

- organização de operações;
- custos;
- lucros/prejuízos;
- documentos;
- exportação para contador;
- explicações por mercado;
- conteúdo revisado conforme legislação;
- não substituir contador/assessoria fiscal individual.

## 19. Corretoras e plataformas

Guia comparativo próximo do lançamento:

- spread;
- comissão;
- slippage;
- execução;
- regulação;
- proteção;
- saque/depósito;
- plataforma;
- disponibilidade por país;
- tutorial.

Spread/custo deve ter peso forte na comparação. Nomes de corretoras não ficam
congelados sem nova pesquisa perto do lançamento.

## 20. Comunidade e WhatsApp

### Comunidade interna

- grupos/salas;
- alunos;
- arquivos;
- histórico;
- busca;
- moderação;
- código de conduta;
- estudo/operacionais;
- suporte.

### WhatsApp

Extensão futura do AtlasQuant:

- consultas;
- avisos;
- alertas informativos;
- linguagem "possível oportunidade em observação", nunca ordem/garantia;
- link de volta para o Radar como fonte principal;
- permissões e consentimento.

## 21. Perfis, permissões e multi-admin

Papéis:

- USER;
- SALES;
- ADMIN;
- múltiplos administradores futuros;
- contas separadas;
- trilha de auditoria;
- menor privilégio;
- dupla aprovação em ação crítica;
- ADMIN pode ativar/bloquear/revogar/mudar plano sem ver senha;
- não existe cadastro público para virar ADMIN;
- 2FA/passkeys/dispositivos/histórico de acesso entram no roadmap.

## 22. Segurança e resiliência

Aprovado:

- Kill Switch geral e por módulo;
- backup + recuperação realmente testada;
- disaster recovery;
- rollback;
- guardrails críticos no CI;
- real_orders off testado automaticamente;
- stale data bloqueia;
- sem auto-promoção;
- detector de degradação de setup;
- Stress Lab;
- Execution Reality Lab com spread, slippage, latência, sessão,
  volatilidade e liquidez;
- auditoria;
- logs;
- central de confiança de fontes.

## 23. Governança e explicabilidade

Aprovado:

- Passaporte da Análise;
- Máquina do Tempo / Replay;
- Linha do Tempo da Decisão;
- Registro de Experimentos;
- Central de Confiança das Fontes;
- Governança da IA;
- histórico de versão;
- fontes;
- correções humanas;
- Mapa de Risco Cross-Asset;
- suitability contínuo;
- modo regulatório por país.

## 24. Alertas

- Centro de Alertas no topo, não uma aba gigante;
- mudança de viés;
- oportunidade em observação;
- dado expirando;
- evento próximo;
- risco bloqueado;
- falha crítica;
- Governador de Alertas para evitar excesso;
- níveis normal / atenção / importante / crítico;
- preferências por canal.

## 25. Comercial e crescimento

Somente depois da estabilidade técnica:

- login individual;
- assinatura;
- planos por nível;
- controle de sessões;
- vídeo institucional;
- landing page;
- lista de espera;
- beta fechado;
- feedback/cases reais;
- referral depois de boa experiência;
- YouTube;
- Instagram;
- TikTok;
- LinkedIn;
- presença complementar em X/Facebook/Threads;
- Brand Kit;
- posicionamento como inteligência de mercado, nunca "robô de sinal";
- revisão jurídica/regulatória antes do lançamento.

Marca AtlasQuant:

- pesquisar disponibilidade e registro de marca no INPI é ação externa futura;
- registro não deve ser chamado de patente;
- depende do proprietário/conta/pagamento.

## 26. Produto futuro: experiência "UAU"

O produto precisa maximizar:

- entendimento em segundos;
- simplicidade;
- velocidade;
- prova;
- confiança;
- auditabilidade;
- escala;
- retenção.

Aprovado:

- Matriz Mestre de Conclusão;
- Product Readiness por pilar;
- medir onboarding;
- ativação;
- retenção;
- uso das funções;
- qualidade do suporte;
- saúde técnica.

## 27. Dependências externas conhecidas

- Render: deploy precisa de integração/hook/credencial válida para publicação
  controlada; não declarar atualizado sem prova do build.
- EODHD: credencial/plano precisa ser válido; 401/403 continua fail-closed.
- TTS/voz final: fornecedor/credencial/licença.
- lojas mobile: contas e processos externos.
- pagamentos: gateway e contratos.
- jurídico/privacidade/licenciamento de dados.
- INPI/registro de marca.

## 28. Prioridade técnica imediata em 22/09/2026

1. Corrigir/fault-isolar erro vermelho do Radar em modo Avançado.
2. Validar Radar local em desktop/mobile e navegar todas as áreas.
3. Confirmar CI/Readiness/Browser/UI Smoke.
4. Confirmar versão realmente servida pelo Render; não confundir Health 200 com
   deploy do build correto.
5. Estabilizar nova navegação/legibilidade.
6. Radar Top 10.
7. Implementar "Por que não?".
8. Assistente Atlas contextual.
9. Agenda.
10. Diário/Performance.
11. Evoluir interface catálogo/carrossel/cadeados.
12. Só então acelerar expansões maiores.

## 29. Itens explicitamente fora deste projeto

Plano pessoal do usuário para gerar renda extra com vendas no Mercado Livre /
TikTok Shop fica fora do AtlasQuant e não entra neste Checkpoint.

## 30. Regra de fechamento

Cada etapa só pode ser anunciada como concluída quando houver evidência real.

Formato de fechamento desejado:

- o que foi feito;
- o que foi testado;
- resultado dos testes;
- commit/PR;
- dependência restante;
- status atualizado no Checkpoint.

No encerramento global do projeto, gerar uma planilha Excel profissional contendo
todas as decisões, estados, implementações, validações, pendências, dependências e
datas, para arquivo do proprietário.
