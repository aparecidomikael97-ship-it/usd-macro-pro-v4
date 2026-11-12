# AtlasQuant Trader — pré-voo da primeira rodada prospectiva D1/W1 (LAB)

**09/11/2026.** Pesquisa isolada. **Não há precisão real mensurada**, posições de mercado publicadas, compra/venda automática, novos custos, deploy, worker ou merge. Prioridade: 28 pares G8 × D1/W1, com **56 posições** e `ALTA`, `BAIXA` ou `AGUARDAR`.

## Verificações efetivamente executadas nesta conversa

- Acesso remoto Desktop Commander: computador **AM12 offline**, visto pela última vez há aproximadamente 32 horas no momento da consulta. Não foram lidos os 103.600 candles nesta rodada.
- GitHub: a PR **#1851** permanece aberta e em rascunho. A consulta aos comentários da PR retornou **zero comentários**: ainda **não existe** um par de âncoras ROSTER/CENSUS observadas via GitHub para uma rodada real.
- Os arquivos `atlasquant_trader_fx_trial_census_lab.py` e `atlasquant_trader_fx_census_github_anchor_lab.py` já estão na branch de laboratório. Eles verificam estrutura/cronologia *alegada*, não comprovam por si só o horário original de uma previsão.
- A auditoria anterior encontrou `GBPNZD` sem D1 de **2025-09-30** e outras pausas de calendário não homologadas. Nenhuma delas foi interpolada nem marcada como feriado por presunção.

## Componente novo

`atlasquant_trader_first_cohort_readiness_lab.py` é um **inventário offline, somente leitura** de pré-requisitos. Não consulta o broker, não faz requisições HTTP, não abre o MT5, não grava arquivos e não libera sinais. Inputs são relatórios **informados pelo chamador**, sem autenticação independente neste componente.

Ele verifica:

1. Auditoria do arquivo MT5 por `atlasquant_mt5_backtest_gap_guard_lab.audit_archive`: **28 pares, 84 séries, 103.600 candles**, com erros e lacunas explicitamente reportados. O modo estrito ainda bloqueia inclusive pausas de fim de semana até existir uma política independente de calendário. Isso é uma dependência para **pontuação retrospectiva**, não motivo para inventar ausência de negociação.
2. Referências documentais aos horários D1/W1 da corretora capturadas **antes do congelamento** e com alvo ainda futuro. **Não presume** que todo broker utilize fechamento diário à meia-noite UTC ou abertura semanal na segunda-feira.
3. Inventário das **oito moedas** com captura cronologicamente anterior ao congelamento; a presença documental **não comprova** metodologia comparável, valor original CPI/juros ou dados de consenso autênticos.
4. Plano de 56 posições, decisão congelada de 56 posições, contabilização de `AGUARDAR` e os dois registros documentais de GitHub com hashes vinculados. **Nem hashes nem campos GitHub fornecidos pelo chamador são testemunho independente**.
5. Retorna bloqueios nomeados para permitir priorização sem acrescentar scores ou fontes inventadas.

### Comando de diagnóstico local

```bash
python atlasquant_trader_first_cohort_readiness_lab.py
```

Sem receber documentos reais, o comando retorna corretamente `LAB_FIRST_COHORT_BLOCKED` com os seguintes itens de pré-voo ainda não comprovados: horário de congelamento, auditoria AM12, calendário D1/W1, recibos macro das oito moedas, plano de 56 alvos, censo das 56 decisões e as duas âncoras externas. **Este comando não recolhe automaticamente esses dados**. A avaliação real da plataforma GitHub deve ser feita pelo conector/API fora deste módulo.

### Testes

```bash
python -m unittest -q test_atlasquant_trader_first_cohort_readiness_lab
```

**13 testes unitários sintéticos locais aprovados.** Cobrem ausência de artefatos, relógio com fuso, arquivo incompleto, lacunas, capturas econômicas posteriores ao congelamento, broker clock futuro, fraudes no hash dos comentários, e contagem de `AGUARDAR`. Caso todos os documentos alegados estejam estruturalmente consistentes, o estado continua apenas `LAB_DOCUMENTARY_INPUT_INVENTORY_COMPLETE_UNATTESTED`, **nunca** `trade_authorized` ou `external_precommitment_verified`.

## Fila estrita e enxuta

1. **AM12 online:** reabrir os manifests e os candles arquivados em modo somente leitura; confirmar convenções D1/W1 com amostras reais e proveniência da corretora; não coletar novamente 84 séries sem necessidade.
2. **Antes da rodada:** fixar janelas D1/W1 futuras, regras de seleção/abstenção e a lista completa de 56 alvos; registrar primeiro hash do plano com timestamp observado no GitHub.
3. **Ainda antes da primeira abertura:** levantar somente evidências macro disponíveis naquele momento, registrar as 56 decisões (inclusive `AGUARDAR`) e o segundo hash, observar e guardar timestamps reais de ambas as publicações.
4. **Depois dos fechamentos:** conferir hashes das velas, saltos/feriados, manifesto sem omissões e comparar o baseline com filtro de regime; testar janelas fora da amostra sem escolher retrospectivamente exemplos favoráveis.
5. **Antes de qualquer comercialização:** auditabilidade das fontes, licença dos dados, limites de risco, avaliação por instrumento e calibração independente; índices WIN/WDO/US500/NAS100/US30 seguem trilha separada.

**Regra final:** `operational_bias=AGUARDAR`, `publishable=False`, `trade_authorized=False`, `validated_directional_accuracy=None`, custo adicional **R$ 0** nesta etapa. Meta de 65–70% permanece uma **hipótese de pesquisa, não um resultado comprovado**.
