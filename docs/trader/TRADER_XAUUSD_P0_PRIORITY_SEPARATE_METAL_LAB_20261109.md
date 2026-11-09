# AtlasQuant Trader — XAU/USD (ouro) como prioridade P0 separada (LAB)

**Decisão aprovada pelo usuário em 09/11/2026.** Adicionar XAU/USD à prioridade de desenvolvimento do Trader, junto a Forex e índices. Esta entrega registra **a prioridade e o contrato mínimo de pesquisa**; não declara que o painel já mostre ouro ou que seu viés esteja operacional.

## Limite arquitetural obrigatório

- Manter **28 pares Forex G8 e 56 posições por rodada D1/W1** inalterados. Ouro **não é** o 29º par Forex, uma nona moeda G8 nem um componente do cálculo da força relativa das moedas.
- Identificador separado: `METAL:XAUUSD`; símbolo de pesquisa `XAUUSD`, apresentação `XAU/USD`. O símbolo negociável, possível sufixo e horário dependem do servidor Pepperstone/MT5 e **não estão verificados**.
- Vieses planejados: **D1 e W1: ALTA / BAIXA / AGUARDAR**. **MN1: contexto** até haver validação própria. Escore 0–10, se futuramente existir, não é probabilidade de acerto.
- Manter um histórico e uma validação **do ouro separados** dos resultados estatísticos de Forex e índices. Nenhum sinal repetitivo ou fabricado.

## Evidências a integrar depois

`USD_AND_DXY`, `US_REAL_YIELDS`, `FED_AND_RATE_EXPECTATIONS`, `US_MACRO_RELEASES`, `GOLD_FLOWS_AND_DEMAND`, `GEOPOLITICAL_RISK`, `XAUUSD_BROKER_PRICE_AND_SESSION`, `XAUUSD_PROSPECTIVE_OUTCOMES`.

São grupos de análise; não são pesos de uma fórmula já validada. Movimentos do ouro podem mudar conforme o regime. Não assumir que juros subindo sempre derrubam ouro ou que dólar caindo sempre o eleva. Notícias precisam de publicação, captura e versão ponto-no-tempo verificadas.

## Critérios antes de liberar um viés real

1. Verificar disponibilidade da cotação XAUUSD no broker, timezone, sessões, velas fechadas, spread e custos do instrumento sem interferir no MT5 do usuário.
2. Comparar fatores macro, financeiros e geopolíticos com fontes e horários de publicação autenticados; incerteza gera `AGUARDAR`.
3. Fixar previsões do ouro **antes dos alvos**, em campanha e registro externo próprios, com abstenções preservadas no denominador.
4. Validar resultados fora da amostra, calibração, cobertura, riscos e custos de execução **separadamente**; ouro não herda a meta ou a precisão de Forex.
5. Integrar ao Radar e ao Painel Mestre apenas após testes e aprovação específica.

## O que o código faz nesta fase

`atlasquant_trader_xauusd_priority_lab.py` define o cadastro de pesquisa P0 do ouro e confere um inventário documental de oito domínios. Mesmo que todos os recibos fornecidos pelo chamador sejam plausíveis, retorna `LAB_XAUUSD_DOCUMENTARY_COVERAGE_UNATTESTED`, `operational_bias=AGUARDAR`, `publishable=False` e `trade_authorized=False`. Não autentica fontes, não lê mercado, não cria sinais nem faz operações. Os testes verificam que XAUUSD **continua excluído** do normalizador de Forex e da lista FX_28.

**NO-GO:** nenhuma ordem real, atualização do Radar publicado, custo adicional, merge ou promessa de assertividade. A PR #1851 segue LAB/draft até autorização distinta.
