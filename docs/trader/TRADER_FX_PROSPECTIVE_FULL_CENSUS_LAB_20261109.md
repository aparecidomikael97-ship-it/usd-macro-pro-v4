# AtlasQuant Trader — manifesto prospectivo completo de 28 Forex × D1/W1 (LAB)

**09/11/2026:** Módulo de pesquisa **isolado**. O computador AM12 apareceu **offline**; nenhum candle real foi lido nesta rodada. **Nenhuma previsão real, taxa de acerto, atualização de Radar, ordem, publicação, worker ou agendamento foi criada.** Não há novo custo.

## Por que este módulo existe

O benchmark anterior (`atlasquant_trader_mt5_paired_outcome_bridge_lab.py`) compara corretamente uma lista recebida de oportunidades com os resultados dos arquivos MT5. No entanto, se a lista já tivesse sido selecionada *depois* de conhecer os preços, o sistema não detectaria as **oportunidades que nunca foram declaradas**. Precisamos declarar o universo completo **antes** dos movimentos e contabilizar o silêncio como **AGUARDAR**.

## Duas fases independentes

1. `freeze_fx_trial_roster_lab`: congela o **plano** dos alvos de uma rodada com os 28 pares canônicos e períodos D1/W1, formando exatamente **56 slots**. Recebe datas futuras de abertura e fechamento e versão das regras. Verifica que são posteriores ao instante alegado de congelamento e que duram 1 dia/7 dias. Constrói IDs determinísticos, JSON canônico e SHA-256. Não pressupõe que os horários de sessão da corretora estejam verificados.
2. `freeze_full_fx_direction_census_lab`: aceita **somente 56 decisões** com os IDs idênticos ao plano. Cada uma deve declarar `ALTA`, `BAIXA` ou `AGUARDAR`, horário de registro e corte da evidência. `AGUARDAR` exige motivo (sem dados, conflito, evento, veto, baixa confiança etc.). Direção exige um hash **declarado** de evidência e informações de elegibilidade/veto. Tudo deve ter sido alegadamente registrado antes da abertura do alvo, com regra de modelo compatível com o plano. Ausência de **um** slot, duplicata ou horário tardio bloqueia **toda** a rodada.
3. `verify_frozen_fx_census_lab`: confere canonicalização, hashes, vínculo ao plano e reconstrução das 56 linhas. Detecta alteração de bytes **não refletida** no hash, mas não confunde um hash recalculado com uma prova de origem ou horário independente.

### Exemplo conceitual (inteiramente fictício)

Um plano de pesquisa teria 28 registros diários + 28 semanais. É válido que **todos os 56 estejam AGUARDAR**: isso documenta que nenhuma hipótese foi emitida, em vez de escolher pares vencedores posteriormente. Outra rodada pode conter três hipóteses e 53 AGUARDAR; todas continuam no manifesto, e as três não são automaticamente operações autorizadas. **O formato não gera direção por conta própria.**

## Contratos e limites importantes

- Hash SHA-256 e horários inseridos pelo chamador são apenas declarações locais. Mesmo um manifesto cujo conteúdo foi recalculado e re-hasheado corretamente **não comprova** que existia antes do candle. Precisamos, posteriormente, de testemunho externo observável de **criação** (e da versão da regra), verificado de maneira independente. **Git commit com data do autor configurável, ou SHA sem testemunho, não basta.**
- A lista canônica dos 28 pares vem de `atlasquant_fx_universe.OFFICIAL_PAIRS`, sem alterar o cadastro. Os índices (WIN/WDO/US500/NAS100/US30) continuam na fila própria.
- A decisão de `AGUARDAR` não é sinal; classificação `ALTA`/`BAIXA` dentro deste LAB também não. `baseline_eligible` e `regime_veto` são entradas declaradas, não decisões calculadas ou auditadas neste módulo.
- Não há importação de notícias, juros, broker, MT5, fontes externas nem dados de execução. Não há inferência de assertividade, de probabilidade 0–10 ou de lucro líquido.
- D1 e W1 se sobrepõem temporalmente e, portanto, não são observações estatisticamente independentes. O calendário por broker, primeira disponibilidade dos dados macro, alterações de definição de regras, série dos preços e amostras intocadas precisam de provas adicionais.
- Este módulo **não altera** `atlasquant_trader_mt5_paired_outcome_bridge_lab.py` nem autoriza alimentá-lo diretamente com previsões sintéticas. Ligação com arquivo de preços exige validação posterior da integridade da origem e dos timestamps.
- Um plano = uma abertura de candle por horizonte para os 28 pares. Rodadas subsequentes deverão ter IDs de campanha distintos; não repetir o mesmo alvo como se fosse nova previsão independente.

## Execução local de testes

Na árvore do repositório (que já contém o módulo canônico `atlasquant_fx_universe.py`):

```bash
python -m unittest -q test_atlasquant_trader_fx_trial_census_lab
```

**34/34 testes sintéticos locais aprovados em 09/11/2026**, usando uma cópia mínima *apenas para testes* da lista canônica de 28 pares. Esse stub não foi incluído no GitHub. Testamos ausência, duplicação, mudança de IDs, versões e janelas, evidência futura, previsão registrada tarde, alteração de JSON sem re-hash, re-hash válido sem prova externa, abstenção e contagens por horizonte.

### Próxima tarefa P0

1. Definir calendário do broker e instante real de corte D1/W1 antes de iniciar uma rodada.
2. Pré-registrar o plano em fonte externa com confirmação independente do horário e travar versão das regras.
3. Registrar os 56 estados antes dos movimentos, incluindo abstinências, e pré-comprometer a lista completa também externamente.
4. Quando AM12 estiver online, conectar os registros prospectivos à ponte de candles reais e medir acerto **fora da amostra**. Se faltar uma prova, seguir com **AGUARDAR**.

**Status operacional**: `AGUARDAR`; `publishable=False`; `trade_authorized=False`; assertividade não mensurada; custo adicional R$0.
