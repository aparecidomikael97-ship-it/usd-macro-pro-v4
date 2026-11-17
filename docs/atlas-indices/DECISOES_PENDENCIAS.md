# Decisões e pendências — Atlas Índices v0.7

**Referência temporal:** 16/11/2026. **Natureza:** decisões comunicadas pelo proprietário ou atribuídas ao relato do auditor; sem execução de mercado.

## Decisões comunicadas (não confundir com validação técnica)

| Tema | Regra/decisão informada |
|---|---|
| Prioridade atual | **Oito ativos primeiro**; expandir somente após validação e nova autorização |
| Ativos | EURUSD, GBPUSD, USDJPY, AUDUSD, USDCAD, US500, NAS100, XAUUSD |
| Fonte de preço candidata | Pepperstone MT5 Demo; sem depósito |
| Escopo de operações | Sem operações reais **nem simuladas** |
| Viés | D1 e W1 do servidor autenticado da Pepperstone |
| Nota mínima | S ≥ +70 (ALTA) ou S ≤ −70 (BAIXA), dois fatores concordantes |
| Horizonte | 52 semanas informativas; 35 favoráveis de 52 sem empate por comparação sob teste aprovado |
| Estatística | Teste exato de sinais unilateral, três baselines, Bonferroni 0,05/3 |
| Fonte econômica | Estudo de cobertura EODHD + fontes públicas **antes de escolher fonte operacional** |
| Modo de captura | Script local após implementação e auditoria específicas; VPS adiado |
| Dados MT5 | H1 + D1 + W1 |
| Guarda | Computador + nuvem, sem prazo final; serviço e restauração pendentes |
| Anterioridade | Hash automatizado após autorização e auditoria, conferência semanal |
| Teste de hash | Aceito em princípio; exige novo sim nos detalhes antes da execução |
| Fora do piloto | WIN, Ibovespa, futuros ES/NQ, índices à vista e demais pares Forex |

## Três decisões principais ainda PENDENTES

1. **Estabilidade:** A (0,05% D1 / 0,25% W1), B (0,10% / 0,50%) ou C (faixa por ativo). Exige medir distribuições de variação dos oito instrumentos, sem otimização retrospectiva.
2. **Tipo de fator:** SURPRESA ou ESTADO para cada fator/indicador. Exige cobertura de histórico, consenso pré-divulgação e proteção PIT, inclusive verificação EODHD.
3. **Validade temporal da evidência:** até próxima divulgação ou N dias, de acordo com tipo do fator; exige estudo de idade e cobertura.

**Nenhuma dessas decisões deve ser preenchida por IA sem aprovação do proprietário.**

## Não verificado operacionalmente

- Detalhes de todos os contratos, horários D1 e W1, feriados, deslocamento real do servidor e relógio sincronizado.
- Existência, extensão, lacunas e integridade dos históricos H1/D1/W1 para os oito ativos.
- Acesso efetivo, cobertura, licença e disponibilidade de consenso do EODHD; não salvar token.
- Matriz causal completa, limiar testado prospectivamente, validade real das evidências.
- Regra de estabilidade selecionada, cobertura direcional e assertividade do método.
- Tempo de disponibilidade e expiração da conta demo.
- Exportador operacional auditado, mecanismo externo de hash, serviço de nuvem e restauração.
- Resultados reais de piloto, vantagem sobre baselines, lucro ou superioridade estatística.

## Condições antes de ampliar

Não ampliar por mera passagem do tempo ou por número alto de acertos isolados. Exigir:
1. Dados e calendários íntegros; nenhuma informação futura.
2. Previsões e hashes comprovadamente anteriores ao movimento.
3. Cobertura, falhas, abstenções e resultados reportados integralmente.
4. Avaliação prevista com baselines e tratamento da dependência semanal.
5. Auditoria independente e **decisão explícita do proprietário**.

**Estado:** DOCUMENTO / LAB / AGUARDAR / HARD NO-GO.