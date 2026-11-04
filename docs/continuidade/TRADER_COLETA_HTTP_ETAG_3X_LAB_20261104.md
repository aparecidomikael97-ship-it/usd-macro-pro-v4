# AtlasQuant Trader — contrato HTTP oficial condicional, sem coleta real (LAB)

## Foco do Checkpoint Mestre

Entrega vinculada somente à investigação de **força relativa e viés diário,
semanal e mensal dos 28 pares Forex G8**, com macro, micro, notícias,
geopolítica e calendário econômico explicados por evidências auditáveis.
Não prioriza FVG/OB, M15 ou sinais de compra e venda.

Na fase grátis ficam **três revisões completas por dia** (06:35, 10:45 e 17:15,
horário de Brasília), ainda **planejadas e não ativadas**. Nenhuma coleta
extra, serviço em tempo real, atualização horária, cobrança ou Render foi
autorizada nesta revisão. AION/Worker seguem HARD NO-GO.

## Bloco implementado

O módulo `atlasquant_trader_official_http_collection_contract_lab.py` é
**totalmente offline**. Ele prepara uma descrição não executável de GET para
uma das fontes RSS pesquisadas. O escopo inicial (BLS/Fed/BCE, USD/EUR)
foi ampliado documentalmente para nove links BoE/BoJ/SNB/RBA/BoC/StatCan:
**14 leads em sete moedas**, com NZD pendente. Inclui URL fixa, cabeçalhos
`Accept`, `If-None-Match` (ETag) e
`If-Modified-Since` (Last-Modified) **somente se** houver cache anterior
compatível; limite de oito segundos **para futura implementação**, teto de
256 KiB e política de **nenhum redirecionamento automático**.

Um segundo método reconcilia **respostas HTTP fornecidas pelo chamador**, sem
fazer requisição alguma. A matriz de comportamento documentada é:

| Condição informada pelo chamador | Resultado documental de LAB | Limite |
|---|---|---|
| HTTP 200 com MIME XML, URL fixa e RSS íntegro | Leitura dos itens, hash e ETag; comparação de revisões quando existir captura anterior | Não autentica origem, notícia atual nem direção cambial |
| HTTP 304 condicionado com cache anterior | Registra alegação de conteúdo inalterado | Não comprova que o noticiário está atualizado; não recicla itens como novidades |
| HTTP 429 | `LAB_SOURCE_RATE_LIMITED` | Não agenda tentativa automática |
| HTTP 5xx | `LAB_SOURCE_UNAVAILABLE` | Não converte notícia antiga em notícia ao vivo |
| HTTP 3xx (exceto 304) | `LAB_REDIRECT_BLOCKED` | Endereço novo exige revalidação humana |
| Status não previsto, HTML, fonte diferente, XML inseguro, ETag injetado ou cache cruzado | Resposta rejeitada | Não altera o viés |

Os marcadores de confiabilidade permanecem falsos mesmo nos cenários 200 e
304: origem autenticada, latência real verificada, cobertura G8 completa,
`live_news`, viés operacional, publicação e negociação. **Todas as respostas
são sintéticas/caller-supplied**, não equivalem a uma conexão TLS verificada.
O registro de cache é apenas uma receita de persistência futura: nenhum
arquivo, banco ou notícia real é gravado.

## O que ainda falta para usar no aplicativo

1. Validar o comportamento real dos feeds e respectivos termos de uso,
   proveniência TLS, condições de redirecionamento, conteúdo e datas.
2. Implementar transporte de leitura com guarda de credenciais, custódia do
   payload original, monitoramento de falhas e persistência verificável.
3. Homologar os XMLs reais, licença e custódia dos novos links de GBP, JPY,
   CHF, AUD e CAD; resolver o lead NZD ainda pendente, cruzando notícias com
   calendário e condições macro/micro/geopolíticas.
4. Medir o atraso e o comportamento de cada fonte nas **três janelas
   gratuitas**, sem prometer atualização a cada evento; calibrar o impacto no
   viés D1/W1/MN1 em teste fora da amostra.
5. Revalidar segurança/qualidade e pedir autorização específica antes de
   ativar qualquer coleta programada, alterar serviço publicado ou custo.

## Testes

```sh
python -m unittest -q \
  test_atlasquant_trader_official_http_collection_contract_lab.py \
  test_atlasquant_trader_official_rss_capture_lab.py
```

As provas incluem: GET fixo sem execução, 200 sintético, ETag condicional,
304 com relatório anterior, diff de revisão documental, 429/5xx, host
fraudulento, cache de outra fonte, MIME HTML, DTD/ENTITY, cabeçalhos com
CRLF, plano adulterado, relógio inválido e teste sem chamadas de rede.
Resultados locais não substituem os checks remotos do GitHub.

**Governança:** PR #1803 DRAFT. Nenhum merge, deploy, Render, cron, Worker,
ordem ou cobrança. BCE continua apenas como referência diária matemática
dos pares; não fornece preços executáveis de M15.
