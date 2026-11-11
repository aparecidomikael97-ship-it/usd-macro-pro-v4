# AtlasQuant Trader — captura real de HTML BLS CPI outubro/2026 no AM12 — 10/11/2026

**Estado:** LAB / captura de navegador local / NÃO É PRIMEIRA DIVULGAÇÃO / SEM SINAIS / SEM DEPLOY.

## Arquivo localizado

- O usuário confirmou que salvou no computador AM12, em `Downloads/livros`, o arquivo `Comunicado de Imprensa do Índice de Preços ao Consumidor - Resultados do M10 2026.html`.
- Hora de criação declarada pelo filesystem do AM12 (UTC): **2026-11-11T00:11:11.2436548Z** (20h11 do dia 10/11 no Mato Grosso). Hora da última modificação ~00:11:12Z.
- Tamanho: **1.366.766 bytes**.
- SHA-256 dos bytes guardados: **`7041541ddfc6fc155e33eab0d191e6dff6ba44c1b847921f1926cf9425126c18`**.
- O marcador local Windows `Zone.Identifier` contém o HostUrl do site oficial `https://www.bls.gov/news.release/archives/cpi_11102026.htm?utm_source=chatgpt.com`. É **indício local da origem**, não assinatura criptográfica do emissor nem comprovação de HTTP 200/da primeira disponibilidade.
- Cópia íntegra, hash idêntico, preservada em **`Documentos/AtlasQuant/Trader/BLS_CPI_20261110/BLS_CPI_OCT2026_BROWSER_SAVED_20261111T001111Z.html`**. Recibo local: `BLS_CPI_BROWSER_SAVE_RECEIPT_20261111.json`.
- Tentativa anterior por `curl` retornou **HTTP 403** e foi salva, identificada e segregada como `BLOQUEADO_HTTP_403_NAO_E_DADO_BLS.html`. Não a contar como fonte econômica.
- Os **bytes completos do HTML não foram copiados para o GitHub**, mantendo o original exclusivamente no computador. O GitHub contém apenas código, testes sintéticos e este inventário de evidências.

## Conteúdo confirmado pelo próprio HTML salvo

A página contém título **Consumer Price Index News Release - 2026 M10 Results**, identificador **USDL-26-1685** e a nota de divulgação da terça-feira **10/11/2026**. A leitura do corpo encontrou:

- **CPI-U geral: +0,4% mensal, com ajuste sazonal**, outubro/2026.
- **CPI núcleo (todos os itens exceto alimentos e energia): +0,3% mensal, com ajuste sazonal**, outubro/2026.
- **Taxa anual do CPI geral de outubro/2026 indisponível** por ausência do índice de outubro/2025; não usar 0%, consenso ou interpolação como valor oficial.
- Abrangência contextual: exatamente os **sete pares G8 com USD**; os demais 21 pares não recebem esse evento automaticamente. Nenhum efeito direcional inferido.

## Verificação do código usando o HTML real

O leitor laboratorial `atlasquant_trader_us_oct2026_cpi_release_text_guard_lab.py` inicialmente falhou em cima dos **bytes reais**, embora 13 testes artificiais passassem. Três diferenças do arquivo real foram identificadas e tratadas:

1. HTML integral de 1.366.766 bytes ultrapassava o limite antigo de 1 MiB; passou a **2 MiB**, mantendo limite de segurança.
2. O arquivo contém **seis bytes isolados `0x9d`** que invalidavam a decodificação UTF-8 estrita. Agora `surrogateescape` preserva esses bytes, não os descarta silenciosamente, conta a quantidade e rejeita mais de 16 bytes não decodificáveis.
3. O CPI núcleo **0,3% aparece duas vezes, ambas consistentes**, no resumo e na explicação detalhada. O parser passou a aceitar de 1 a 4 ocorrências *somente se os valores forem idênticos*. Múltiplos números conflitantes continuam bloqueados.

Validação no AM12 **Python 3.12**: **18 testes unitários** passaram. O teste separado `audit_saved_bls_against_gate.py` aplicado aos bytes locais reais devolveu `LAB_BLS_HTML_MONTHLY_CONTEXT_UNATTESTED`, `headline_oct2026_sa_mom_pct_body_claim='0.4'`, `core_oct2026_sa_mom_pct_body_claim='0.3'`, `headline_yoy_reported_missing_oct2025_baseline=True`, `usd_pair_count=7`, `operational_bias='AGUARDAR'` e `publishable=False`.

Não inserimos o HTML completo nas fixtures do CI: os testes automatizados usam apenas corpos sintéticos, e o teste do arquivo integral foi executado manualmente no AM12. Para reproduzir, usar a cópia local e o script de auditoria da pasta de pesquisa.

## Limites de evidência e próxima ação

- Data/hora do sistema local e `Zone.Identifier` são **metadados de máquina**, não prova externa do primeiro instante de disponibilização pelo órgão.
- Os valores são **informações extraídas dos bytes do arquivo de navegador**, não captura autenticada do HTTP 200 original. O recibo laboratorial inclui *status 200 declarado* apenas para exercitar o parser; **não** autentica uma resposta de rede.
- O comunicado foi salvo **horas após** a divulgação; nunca retroagir essa evidência para dizer que o sistema capturou o CPI no evento.
- **Sem consenso pré-divulgação auditado** (mesma métrica MoM SA e janela temporal adequada), não há cálculo de surpresa nem contribuição validada ao viés EUR/USD; direção, probabilidade, taxa de acerto e entrada permanecem `null/AGUARDAR`.
- Próxima etapa: avaliar a possibilidade de coleta reproduzível da fonte com metadados de rede realmente observados, respeitando direitos de uso; depois capturar expectativas MoM **antes** de novos eventos. Não contratar assinaturas ou habilitar robô sem aprovação.

**No-go:** não ativar worker, scheduler, publicação, score direcional nem ordens; não mesclar PR em rascunho apenas por testes de parser aprovados.
