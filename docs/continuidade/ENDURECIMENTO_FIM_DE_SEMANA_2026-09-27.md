# Endurecimento de fim de semana — 2026-09-27

Branch `cursor/weekend-hardening-5f03`, empilhada sobre a Draft PR #244
(`cursor/premium-ui-foundation-5f03`). Nada foi mesclado, publicado ou
alterado em produção, Render, secrets ou autenticação.

## Auditoria de interface (`tools/interface_audit.py`)

Crawler Playwright somente leitura. Faz login com uma conta local de teste,
percorre as áreas do Iniciante e todas as opções de "Área avançada" em desktop
(1440×1000) e celular (390×844), e registra por área: tempo, exceções
(`stException`), alertas de erro, falhas de contraste WCAG, overflow horizontal
e número de botões. A senha é lida de variável de ambiente e nunca impressa.

```
AQ_AUDIT_PASSWORD=... python3 tools/interface_audit.py --user <conta> --out /tmp/aq-audit
```

No Streamlit 1.64 o seletor é um combobox React Aria com lista virtualizada;
o crawler percorre as opções pelo teclado.

Resultado local em modo PRODUCTION, com snapshot real de `atlasquant-runtime` e
sem chaves de API: 29 áreas × 2 viewports, 0 exceções, 0 falhas de contraste
depois da correção abaixo, 0 overflow. Os "alertas de erro" contados são
intencionais: bloqueio do Safety Core, sinais de VENDA em vermelho, persistência
do scanner não configurada e bloqueios de setups não congelados.

## Correções

- Tags de multiselect: texto branco sobre `primaryColor #4fa3ff` (2,62:1) em
  Backtest e Aprender. Agora `#f8fbff` sobre `#1d4e89`.
- Proveniência após a atualização em segundo plano: os loaders gravam
  `STATUS_FONTE` nos globais da execução que iniciou o job. Depois da troca, a
  linha "Fontes/estado" ficava vazia e o banner dizia apenas "Fontes
  atualizadas", mesmo com EUA em valores de segurança. O job agora guarda o
  estado das fontes junto do pacote, e o banner lista as fontes em fallback.
  Esta correção também foi aplicada na #244.
- Cabeçalho do AION: lia `access["username"]`, mas em produção o usuário fica em
  `access["session"]`; sem `AION_ADMIN_DISPLAY_NAME` aparecia "Administrador".
- Ordenação do Radar por sessão não quebra mais com prioridade não numérica.
- Erros de fonte da atualização em segundo plano passam por `redact_text`
  antes de irem para a tela: exceções de requisição podem conter a URL com
  `api_key`. Também aplicado na #244.

## AION Central (`atlasquant_aion_workspaces.py`)

As áreas do console já existiam. O módulo novo define seis personas sobre elas:

| Persona | Área do console |
| --- | --- |
| AION Trader | 📈 Trading |
| AION Administrador | 🗂️ Secretaria |
| AION Desenvolvedor | 🛠️ Desenvolvimento |
| AION Vídeo | 🎬 Studio |
| AION Negócios | 💼 Negócios |
| AION Laboratório | 🧪 Laboratório |

Cada persona tem chave de contexto própria (`aion_ctx::<persona>::<chave>`) e
um escopo de ações. O escopo é verificado antes do Guardian e só restringe:
ordens reais, merge, deploy e leitura/escrita de secrets são negados a partir de
qualquer persona, mesmo com aprovação e feature flag.

