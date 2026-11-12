# AtlasQuant Trader — P0: expectativas de juros, surpresas e contradições

**Decisão de 08/11/2026:** foco inalterado nos **28 pares Forex G8**, com hipóteses de direção **D1/W1**, poucas emissões e direito de responder **AGUARDAR**. **WIN/WDO/US500/NAS100/US30** permanecem no escopo futuro, mas precisam de metodologia própria. AION/Negócios/Investimentos não são reativados. **Sem gastos, worker, agendamento, deploy, merge ou ordens.**

## Ordem de execução firmada

1. **P0 — Mudança na expectativa futura de juros de ambas as moedas.** Guardar dois snapshots comparáveis *registrados no momento*, mesma data-alvo, convenção, unidade, instrumento da mesma moeda, fonte e hora. Comparar **mudanças**, não simplesmente taxas de juros nominais dos países.
2. **P0 — Surpresa econômica contra consenso realmente pré-evento.** Aproveitar `atlasquant_trader_g8_event_relevance_lab.py`: `actual − consensus` é aritmética; CPI/NFP maior que o consenso não equivale mecanicamente a dólar mais forte. Guardar a regra interpretativa e o regime antes de testar seu impacto.
3. **P0 — Detector de contradições.** Se expectativa relativa de juros documentada contrariar um candidato D1 ou W1, exigir revisão/abstenção; se concordar, a concordância **não** autoriza emitir viés. Dados ausentes, envelhecidos, incompatíveis ou com captura posterior ao corte continuam bloqueados.
4. **Após provar valor incremental — Regime do mercado.** Tendência/lateralização/aversão a risco, com evidência medida fora da amostra; não empilhar indicadores sem testar se ajudam.

## Código desta etapa

- `atlasquant_trader_policy_expectations_conflict_lab.py`
- `test_atlasquant_trader_policy_expectations_conflict_lab.py`

O novo analisador compara hipóteses para os **28 cruzamentos** a partir de duas leituras temporais por moeda. Usa unidade de **pontos-base**, horizonte experimental de três meses e compara a variação de expectativas de **base − cotada**. Para uma hipótese `ALTA`, uma queda relativa grande aponta **contradição documental**; para `BAIXA`, um aumento relativo grande aponta contradição. O corte de **5 pontos-base** é apenas um parâmetro de teste *não calibrado*; nenhuma relação causal, probabilidade ou melhoria estatística foi demonstrada.

`inspect_policy_expectations_d1_w1_lab` compara **W1 no corte semanal** e **D1 no corte diário**, sem importar dados obtidos depois para decisões anteriores. Ele rejeita ordem de datas impossível, períodos/tenores divergentes, relógios futuros, hashes malformados, mesma captura reutilizada como nova leitura, ausência de moeda e janelas de cotação incompatíveis. Na presença de dados ausentes em qualquer período, sinaliza `research_candidate_requires_review`.

## Limites de confiabilidade ainda abertos

- **Nenhum dado real de futuros/OIS foi ingerido neste módulo.** Os inputs dos testes são inteiramente fabricados. Um SHA-256 fornecido pelo chamador não autentica a origem nem o horário da cotação.
- Instrumentos OIS, futuros e expectativas implícitas precisam de **normalização econômica verificável**; horizonte de três meses não transforma instrumentos diferentes em fontes idênticas.
- **Novo veto de integridade (10/11):** `instrument_id` precisa ter o prefixo exato da moeda (`USD:...`, `EUR:...` etc.) e sufixo não vazio, nos dois snapshots. Isso impede uma série USD erroneamente rotulada como EUR de participar da comparação, mas **não** autentica que o identificador ou a fonte existem.
- A cadeia de **consenso independente pré-divulgação** e o efeito **pós-notícia** sobre cada moeda ainda necessitam fonte real, timestamp e validação. A captura de CPI do BLS em outra etapa é contexto econômico, **não** previsão de juros nem consenso de mercado.
- A pontuação de acerto dos vieses **D1/W1 ainda não foi validada**; devemos avaliar acerto direcional, cobertura e estabilidade em períodos prospectivos fora da amostra, sem seleção posterior dos vencedores.
- Sem evidência que comprove incremento de qualidade, o filtro não pode ser chamado de fator que aumentou a assertividade. A meta de 65–70% é **objetivo de pesquisa**, não performance.
- Não há autorização para publicar/operar. `operational_bias=AGUARDAR`, `fx_bias=None`, `calibrated_direction_probability=None`, `trade_authorized=False`, `publishable=False` em todos os caminhos.

## Testes locais

```bash
python -m unittest -q test_atlasquant_trader_policy_expectations_conflict_lab
```

**25/25 testes sintéticos passaram** em ambiente isolado com stub da matriz canônica G8. O teste não equivale à regressão completa do repositório nem valida fontes, índices ou operações reais. Próximo passo de engenharia: integrar o veto documental ao `atlasquant_trader_evidence_join_lab.py` e testar com todo o repositório; a integração não está ativa no aplicativo.
