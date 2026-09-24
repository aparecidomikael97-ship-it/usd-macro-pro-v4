# AtlasQuant — AION Foundation — 2026-09-23

## Estado deste checkpoint

Este documento registra o primeiro bloco implementado do **AION oficial do Administrador**.
Ele representa código criado em branch de feature e **não deve ser confundido com produção validada**
até que Quality, UI Smoke, Mobile DOM e os checks aplicáveis estejam verdes, o PR seja revisado/mesclado
e a produção confirme o build correspondente.

## Prioridade aprovada

A ordem de trabalho definida para esta fase é:

1. Interface / experiência principal.
2. Modo Administrador.
3. Central AION.
4. Memória persistente + Checkpoint Mestre.
5. Guardian / permissões / verdade / segurança.
6. Integrações avançadas.
7. Retomar refinamento de operacionais, treino e backtests depois da fundação do sistema.

## O que foi implementado neste bloco

### Núcleo AION

Criado `atlasquant_aion_core.py` com:

- roteamento de contexto entre Central, Trading, Studio, Negócios, Laboratório, Secretaria,
  Desenvolvimento e Promoções;
- Camada de Verdade: CONFIRMED / INFERENCE / HYPOTHESIS / UNKNOWN;
- Guardian fail-closed;
- bloqueio permanente de trading real nesta release;
- aprovação explícita para ações sensíveis;
- feature flags desligadas por padrão;
- política Custo Zero;
- Motor de Missões básico e determinístico.

### Memória / Checkpoint Mestre

Criado `atlasquant_aion_memory.py`.

Fontes canônicas de memória:

- `CONTEXTO_DO_PROJETO.md`;
- `HISTORICO_DE_ALTERACOES.md`;
- `docs/continuidade/*.md`;
- `docs/release/ATLASQUANT_RELEASE_FINAL.md`;
- fundação AION aprovada e consolidada neste checkpoint.

A memória estática é pesquisável por texto e mantém proveniência (arquivo, trecho e hash).

O Checkpoint Mestre mutável usa, quando configurado, o branch dedicado de runtime e o caminho:

`dados/aion/checkpoint_master.json`

A escrita:

- nunca vai para `main`;
- exige sessão ADMIN;
- exige clique/aprovação explícita;
- retorna status real de persistência;
- não declara sucesso quando credenciais/runtime estão ausentes.

### Gateway de IA

Criado `atlasquant_aion_gateway.py`.

Estado inicial:

- modo local/determinístico;
- custo zero;
- nenhum modelo externo ativado automaticamente;
- solicitação de modelo externo permanece bloqueada por feature flag;
- respostas locais deixam claro os limites da fundação.

Isso significa que **o chat AION ainda não equivale a um LLM geral de primeira linha**.
A fundação de roteamento, segurança, memória e UI está pronta para receber esse provedor depois,
sem ativar cobrança sem autorização.

### Command Center do Administrador

Criado `atlasquant_aion_admin.py` com interface futurística responsiva.

Workspaces internos:

- Central;
- Trading;
- Studio;
- Negócios;
- Laboratório;
- Desenvolvimento;
- Promoções.

A Central mostra:

- estado da memória;
- estado do Checkpoint Mestre;
- estado do gateway de IA;
- regra da verdade;
- pendências;
- consulta à memória;
- briefing por voz quando o TTS neural já estiver configurado.

### Integração no aplicativo

O AION é anexado dinamicamente como **índice 21 somente em sessão ADMIN**.

Os 21 destinos públicos existentes continuam intactos e com os mesmos índices.
Assim, o AION não desloca Radar, Macro, Backtest, Conta, Vendas, Investir ou Suporte.

### Permissões

ADMIN ganhou permissões AION explícitas:

- `aion:admin`;
- `aion:checkpoint`;
- `aion:development`;
- `aion:approve_publish`;
- `aion:approve_cost`.

USER e SALES permanecem sem essas permissões.

## Feature flags externas — padrão OFF

As seguintes capacidades são deliberadamente desligadas no nascimento do AION:

- modelo LLM externo;
- publicação em redes sociais;
- publicação em marketplace;
- pedidos de marketplace;
- pagamentos;
- ativação de promoções;
- deploy de produção;
- auto-merge;
- execução real em corretora.

Ligar uma integração no futuro não elimina o Guardian nem a aprovação exigida.

## Studio

A primeira interface já aceita uma ideia de conteúdo e gera briefing estruturado para:

- Instagram;
- TikTok;
- YouTube;
- vídeo vertical e adaptação horizontal;
- gancho / demonstração / prova / CTA.

Ainda não existe publicação real nestas redes neste checkpoint.

## Negócios

A primeira interface contém a meta de sustentabilidade:

- custo mensal do ecossistema;
- lucro líquido informado;
- percentual de cobertura do custo.

Os números são identificados como **informados pelo administrador**, e não como vendas confirmadas.
Mercado Livre e TikTok Shop ainda não estão conectados neste checkpoint.

## Promoções

Existe criação de rascunho para:

- 7 dias grátis;
- 30 dias grátis;
- desconto percentual;
- desconto fixo;
- limite de usos.

Ativação real depende de integração comercial futura e feature flag.

## Regra da Verdade

O AION deve:

- nunca inventar integração, venda, cliente, mercado, deploy, teste ou conclusão;
- dizer quando não há confirmação;
- separar fato, inferência, hipótese e desconhecido;
- consultar evidência aplicável antes de afirmar que algo está pronto;
- nunca chamar score de probabilidade de lucro;
- nunca declarar que publicou/cobrou/deployou sem evidência real.

## Regra Custo Zero

Padrão:

- gratuito/local/open-source/recursos já disponíveis primeiro;
- nenhuma assinatura ou upgrade automático;
- qualquer custo positivo deve mostrar valor, finalidade e alternativa gratuita;
- autorização explícita do administrador é obrigatória.

## Segurança operacional

Este bloco não altera:

- Safety Core;
- Gate operacional;
- cálculo de score;
- scanner;
- parâmetros de setup;
- ordens em corretora;
- execução real.

Trading real permanece **BLOQUEADO**.

## O que ainda NÃO está pronto

Não afirmar como pronto antes de evidência:

- provedor LLM externo completo;
- publicação automática Instagram/TikTok/YouTube;
- integração Mercado Livre/TikTok Shop;
- dados confirmados de clientes novos em tempo real;
- provedor de pagamentos;
- ativação real de cupons;
- deploy/merge automático;
- memória runtime confirmada em produção;
- AION individual por assinante;
- autonomia de desenvolvimento sem Guardian/aprovação.

## Próximo checkpoint

1. Rodar Quality e testes AION.
2. Rodar UI Smoke e Mobile DOM.
3. Corrigir qualquer regressão.
4. Revisar PR.
5. Só depois de checks verdes, mesclar.
6. Confirmar build de produção.
7. Validar AION Admin em produção privada.
8. Então avançar para provedor inteligente externo, observabilidade e integrações, uma por vez.
