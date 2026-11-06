# AtlasQuant Trader — schema de HICP 2026 e diagnóstico `coicop18` (LAB)

**06/11/2026 — pesquisa documental e fixtures sintéticas; zero resposta real de API capturada.**

## Novo achado relevante ao viés EUR

O Eurostat documenta a introdução da **ECOICOP versão 2 / COICOP 2018** para os
HICP divulgados em 2026. Na [visualização oficial de pesos de HICP](https://ec.europa.eu/eurostat/databrowser/view/prc_hicp_iw__custom_19973032/bookmark/table?bookmarkId=fdf99756-185b-4f25-83f8-cb3245814c9d&c=1770200763000&lang=en),
um dataset **vizinho** da mesma família apresenta a dimensão **`COICOP18`**.
A [nota oficial de migração](https://ec.europa.eu/eurostat/databrowser-backend/api/public/explanatory-notes/get/Info_note_HICP_COICOP18_20260128.pdf)
explica a mudança de classificação e os novos códigos de datasets.

**Inferência, não fato confirmado:** é plausível que a dimensão técnica do
`prc_hicp_fpd` também seja `coicop18`, mas **não temos a resposta API** para
verificar. O laboratório anterior testava um nome provisório `coicop`:
isso não deve virar contrato de produção nem ser aceito como fato. `RCH_A`,
`CP00` e `FIN` seguem **somente como códigos fictícios de teste**.

## O que o novo diagnóstico faz

`atlasquant_trader_eurostat_fpd_ea21_schema_probe_lab.py` inspeciona **apenas
um arquivo JSON-stat recebido manualmente**. Suporta a hipótese `coicop` ou
`coicop18` **somente em quarentena**, para deixar explícita a distinção entre
dois contratos candidatos. Não tenta converter de um código para outro.

Faz validações rigorosas de: origem *alegada* no URL, recorte único EA21 para
setembro/2026, filtros do URL consistentes com dimensões do corpo, 64 KiB
máximos, categoria e índice, chaves únicas, datas declaradas coerentes,
contexto documental SHA-pinned e piso conservador de captura em 17/10 UTC.

**Nunca** devolve valores numéricos, transforma em inflação, calcula viés,
atribui ponto de força ao EUR, ou atesta que o URL e timestamp declarados são
verdadeiros. O estado positivo possível é somente
`LAB_SUPPLIED_SCHEMA_PROBE_QUARANTINED_NOT_VERIFIED`. Se há inconsistência:
`LAB_BLOCKED`.

O resultado traz unicamente IDs e códigos de dimensão **não autenticados**,
hash dos bytes fornecidos e flags de proibição de uso. O probe também não
atesta que a série consultada representa **taxa anual geral (all-items)**:
isso requer conferir as definições reais de `unit`, `coicop18` e `release`
na resposta oficial e na documentação da estrutura.

## Próxima evidência necessária

Obter, por rota legítima e com registro de URL, certificado TLS, hora e
hash, uma resposta pequena de `prc_hicp_fpd`. O acesso direto pela ferramenta
de pesquisa não disponibilizou o JSON nesta sessão. Uma cópia enviada pelo
usuário pode ser **inspecionada**, mas **não pode ser tratada como prova
independente da sua origem**. Não buscar atalhos para restrições de rede.

Até lá: **AGUARDAR D1/W1 nos 28 pares**, nenhuma previsão validada, nenhuma
alegação de precisão, sem merge, publicação, Worker, agendamento, transação,
solicitação HTTP automatizada ou custo novo.