AION Administrador mostra saudação pelo horário de Brasília ("Bom dia", "Boa
tarde", "Boa noite") com o nome de `AION_ADMIN_DISPLAY_NAME` ou, se ausente, o
usuário da sessão, e um resumo montado apenas com valores do Pulso Executivo.
Contagem ausente aparece como "não confirmado".

AION Desenvolvedor exibe a política de confiança: níveis 0 (leitura) e 1
(rascunho) são autônomos; nível 2 (branch) e 3 (Draft PR) exigem pessoa.
`auto_merge`, `auto_deploy` e autoelevação são sempre falsos. Rollback por
`git revert`, nunca reset ou force push.

## Scanner Forex — universo 28 + TOP 10

O Radar agora mantém explicitamente os 28 cruzamentos únicos das moedas G8,
mesmo quando uma fonte não retorna leitura. O TOP 10 é sempre derivado dessa
mesma população; prioridade inválida vai para o fim sem derrubar o ranking.
Índices e criptos usam rankings próprios.

O pipeline registra separadamente dados, técnica, macro, sessão, qualidade,
score e ranking. Ausência de evidência permanece `SEM DADOS`, `NÃO CONFIRMADA`
ou `BLOQUEADO`; não produz confiança nem autoriza ordem. A fila automática
prioriza pares ausentes, sem horário comprovado e expirados. O worker contínuo
externo não foi ativado porque depende de provider, credencial, cota e decisão
de infraestrutura.

## Laboratório (`atlasquant_lab_matrix.py`)

Matriz timeframe × estilo × setup, reaproveitando `atlasquant_timeframe_profiles`
(M15 e M30 intraday, H1 day trade, H4 e D1 swing, W1 position/semanal) e o
catálogo de `atlasquant_setup_validation`. Toda célula começa em
`SEM_EVIDENCIA`; só muda com um registro de evidência daquela combinação.
Registro parcial fica `EVIDENCIA_INCOMPLETA` com os campos ausentes vazios.
Nenhum backtest é executado ou simulado. A matriz está exibida na área Backtest
e no AION Laboratório, conectada aos registros reais de evidência já existentes.
Trades, win rate, expectancy, profit factor, drawdown, resultado líquido,
período, fonte e versão das regras só aparecem quando registrados. Comparações
mensais/anuais exigem pelo menos dois períodos provenientes.

PPR entrou no catálogo como "definição pendente": não há regra objetiva
documentada no projeto, então fica bloqueado para qualquer atribuição.

## Cockpit premium

Radar, Painel Mestre e Laboratório receberam cabeçalho de comando, telemetria,
hierarquia, profundidade, estados de foco/hover e responsividade. A revisão
visual cobriu desktop e celular sem carregar motores adicionais no boot.

Capturas em `/opt/cursor/artifacts/weekend-245/`: Radar, Painel Mestre,
Laboratório e AION em desktop e mobile. Nas oito telas: zero exceções, zero
falhas de contraste e zero overflow horizontal.

## AION, memória e capacidades

As seis personas estão conectadas somente a capacidades existentes e dentro do
escopo do Guardian. A memória operacional usa schema versionado, namespaces por
persona, digest, limites e recuperação vazia/parcial de checkpoint corrompido
ou incompatível. Contexto de Trader, Desenvolvimento, Vídeo, Negócios,
Laboratório e Administrador não é compartilhado.

Vídeo/clipagem possui pipeline provider-neutral para conteúdo autorizado,
transcrição, cortes, roteiro, legendas, formatos, thumbnail, metadados e fila de
aprovação. Direitos desconhecidos bloqueiam o fluxo; voz e providers ausentes
aparecem como não configurados. Negócios possui modelos de funil, CAC/LTV,
catálogo e margens sem gasto, campanha ou publicação. Vendas preserva autorização
SALES/ADMIN independentemente da política visual do menu.

## Painel Mestre executivo

A visão executiva reúne a população Forex de 28 pares e seu TOP 10, índices,
DXY e criptos em rankings separados, contexto macro/fundamental, evento e
pré-notícia, alinhamentos, divergências, fontes em fallback e oportunidades
liberadas apenas para estudo. Micro/fluxo, geopolítica e sentimento aparecem
como `SEM DADOS` quando não há fonte; o painel não preenche lacunas.

## Investimentos

O comparador avançado aceita produtos observados com taxa bruta/líquida, prazo,
liquidez, risco, custos, fonte e timestamp. Sem feed real exibe
`SEM PRODUTOS CONFIRMADOS`; não estima rentabilidade líquida e não cria ranking
de recomendação personalizada.

## Commits desta continuação

- `794556cd` — pipeline/ranking determinístico dos 28 pares;
- `edcafdd4` — fila automática fail-closed;
- `4a5d713b` — matriz do Laboratório ligada às evidências;
- `82cb9cf5` — segunda rodada do cockpit premium;
- `9fa2f211` — personas AION, memória e capacidades seguras;
- `235a7e36` — visibilidade de Vendas segura por papel;
- `48b326a7` — visão executiva do Painel Mestre;
- `b51441d4` — comparação de investimentos proveniente;
- `a666bcb6` — inclusão dos novos testes no gate de qualidade.

## Limites e diferença para produção

Todo o trabalho está apenas na Draft PR #245, empilhada sobre a Draft PR #244.
Produção não foi alterada. Nenhum merge, deploy, secret, credencial, ordem real,
pagamento, compra, anúncio ou publicação externa foi executado. Dependências
humanas permanecem em `PENDENCIAS_MIKAEL.md`.

## Medições locais (processo novo, sem chaves de API)

| Etapa | Desktop | Celular |
| --- | --- | --- |
| Formulário de login | 1,9 s | 1,4 s |
| Login até o shell | 1,0 s | 1,4 s |
| Primeira abertura do Avançado (cache) | 1,7 s | 1,6 s |
| Troca de área (mediana) | 0,74 s | 0,72 s |
| Abrir AION | 0,74 s | 0,79 s |

São medições em máquina local; a latência do Render não está incluída.

## Qualidade pós-alterações

- Compilação integral: aprovada.
- Suíte local do workflow: **2231 testes aprovados**.
- Auditoria final em processo local PRODUCTION:
  - ADMIN: 29 áreas em desktop e mobile;
  - USER: 28 áreas em desktop e mobile;
  - **0 exceções, 0 falhas de contraste e 0 overflow horizontal**;
  - alertas classificados são estados fail-closed intencionais (Safety Core,
    fonte em fallback, scanner sem persistência externa, regra não congelada ou
    acesso SALES bloqueado), não exceções de renderização.
- Benchmark final:
  - login até shell: ADMIN 1,44 s desktop / 1,10 s mobile; USER 1,45 s /
    1,10 s;
  - abertura do Avançado: ADMIN 1,40 s / 1,36 s; USER 1,43 s / 1,59 s;
  - troca de área mediana: ADMIN 0,714 s / 0,694 s; USER 0,694 s / 0,698 s;
  - AION ADMIN: 0,763 s desktop / 0,800 s mobile.
  Esses números preservam ou melhoram o baseline anterior; não foi observada
  regressão relevante.
- Evidência final: `/opt/cursor/artifacts/weekend-245-final/admin/` e
  `/opt/cursor/artifacts/weekend-245-final/user/`, incluindo relatórios JSON e
  screenshots de todas as áreas avançadas em desktop/mobile.
- Bugs encontrados e corrigidos nesta continuação:
  - import local de `PREMIUM_CSS` causando `UnboundLocalError` no Radar;
  - novos testes fora do gate do workflow;
  - comparador novo alterando indevidamente a jornada Iniciante;
  - normalização de estado de fonte em texto não reconhecendo os marcadores
    existentes.
- O log da suíte ainda contém o diagnóstico seguro
  `PAIR_INTELLIGENCE_RUNTIME / KeyError` gerado por um cenário AppTest que
  valida o fallback do Radar avançado; os testes confirmam que a falha fica
  isolada e não amplia permissão.
