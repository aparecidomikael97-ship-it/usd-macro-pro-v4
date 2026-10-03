# AtlasQuant — revisão visual das referências

Branch: `integration/ecosystem-visual-fidelity-20261003`.
Base: `7d3f979c555b4f4712aa6ced9fceb59f4e83d915`.
Sem merge, deploy, chamadas a produção ou alteração de credenciais.

## Implementação

A arte fornecida pelo usuário é o fundo real dos cockpits. Central e Negócios
foram codificados em WebP sem perda; Trader mantém o JPG original, sem
recodificação. A imagem dupla foi dividida em dois recortes sem perda de
1048 × 748 pixels, removendo somente o divisor branco entre as telas.
`assets/ecosystem_reference/manifest.json` registra hashes, dimensões e recortes.
Os testes com os anexos originais verificam igualdade dos pixels decodificados.

Os ícones de menu são sprites sem perda recortados da referência, com hashes
e coordenadas registrados no mesmo manifesto.

Os cartões, painéis, abas superiores, menus e ferramentas têm botões DOM
proporcionais com rótulos acessíveis e foco de teclado. O componente Streamlit
V2 envia eventos dentro da sessão atual. O servidor valida cada destino contra
o ambiente e o gate existente. Conteúdo escolhido substitui a home na área
principal e aparece no topo. Não há faixa duplicada de acessos.

Trader tem os 19 acessos solicitados. Negócios e Investimentos não aparecem em
seu menu; o seletor analítico antigo também omite atalhos de outros ambientes,
sem alterar os índices do dispatcher. O AION interno é especializado por
ambiente. Os oito papéis do núcleo são responsabilidades de um único AION Core.

Painel Mestre abre com quatro resumos essenciais. Os 28 pares ficam em seção
secundária; Radar destaca as dez primeiras posições da estrutura visual.
As posições e direções ainda aguardam ranking validado: não são sinais atuais.
Os demais módulos abrem suas prévias no topo. As análises Trader já existentes
podem ser abertas explicitamente, reutilizando a navegação anterior e oferecendo
retorno imediato ao cockpit. Vídeos, chat e integrações sem conexão continuam
identificados como prévias, sem simular resultados.

## Desempenho e preservação

Central, Trader e os ambientes privados retornam antes de carregar snapshots,
scanner ou providers. A arte é lida do repositório e mantida em cache local. Os ícones vêm de pequenos
sprites recortados da própria referência. O fundo é herdado por CSS, sem
repetir a URL grande em cada cartão, e é omitido dos painéis internos.
Somente o ambiente solicitado é montado; os dois recortes evitam enviar a imagem
dupla em cada abertura. O caminho analítico existente mantém seu cache.

Nenhum arquivo de autenticação, RBAC, Safety Core, provider ou execução foi
alterado. O teste de produção controlada usa o login real com fixtures, preserva
username, role e authenticated_at durante as trocas e exige zero chamadas de
snapshot e refresh nas homes. O preview isolado usa identidade de revisão e não
é um mecanismo de entrada no aplicativo de produção.

## Validação

- Suíte de interface, startup, fluxo autenticado, acesso e bridge: 142 testes e
  48 subtestes passaram.
- Regressões após as correções de CI: 109 testes e 26 subtestes passaram.
- Contratos da nova interface após os recortes: 20 testes passaram.
- Chromium real: 1440 × 1000 e 390 × 844; cinco telas, cartões, menus, ferramentas,
  retorno, posição do título, ausência de overflow e movimento reduzido.
- O navegador exige decodificação bem-sucedida da imagem. Essa verificação
  detectou e corrigiu o limite de 1 MiB das custom properties do Chromium;
  a imagem agora é aplicada por uma propriedade CSS normal.
- `py_compile` dos arquivos de execução e `git diff --check` passaram.

A medição final fica em `visual_review/timings.json`, junto das capturas.
São medidas do preview local, não tempos medidos em produção. Uma execução
anterior com outras suítes concorrentes levou 14,2 s na abertura fria e
0,93–6,02 s nas trocas; o relatório final registra a execução após os recortes.

## Medição final local

Abertura fria do preview, incluindo inicialização do frontend Streamlit: 11.653 s.

| Troca de ambiente | Tempo |
| --- | --- |
| Trader | 0.471 s |
| Negocios | 0.599 s |
| Investimentos | 1.082 s |
| Aion | 1.122 s |

A varredura final de cliques terminou sem erro de JavaScript ou de Streamlit em
186,04 s. A primeira abertura fria ainda inclui o custo do framework e não é
uma medição da Central após o login em produção.

## Diferenças objetivas que permanecem

1. Menus, identidade autenticada, retorno à Central e seletor de modo são DOM
   sobre a arte: os rótulos e o espaçamento mudam onde os requisitos exigem
   remover atalhos cruzados e acrescentar funções.
2. Trader substitui os títulos Investimentos e Treasury pelos acessos
   Painel Mestre e Diário. As ilustrações originais desses cartões permanecem.
3. Há uma faixa discreta explicando que os dados pintados na imagem são
   ilustrativos. Cotações, horário, status e gráficos da arte não são dados vivos.
4. Mobile usa menu recolhível e cartões recortados da arte, pois não foi
   fornecida uma referência móvel. Sua composição difere da tela desktop.
5. Painéis internos usam layout funcional de prévia; não existe referência
   aprovada para essas telas. Dados analíticos e players ainda não conectados
   não são apresentados como funcionalidades completas.
6. A arte tem a resolução dos anexos: a ampliação pode suavizar textos pintados.
   Não houve reconstrução vetorial ou criação de novas ilustrações.

Não há alegação de igualdade pixel a pixel da interface inteira. A igualdade
verificada é da arte original, antes dos controles e adaptações descritos acima.

## Arquivos alterados

- Execução/interface: `atlasquant_reference_ui.py`, `atlasquant_central_hub_ui.py`,
  `atlasquant_premium_shell.py`, `usd_macro_pro_v4_cloud.py`.
- Testes: `test_atlasquant_reference_ui.py`, `test_atlasquant_reference_browser.py`,
  `test_atlasquant_central_hub_ui.py`, `test_atlasquant_premium_shell.py`,
  `test_atlasquant_production_admin_flow.py`, `test_atlasquant_ui_v1.py`.
- Arte: `assets/ecosystem_reference/central.webp`, `trader.jpg`, `negocios.webp`,
  `investimentos.webp`, `aion.webp`, `trader_nav.webp`, `negocios_nav.webp`,
  `investimentos_nav.webp`, `aion_nav.webp`, `manifest.json`, `reference.css`.
- Revisão/CI: `tools/reference_ui_preview.py`,
  `.github/workflows/atlasquant-reference-ui.yml`,
  `.github/workflows/atlasquant-ui-smoke.yml`,
  `.github/workflows/mobile-dom-stability.yml`,
  `.github/workflows/quality-tests.yml` e este relatório.

As capturas locais em `visual_review/` ficam fora do commit. A CI produz suas
próprias capturas e as publica somente como artefato do workflow.

## Reproduzir localmente

```powershell
python -m streamlit run tools/reference_ui_preview.py --server.address 127.0.0.1 --server.port 8772 --server.headless true
python -m pytest -q test_atlasquant_reference_ui.py
python -m pytest -q -s test_atlasquant_reference_browser.py
```

O teste de navegador requer Playwright/Chromium e inicia seu próprio servidor
em porta loopback livre. O workflow `atlasquant-reference-ui.yml` executa apenas
CI em pull requests e salva as capturas como artefato; não publica o aplicativo.
