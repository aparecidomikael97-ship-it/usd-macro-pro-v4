# AtlasQuant Trader — registro prévio de vieses com cadeia de hashes (LAB)

**Data:** 10/11/2026. **Escopo:** 28 pares Forex G8. Sem sinais ou decisões
financeiras reais. Módulo: `atlasquant_trader_fx_forecast_precommit_lab.py`.

## Por que existe

A porta de preços MT5 adicionada anteriormente produz apenas uma variação
histórica *documental* (resultado depois do movimento). Para medir assertividade
é necessário preservar **uma previsão emitida antes do resultado**. Este módulo
constrói um formato auditável para as alegações iniciais; não produz previsões,
não dá horário confiável sozinho e não autoriza calcular taxa real de acerto.

## Campos e controles

Cada `ForecastPrecommitClaim` guarda:

1. `opportunity_id` único, par G8, horizonte `D1/W1/M1` e decisão alegada
   `UP`, `DOWN` ou `ABSTAIN`. Uma abstenção precisa ter motivo explícito;
   ausência de documentação macro bilateral é um dos motivos válidos.
2. Hash alegado do modelo e data de congelamento anterior à captura de
   características; hash alegado das características, instante de captura e
   instante de emissão anteriores ao início do resultado.
3. Janela prospectiva com duração correspondente a D1/W1/M1. Janelas
   sobrepostas do mesmo par e horizonte são rejeitadas; um conjunto de
   atualizações durante o dia não aumenta artificialmente o denominador de
   acertos. IDs repetidos e ordem cronológica inválida também são rejeitados.
4. Para um registro `UP/DOWN` de pesquisa, um `MacroVintageClaim` para
   **cada moeda** (base e cotação), com emissor e identificador da publicação,
   SHA-256 do documento *alegado*, instante de publicação alegado e captura
   alegada. Precisa ocorrer: publicação <= captura <= características <= emissão.
   Uma abstenção pode ser documentada mesmo com fonte unilateral ou ausente.
   O requisito é **necessário, não suficiente** para viés macro robusto.
5. Não há campos de preço futuro ou realização no registro. É intencional:
   não pode guardar o resultado dentro da própria "previsão prévia".

## Cadeia de hashes: utilidade e limite crítico

`build_fx_precommit_chain_lab` serializa de forma canônica as alegações e os
identificadores; cada hash SHA-256 inclui o hash anterior. `verify_fx_precommit_receipts_lab`
recalcula e rejeita alteração de conteúdo quando os recibos originais e o
hash final tiverem sido preservados em outro lugar. A ordem de referências das
duas moedas é normalizada; os horários incluem timezone UTC normalizado.

**O hash não é um carimbo de tempo confiável.** O usuário, uma aplicação ou
atacante pode fabricar uma sequência inteira depois do evento e recalcular os
hashes. Os próprios documentos macro e seus horários são alegações, não provas
de disponibilidade histórica. Portanto o retorno preserva sempre:

- `external_anchor_authenticated=false`;
- `prediction_timestamp_independently_attested=false`;
- `macro_source_issuer_authenticated=false`;
- `features_point_in_time_verified=false`;
- `precommitted_prediction_independently_proven=false`;
- `can_feed_validated_backtest=false`, `validated_accuracy=null`;
- `operational_bias=AGUARDAR`, `trade_authorized=false`, `publishable=false`.

Não há persistência automática nem conexão com corretora, MT5, banco de dados,
Worker, servidor, notificações ou Radar. O código é **puro e somente local**;
se algum dia houver recibos reais, será necessário decidir e auditar um meio
de registro externo imutável, carimbo de tempo autenticado e cadeia de custódia.

## Testes desta etapa

`test_atlasquant_trader_fx_forecast_precommit_lab.py`: **19 testes sintéticos**
e todos aprovados. Cobrem previsão UP/DOWN, abstenção, hashes e adulteração,
fraude com cadeia inteiramente recriada, dados macro unilateral/pós-evento,
horário ingênuo, duplicidade de oportunidade, janelas sobrepostas e os três
horizontes. Os testes incluem a prova de que uma cadeia forjada continua sem
atestado independente.

Suíte completa nesta rodada:
`python -m unittest discover -q -p 'test_atlasquant*.py'` => **254/254 PASS**.
Não houve novas previsões reais, nem revalidação dos 103.600 candles AM12;
nenhuma acurácia de 60%, 70%, 80% ou 90% foi demonstrada.

## Próxima etapa controlada

Definir um recibo externo autenticado (origem + instante de gravação) para
previsões de pesquisa e verificar seus documentos macro *point-in-time*. Só
então associar o recibo prévio às etiquetas documentais do MT5, sem atravessar
gaps/sessões e com divisão walk-forward, embargo, custos, correlação entre pares
e abstenções. Até lá, **NO-GO operacional** e PR em rascunho.
