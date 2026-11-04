# AtlasQuant Trader — ligação calendário/consenso à fonte oficial (LAB)

**Prioridade:** viés dos 28 pares, 8 moedas, D1 principal, W1 confirmação,
MN1 contexto, com macro, micro, geopolítica, notícias e calendário.
**Não é prioridade:** FVG/OB ou execução de trade.

## Contrato novo

`atlasquant_trader_macro_pit_documentation_link_lab.py` combina, sem HTTP:

1. Um evento sintético validado pelo contrato point-in-time existente
   `atlasquant_trader_macro_surprise_pit_lab.py`.
2. A referência documental oficial do grupo/moeda no catálogo G8 de **32
   posições** (`atlasquant_trader_g8_country_macro_catalog_lab.py`).

O contrato só aceita o `documentation_url` **exatamente correspondente** à
moeda, ao grupo (inflação, emprego, juros, atividade) e ao indicador/unidade
pré-selecionado. Rejeita fonte trocada, indicador não preselecionado, unidade
incorreta, declaração extra de autenticidade e dados futuros incorporados
a uma previsão pré-divulgação.

## Cadeia causal explícita

| Estágio | Tratamento do dado neste LAB |
|---|---|
| Valor anterior | Aceito somente como declaração sintética datada |
| Consenso pré-evento | Aceito se declarado antes do corte da pesquisa |
| Divulgação | Só pode entrar após o horário de publicação/captura informado |
| Surpresa | `actual-consensus` com unidade e deadband fixados; ainda sintética |
| Fonte oficial | URL canônica é somente identidade documental, não origem autenticada |
| Leitura de moeda | **UNDETERMINED / AGUARDAR**, sem inferir ALTA/BAIXA |

Uma inflação acima do consenso **não obriga** alta da moeda: surpresa,
expectativa de juros, posicionamento, reação e regime geopolítico são etapas
distintas, além de qualquer preço observado.

## Verdade e permissões

Mesmo quando a URL coincide, sempre ficam `source_content_authenticated=false`,
`release_and_consensus_vintages_attested=false`, `provider_license_verified=false`,
`can_feed_live_radar=false`, `trade_authorized=false`, `publishable=false`.
O vínculo não baixa documentos, não usa API, não ativa Worker, não opera e
não altera o aplicativo.

Antes de promover um dado para compor o viés D1/W1/MN1 será necessário
capturar a **publicação original**, demonstrar disponibilidade **point-in-time**,
fonte do consenso, convenção da série, direitos de uso, transmissão econômica
plausível e teste fora da amostra. Sem isso, o viés operacional permanece
**AGUARDAR**.

**Checkpoint:** PR #1803 DRAFT/LAB/HARD NO-GO, sem custos, Render, merge,
AION, Worker, agendamento ou operações reais.
