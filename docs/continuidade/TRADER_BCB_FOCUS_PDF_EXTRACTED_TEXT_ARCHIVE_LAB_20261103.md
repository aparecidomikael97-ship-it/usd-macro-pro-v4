# AtlasQuant Trader — arquivo de EXTRAÇÃO TEXTUAL do Focus BCB 30/10 (LAB, 03/11/2026)

**Publicação oficial:** [BCB, Focus 30/10/2026](https://www.bcb.gov.br/publicacoes/focus/30102026) (a página exibe a data de publicação **03/11/2026**), link direto para [o PDF de duas páginas](https://www.bcb.gov.br/content/focus/focus/R20261030.pdf).

## Evidência nova realmente arquivada

- `docs/continuidade/R20261030_BCB_PDF_TEXT_EXTRACTED_LAB_20261103.txt` contém o **texto extraído por um leitor de conteúdo público diretamente da URL do PDF oficial** em 03/11. **Não é o arquivo PDF original, nem transcrição certificada pelo BCB.**
- Identificador Git do blob de TEXTO extraído: `7123568a4140fb751c757f8fc423538d0905b18c`. O teste pode recalcular `SHA-1 Git blob = SHA1("blob " + comprimento_bytes + NUL + bytes_texto)`, detectando alterações nesse texto após versionamento. **Isto não é SHA-256 do PDF e não autentica o servidor do BCB nem o horário da captura.**
- O download binário via ambiente disponível falhou (acesso à URL do PDF pelo downloader e resolução de rede indisponíveis), portanto o PDF original **NÃO foi arquivado**. `original_pdf_sha256=null`, sem assinatura de origem ou recibo HTTP independente.
- A edição oficial do BCB foi comparada anteriormente com o Focus 23/10 e as reportagens de 03/11. A nova rotina cruza os **números presentes no próprio texto preservado** com as expectativas congeladas em `TRADER_BCB_FOCUS_20261030_OFFICIAL_REVIEW_LAB.json`.

## Verificação reprodutível

O validador `atlasquant_trader_bcb_focus_extracted_text_lab.py`:
- Confere que há as duas marcações de página do PDF e o título de 30/10/2026.
- Extrai, em cada linha da página 1, tríades "há 4 semanas", "há 1 semana", "hoje" e a contagem de respondentes dos últimos 30 dias, para IPCA, PIB, câmbio R$/US$ e Selic em **2026, 2027 e 2028**.
- Compara as 12 medianas anuais e respondentes com a transcrição versionada.
- Extrai da página 2 as **oito** medianas para IPCA outubro/novembro/dezembro/inflação 12m suavizada, câmbio novembro/dezembro e Selic novembro/dezembro.
- Recusa adulteração de texto, mudança da tabela, linha ausente, valor e respondentes incompatíveis, falsa alegação de PDF binário arquivado, consulta retrospectiva antes da janela conservadora 03/11 15h UTC, fuso ingênuo e dados inválidos.
- Reporta `12 annual_matches` e `8 monthly_matches` somente para texto documental consistente. **Nunca** habilita viés direcional, probabilidade, OOS real, ordens, Render ou Worker.

O texto do PDF é um artefato rastreável para **conferência posterior**, não licença comercial, garantia de tempo de publicação, notícia em tempo real, execução sobre preços nem recibo histórico do BCB. O corte 15h UTC é controle conservador escolhido para a leitura LAB, e não comprovação do horário exato da consulta.

## Relação com o Copom de 04/11

O checkpoint pré-Copom `1281f218` permanece **intacto** como versão congelada antes do evento. O novo texto melhora apenas o rastro de fonte das expectativas registradas; **não altera** as hipóteses (manutenção 13,75% como cenário modal entre respondentes da Reuters, corte de 0,25 pp como cenário alternativo, outros). A Selic Focus novembro/2026 **13,50%** é expectativa de **fim de mês**, nunca probabilidade da decisão de 04/11. Não registrar resultados futuros antes do comunicado.

Testes: `test_atlasquant_trader_bcb_focus_extracted_text_lab.py` integrados à CI Quality. Se a CI falhar, a fonte não está homologada. O PDF original ainda precisa de download binário confiável, cálculo de hash e confirmação independente para elevar o nível de proveniência.

**PR #1803 DRAFT · LAB / HARD NO-GO · R$ 0 extra · sem merge, deploy, Worker, scheduler, ordens ou mudanças do Render/UI.**
