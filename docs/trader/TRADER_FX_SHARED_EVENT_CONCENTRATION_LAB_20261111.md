# AtlasQuant Trader — concentração de evento-raiz entre pares FX — 11/11/2026

**Escopo:** somente laboratório offline, Forex G8 / 28 pares, horizontes D1/W1. PR #1851 permanece rascunho. **Não foi liberado viés, ordem, alerta, merge, deploy, Worker, gasto ou acesso ao MT5.**

## A lacuna corrigida

A auditoria de dependências `atlasquant_trader_fx_evidence_dependency_gate_lab.py` já identifica vários indicadores associados ao mesmo evento em **um par**. Faltava enxergar a concentração **entre pares**: por exemplo, o PPI dos EUA pode afetar sete cruzamentos que contêm USD, mas isso não fornece sete observações independentes sobre o impacto macroeconômico.

Novo contrato: `atlasquant_trader_fx_event_concentration_lab.py` e `test_atlasquant_trader_fx_event_concentration_lab.py`.

- Reaproveita a validação da evidência por par e usa exclusivamente os 28 símbolos FX canônicos.
- Agrupa candidatos D1/W1 pelo **evento-raiz declarado**, reunindo os pares distintos e separando número de observações de número de ativos. O mesmo par nos dois horizontes não vira duas apostas independentes.
- Identifica candidatos com hipótese de exposição oposta à mesma moeda sob o mesmo evento declarado (necessidade de revisão); não presume que um evento isolado causou todo o movimento do par.
- Rejeita antes do agrupamento: símbolo invertido fora do universo canônico, duplicação de par/horizonte, divergência D1/W1, relógio futuro ou sem fuso, fonte capturada após decisão, evidência inválida, direção de fator contrária à hipótese e raiz desconhecida.
- Retorna razões documentais: `LAB_SHARED_ROOT_EXPOSURE_REVIEW_REQUIRED`, `LAB_EVENT_EXPOSURE_CONFLICT_ABSTAIN` ou inventário `UNATTESTED_NO_GO`. **Todas** as saídas continuam `AGUARDAR` em termos operacionais.

### Exemplo inteiramente sintético

Sete candidatos nos pares que contêm USD, todos rotulados com raiz declarada `US_PPI_OCT2026`:

| Contagem | Resultado de pesquisa |
| --- | ---: |
| Observações de candidato | 7 |
| Pares distintos | 7 |
| Eventos-raiz declarados | 1 |
| Ensaios independentes comprovados | **Nenhum número estimável** |
| Aprovação de risco ou negociação | **Não** |

O sistema pode apontar *concentração temática* sem atribuir coeficiente de correlação, exposição financeira, ganho estatístico ou probabilidade. Diferença de nomes de raízes **não prova** independência causal; os identificadores, vínculos e horários são fornecidos pelo chamador e ainda não autenticados.

## Validação e próximo P0

**20/20 testes locais sintéticos aprovados**; incluídos no workflow D1/W1 de Python 3.11/3.12. Não são backtests reais e não provam taxa de acerto. Nenhum histórico de cliente, cotação ou conta foi usado.

1. Conectar esse inventário ao coordenador de seis estágios **somente em LAB**, sem permitir que resultado de uma etapa substitua prova das demais.
2. Pré-registrar todos os candidatos e abstenções; no ensaio prospectivo PPI 13/11, tratar os sete pares USD como **um grupo de evento**, com resultados por par apresentados separadamente.
3. Depois, com fonte bid/ask e custos reais verificados, testar concentração de risco por moeda/evento e correlação efetiva fora da amostra. Sem posições, notional, broker atestado ou dados independentes não há limite monetário confiável.

**GO-LAB para a estrutura. NO-GO para integrar ao Radar ao vivo. HARD NO-GO para ordens.** AION permanece congelado.
