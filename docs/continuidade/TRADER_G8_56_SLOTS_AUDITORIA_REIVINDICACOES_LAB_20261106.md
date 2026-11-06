# AtlasQuant Trader — auditoria separada das 56 vagas prospectivas (LAB, 06/11/2026)

## Avanço

O registro do universo G8/28 pares × D1/W1 de 08/11 permanece **inalterado**, com 56 vagas sem previsão. Foi criado `atlasquant_trader_fx_g8_cohort_claims_lab.py`, um auditor **offline** para futuras reivindicações de previsão ou abstenção inseridas manualmente em arquivo separado. Ele não produz previsões, não consulta fontes, não cria arquivos, não publica timestamps externos e não acessa MetaTrader.

O objeto de entrada exige `schema=ATLASQUANT_TRADER_FX_G8_COHORT_CLAIMS_LAB_V1`, `research_kind=MANUAL_RESEARCH_CLAIMS_UNATTESTED`, `cohort_id`, `cohort_sha256` e `entries` (uma lista de 1 a 56). Cada entrada precisa identificar **exatamente** um `slot_id` fixado no manifesto original e conferir par e horizonte. A auditoria rejeita posições duplicadas, pares trocados, campos desconhecidos, JSON duplicado, horários inválidos, criação alegada após o limite pré-sessão e assinaturas de evidência malformadas.

Por entrada, `direction_claim` pode ser:

| Valor | Contagem | Restrições adicionais |
|---|---|---|
| `ALTA`/`BAIXA` | Reivindicação direcional **não autenticada** | Modelo de pesquisa pré-declarado, SHA-256 da evidência alegada e corte dos dados anterior à criação |
| `NEUTRO` | **Abstenção**, nunca acerto direcional | Mesmo vínculo declarado a evidência/modelo, mas sem contagem de acerto |
| `AGUARDAR` | **Abstenção** por falta/conflito de evidência | Razão enumerada; modelo, SHA e corte ausentes devem ficar `null` |

São calculados `submitted_slots`, `missing_slots`, `directional_claims`, `neutral_abstentions`, `await_abstentions` e `coverage_fraction`, sempre com denominador **56**. Se as duas reivindicações direcionais D1/W1 de um mesmo par existirem, o relatório mostra concordância ou oposição, **sem selecionar um trade**. Uma posição ausente nunca desaparece do denominador; os 28 pares não viram 28 fontes de dados independentes.

## Portas que continuam fechadas

- O contrato aceita só `MANUAL_RESEARCH_CLAIMS_UNATTESTED`; carimbos e hashes fornecidos não são prova de assinatura externa, publicação macroeconômica no instante correto ou congelamento histórico do algoritmo.
- Uma auditoria realizada após o limite de compromisso pré-sessão devolve `LAB_ARCHIVAL_CLAIMS_AFTER_DEADLINE_UNATTESTED`. Declarar no arquivo um horário antigo não prova que o conteúdo existia naquele horário.
- `validated_prediction_count=0`, `validated_accuracy=null`, `probability_calibrated=null`, `fx_bias=null`, `operational_bias=AGUARDAR`, `trade_authorized=false` **mesmo que 56 reivindicações pareçam completas ou concordantes**.
- Os testes são sintéticos; **não** foram preenchidas previsões reais para 08/11, não existem resultados OOS, negociação, ordens, licenças de preços aprovadas ou inferências sobre tendência dos pares.
- Nada foi conectado ao Radar, Painel Mestre, cron, Worker, main, publicação ou fontes pagas.

## Próximo trabalho prioritário

1. Obter capturas de divulgação de cada indicador das duas moedas e o **consenso efetivamente disponível antes** do evento, com tempos e versões verificáveis.
2. Congelar a regra de tradução dessas evidências em impulsos de pesquisa antes de gerar **qualquer previsão real**. A V1 atual de quatro fatores tem pesos **não calibrados** e só admite entradas sintéticas.
3. Se houver previsão real, documentá-la **externamente antes da sessão** e manter cada abstenção e vaga não preenchida; o auditor offline isolado não certifica esse compromisso.
4. Após a janela, obter dados de preços independentes, fuso de corretora e spread bid/ask; testar walk-forward OOS com cobertura, taxa-base, tamanho de amostra e intervalo de incerteza.

**HARD NO-GO:** esta revisão não autoriza merge, deploy, Worker, agendador, pagamento, fontes não licenciadas, operação real nem alegação de 80%/90% de acerto.
