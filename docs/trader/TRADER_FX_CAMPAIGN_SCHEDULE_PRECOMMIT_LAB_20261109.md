# AtlasQuant Trader — compromisso da agenda inteira de rodadas D1/W1 (LAB)

**09/11/2026 — pesquisa sem operações, sem sinais operacionais, sem publicação de performance.** O AM12 permaneceu offline e nenhuma previsão real foi criada. Nenhum comentário com previsões foi publicado no GitHub nesta etapa; não houve acesso ao MT5, a preços, a contas ou a credenciais.

## Lacuna resolvida parcialmente

O acumulador `atlasquant_trader_fx_multicohort_ledger_lab.py` conservava **56 posições por rodada** e todas as rodadas da lista fornecida pelo chamador, mas essa lista podia ser preparada depois dos movimentos. A proteção contra seleção de períodos ruins só era relativa à lista recebida.

`atlasquant_trader_fx_campaign_precommit_lab.py` permite fixar prospectivamente, em um documento canônico SHA-256, um **plano inteiro**, com:

- identificador de campanha e `rule_version` fixos;
- IDs de cada rodada, na ordem declarada;
- aberturas e fechamentos **explícitos**, em UTC, dos alvos D1 e W1;
- exatamente **56 posições esperadas por rodada**, sem duplicação, reordenação ou sobreposição no mesmo horizonte;
- bloqueio de intervalos semanais NY17 de 168 horas atravessando mudança de horário de verão, **sem inventar a duração alternativa**.

Depois, `bind_campaign_to_fx_ledger_lab(...)` **deriva** o conjunto de rodadas a partir desse documento imutável por hash. Verifica cada `FrozenFxCohort` com seu roster e horários originais, exige que o documento da campanha tenha horário declarado anterior ao primeiro roster de cada rodada, preserva todas as oportunidades, inclusive `AGUARDAR` e vetos, e só então chama o acumulador anterior. **Uma só rodada omitida bloqueia a campanha inteira.**

`prepare_campaign_github_anchor_lab(...)` gera o texto exato, sem postar, de uma **terceira âncora**, anterior às âncoras de plano (`ROSTER`) e de decisões (`CENSUS`) de cada rodada. **Ordem metodológica pretendida**: fixar agenda e observar o comentário real do GitHub *antes* de qualquer roster individual → criar roster e observar âncora → calcular e registrar as 56 decisões, incluindo AGUARDAR, e observar segunda âncora antes das velas → verificar as evidências macro ponto-no-tempo → apenas depois do fechamento medir as oportunidades. Esta implementação pura ainda não autentica comentários, relógios do provedor nem a publicação inicial.

## Limitações que impedem um resultado de mercado

1. O universo de semanas/dias elegíveis e a **completude do calendário** não são conhecidos: o programa verifica a agenda que foi congelada, **não prova que todos os dias possíveis foram incluídos**. Gaps e exclusões devem ser declarados e justificados antes, após autenticar o calendário da corretora.
2. A base do GitHub precisa ler de verdade uma âncora da agenda **anterior à primeira rodada**. Hashes locais e horários fornecidos pelo chamador não comprovam retrospectivamente a cronologia. Um comentário publicado tarde não pode retroagir a campanha.
3. A duração semanal contratual antiga continua nominal em 168 horas; semanas que cruzam DST NY17 são bloqueadas até haver evidência da sessão real. Isso limita estudos multianuais: **não interpretar a capacidade de até 240 rodadas como calendário de 240 semanas já aprovado**.
4. A separação entre resultados D1/W1 e por par, independência estatística, vintages macro e custos de spread/slippage continuam pendentes.
5. O limiar do benchmark existente exige pelo menos **100 decisões baseline elegíveis por par/horizonte**, 30 após filtro e três janelas OOS com quantidades mínimas. Em W1, 100 observações por par representam **ao menos 100 semanas com decisão elegível** — possivelmente mais de dois anos com AGUARDAR ou lacunas. Os 56 cruzamentos de uma semana não são 56 observações independentes desse mesmo par.
6. Nenhuma probabilidade calibrada, taxa real de acerto, previsão real, opinião operacional, deploy ou merge é autorizada pelo módulo. Os retornos mantêm `operational_bias=AGUARDAR`, `publishable=False`, `trade_authorized=False`, `validated_directional_accuracy=None` e custo novo R$0.

## Verificações

```bash
python -m unittest -q test_atlasquant_trader_fx_campaign_precommit_lab
```

**21 testes sintéticos locais** conferem: campanha completa de três rodadas, remoção, reordenação, troca de regras, troca de alvo sob mesmo ID, tentativa de congelar depois do primeiro roster, esquecimento de candidatos vetados, tempos sobrepostos, DST, documento JSON/hash adulterado, ausência de postagem externa, identificação incorreta da PR e manutenção permanente de `NO-GO`.

A rotina GitHub Actions do Trader executará o novo módulo com o universo FX canônico em Python 3.11 e 3.12. Os resultados da CI devem ser observados no GitHub, não inferidos do código. **Próximo passo operacionalmente válido:** restaurar AM12 quando o usuário estiver disponível, identificar hora/servidor e calendário D1/W1, reunir dados macro anteriores à decisão; só depois preparar uma campanha futura realmente precomprometida.
