# AtlasQuant Trader — histórico de expectativa monetária USD (Atlanta Fed, LAB)

Checkpoint UTC 05/11/2026, continuidade da PR #1815 depois da proteção de
consenso PIT (`5aaf687c`). **Sem custo novo, merge, deploy, Worker, cron,
publicação de dados, conexão ao Radar ou negociação real.**

## Fonte pesquisada

- [Federal Reserve Bank of Atlanta, Market Probability Tracker](https://www.atlantafed.org/research-and-data/data/market-probability-tracker)
  oferece histórico XLSX e código-fonte para pesquisa.
- Mede distribuições implícitas nas **opções de futuros trimestrais sobre
  SOFR** da CME, com referência à **média SOFR de três meses**, e atualiza
  as estimativas diariamente, normalmente com dados do dia anterior.
- **NÃO** mede diretamente a faixa-alvo dos Fed Funds, a surpresa exata da
  decisão do FOMC ou um consenso de analistas.
- A [API FedWatch CME](https://www.cmegroup.com/market-data/market-data-api/fedwatch-api.html)
  é distinta e comercial. Não foi contratada, chamada nem incorporada.

## Captura real no AM12 (somente pesquisa privada)

Uma consulta manual `HEAD` ao arquivo oficial retornou **HTTP 200**,
`application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`, tamanho
`7199234` bytes. Uma única requisição de download HTTPS foi realizada sem
redirects, com arquivo de destino único, sem alterar os ZIPs anteriores.

- URL original:
  `https://www.atlantafed.org/-/media/Project/Atlanta/FRBA/Documents/research-and-data/data/market-probability-tracker/mpt_histdata.xlsx`
- Início da captura (relógio do AM12): `2026-11-05T01:23:06.5291724Z`.
- Arquivo privado: `evidence/atlantafed_mpt_histdata_20261105T012306520Z.xlsx`
  na pasta do projeto `AtlasQuant_Trader_G8_LAB_20261104` no AM12.
- Tamanho observado: **7.199.234 bytes**.
- SHA-256 do XLSX original:
  `76f9288f2a3c06d493e053a1df950915658aa1bf077211d91439d1f95b79f18c`.
- Estrutura do arquivo: abas `LICENSE`, `DICTIONARY` e `DATA`.
- Releitura offline Windows: **319.643 registros de dados**, de
  `2023-03-29` até `2026-11-03`; campos categorizados como taxas de
  média/moda/percentis e probabilidades de alta/corte, todos para
  **janelas trimestrais SOFR**. Os valores financeiros originais não foram
  copiados para o GitHub.
- Uma observação histórica inicial (`2023-03-29`) e um contrato trimestral
  (`2023-06-21`) foram selecionados para testar a estrutura, sem usá-los
  como previsão ou direção de câmbio.

### Restrição material de licença

O texto da aba `LICENSE` aparece em um **objeto de desenho do Excel**, e
não em células ordinárias. A licença do arquivo limita o uso a propósitos
**pessoais e educacionais**; dados da CME são usados pelo Atlanta Fed sob
permissão específica. O código reconhece essa restrição e exige sua
presença; não assume direito de uso comercial, redistribuição ou
integração nos produtos oferecidos futuramente a clientes.

Por isso, **nenhum XLSX ou linha de preços/licença foi enviado ao GitHub**.
O documento no repositório registra somente proveniência, hash, estrutura,
testes e limitações. O arquivo bruto continua privado no AM12.

## Leitor novo, estritamente offline

O módulo `atlasquant_trader_us_mpt_history_lab.py`:

1. lê bytes XLSX fornecidos pelo usuário; **não faz HTTP**, não salva nem
   edita planilhas; limita tamanho, quantidade de linhas, partes ZIP, XML;
2. valida nomes `LICENSE/DICTIONARY/DATA`, campos da aba de dados,
   datas, identificadores do contrato e unidades (pontos-base vs `%`);
3. lê o texto de licença no *drawing* do Excel e bloqueia documento sem
   restrição reconhecida, em vez de presumir reutilização comercial;
4. seleciona uma data de observação e uma janela trimestral específicas,
   recusando duplicidade, faixa incoerente, números inválidos ou ausentes;
5. retorna apenas `LAB_MPT_QUARTERLY_SOFR_RESEARCH_ONLY`, sem autorizar
   consenso pré-evento, dados históricos ponto-no-tempo, publicação, viés
   FX ou operação. Uma CLI manual requer `--confirm-personal-lab-read`
   e imprime somente metadados, sem republicar as estatísticas licenciadas.

**A data da observação na planilha não comprova que aquela vintage exata
estava pública naquele dia.** O arquivo histórico baixado em novembro/2026
pode ter sido calculado ou revisado posteriormente. O próprio horário
local do AM12 não é testemunha institucional independente.

## Testes e próximos bloqueios

- Testes sintéticos em memória: conteúdo válido, licença ausente, ZIP
  inválido, data futura, unidades, duplicidade, ausência e troca de janela.
- Leitor executado contra o **XLSX real** no AM12, com conclusão de
  `state=LAB_MPT_QUARTERLY_SOFR_RESEARCH_ONLY`, `fx_bias=null`,
  `trade_authorized=false` e `commercial_reuse_authorized=false`.
- Código e testes adicionados à Quality CI da PR em DRAFT.
- Próximo foco: pesquisar alternativa EUR de expectativas pré-evento,
  validar licença e vintages históricas; **sem contratar dados pagos**.

**HARD NO-GO permanece.**
