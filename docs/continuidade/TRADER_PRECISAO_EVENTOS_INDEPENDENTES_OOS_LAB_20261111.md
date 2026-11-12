# AtlasQuant Trader — Auditoria de amostras e raízes de evento (LAB, 11/11/2026)

**Objetivo:** impedir que o AtlasQuant apresente muitos acertos derivados de **uma única notícia** como se fossem muitas observações econômicas independentes. Complementa, sem substituir, `atlasquant_trader_selective_bias_gate_lab.py` e `atlasquant_trader_fx_event_concentration_lab.py`.

## Por que isso importa para a precisão do viés?

Exemplo: o PPI dos EUA afeta EUR/USD, GBP/USD, AUD/USD, NZD/USD, USD/JPY, USD/CHF e USD/CAD. Mesmo sete previsões simultâneas corretas continuam relacionadas a **uma divulgação econômica**; somar as sete como sete eventos independentes infla a confiança na estratégia.

Outro problema é mostrar apenas as previsões escolhidas e esquecer todas as ocasiões em que o modelo ficou neutro, aguardou ou não emitiu viés. A **cobertura de decisões** importa tanto quanto a taxa de acerto dos poucos sinais emitidos.

Referências metodológicas primárias:

- [NIST — intervalo de Wilson para proporções](https://itl.nist.gov/div898/handbook/prc/section2/prc241.htm). O intervalo usa um modelo binomial; sua interpretação depende das hipóteses do modelo.
- [scikit-learn — cuidados com vazamento de dados](https://scikit-learn.org/stable/common_pitfalls.html). Uma validação mal separada pode ver informações que ainda não existiam na hora da previsão.
- [Bailey et al. — The Probability of Backtest Overfitting](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2326253). Repetir seleção de estratégias sobre os mesmos dados pode criar resultados históricos ilusórios.

## Novo contrato `atlasquant_trader_selective_event_root_oos_audit_lab.py`

1. Exige um manifesto de *todas* as oportunidades declaradas antes da primeira decisão (identificadores, versão de regra e horário alegado de congelamento).
2. Exige exatamente uma observação correspondente para cada identificador; se alguém removeu uma perda ou parte da lista, o estudo inteiro bloqueia.
3. Separa **sinais emitidos** de **AGUARDAR**; abstenções são contabilizadas na taxa de seleção, mas nunca recebem rótulo de acerto.
4. Exige resultado observado depois da decisão e antes da auditoria. Rejeita resultados futuros, ausentes ou com rótulo impróprio.
5. Agrupa sinais por `event_root_id` e calcula duas estatísticas distintas: taxa observada por sinal e taxa conservadora **por raiz declarada**, na qual a raiz só acerta se *todos* os sinais associados acertarem.
6. Usa um limite de Wilson de forma **apenas ilustrativa, sob hipótese não verificada de independência**. O mínimo experimental de 100 raízes declaradas **não prova independência nem tamanho amostral adequado** para um mercado real.

Não importa o resultado: **`operational_bias=AGUARDAR`**, `validated_accuracy=null`, `calibrated_direction_probability=null`, `trade_authorized=false`, `publishable=false`. Nem as raízes declaradas nem as timestamps são atestadas de forma independente. O procedimento não verifica comissão, spread executável, slippage, rentabilidade líquida ou validade causal.

**Limitação red-team explícita:** um fornecedor malicioso ainda poderia reclassificar retrospectivamente uma previsão perdedora como `AGUARDAR` sem violar o manifesto de oportunidades. O auditor documenta `individual_issued_decisions_first_seen_externally_attested=false` e mantém NO-GO. Para impedir a troca seriam necessários recibos públicos/externos com direção e horário de cada previsão **antes** da realização do mercado.

## Exemplos apenas sintéticos

| Cenário | Sinais | Raízes de evento **alegadas** | Conclusão |
|---|---:|---:|---|
| PPI afetando sete pares | 7 | 1 | Uma raiz, não sete; nenhum viés liberado |
| Cem sinais ligados ao mesmo evento | 100 | 1 | Não satisfaz o mínimo experimental de raízes |
| Cem raízes fictícias com 100% de acerto | 100 | 100 | Estatísticas ilustrativas, mas sem autenticação: **NO-GO** |
| Sete sinais e três abstenções | 7 | 1 | Taxa documental de seleção de 70%, sem chamar abstenção de vitória |
| Uma oportunidade apagada da lista esperada | 6/7 presentes | — | **BLOQUEADO**; sem taxa de acerto parcial |

Testes em `test_atlasquant_trader_selective_event_root_oos_audit_lab.py` usam exclusivamente dados artificiais. Não houve acesso ao MT5, dados reais de preços, contas, ordens, scheduler ou qualquer mudança no app publicado.

## Para transformar em evidência futura (ainda não feito)

Obter uma lista completa de oportunidades congelada *antes* dos eventos com carimbo externo verificável, dados de broker com relógios auditados, resultados suficientes de períodos posteriores não utilizados para escolher regras, e uma revisão estatística que trate correlações entre notícias, pares e regimes. Só então avaliar separadamente precisão, frequência de abstenção, custos e calibração. A publicação permanece sujeita a aprovação humana.
