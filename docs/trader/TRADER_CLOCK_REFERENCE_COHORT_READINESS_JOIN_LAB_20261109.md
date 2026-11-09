# AtlasQuant Trader — auditoria de relógio como bloqueio do primeiro cohort D1/W1 (LAB)

**09/11/2026 — pesquisa somente leitura.** Nenhum sinal de mercado, ordem, deploy, agendamento, custo novo, merge ou alteração no Radar. O computador **AM12 estava offline** nesta rodada; não houve nova leitura de velas reais. As amostras abaixo são sintéticas ou horários documentados de uma auditoria anterior, **não** atestados em tempo real neste módulo.

## Lacuna anterior

O `atlasquant_trader_first_cohort_readiness_lab.py` exigia 28 pares/84 séries/103.600 candles, documentação de calendário e fontes macro das oito moedas, plano das 56 posições, decisões congeladas e dois comentários de pré-registro externos. Porém, a auditoria do padrão de horário D1/W1 (`atlasquant_trader_fx_nyclose_clock_audit_lab.py`) não fazia parte do pré-voo. Assim, a ausência de relatório, um horário contraditório ou uma suposta auditoria editada podiam passar sem bloqueio específico.

## O que mudou

Adicionamos um parâmetro opcional **`clock_reference_report`**, que por padrão não existe e consequentemente **bloqueia**. O pré-voo agora:

1. Exige um relatório com esquema `ATLASQUANT_FX_NY_CLOSE_BAR_CLOCK_REFERENCE_LAB_V1`, amostras tanto em **D1** quanto **W1**, contagens consistentes e nenhuma divergência com a referência, antes de poder declarar o inventário documental completo.
2. Detecta separadamente **ausência de auditoria**, **divergência a investigar com o servidor**, **relatório parcial/inválido**, **captura posterior ao congelamento da previsão** e **resultado adulterado/não reproduzível**.
3. Reconstrói cada `FxClockSample` recebido do relatório e roda novamente o algoritmo de comparação com o horário de Nova York. Campos como `bar_open_new_york` não são aceitos sem recomputação. Hashes e horários continuam **alegações locais**, sem atestar fonte externa.
4. Nunca corrige, desloca, preenche ou reamostra automaticamente candles do MT5. Uma divergência com a referência NY-close **não prova preço errado nem servidor incorreto**: exige diagnóstico no terminal original antes de homologar o calendário ou definir o período da previsão.
5. Mantém **`bar_clock_broker_association_verified=False`**, `operational_bias=AGUARDAR`, `publishable=False`, `trade_authorized=False`, `validated_directional_accuracy=None` mesmo quando todas as amostras combinam com a referência.

### Cenário conhecido que bloqueia

A auditoria documentou, entre outros exemplos, um rótulo diário `2026-11-05T00:00:00Z` e um semanal `2026-10-25T00:00:00Z` em arquivos do AM12. A ferramenta independente identifica **duas divergências** diante da referência de abertura de sessão de NY às 17h. Esses registros não provam a convenção do servidor nem devem ser automaticamente deslocados para outro horário.

## Testes executados

Diretamente no ambiente local, usando a lista sintética de 28 identificadores equivalente ao registro canônico apenas para importar o módulo de referência, sem rede, MT5 ou dados operacionais:

```bash
PYTHONPATH=.:/mnt/data/atlasquant_clock_lab \
  python -m unittest -q \
  test_atlasquant_trader_first_cohort_readiness_lab \
  test_atlasquant_trader_fx_nyclose_clock_audit_lab
```

**43/43 testes sintéticos aprovados**, sendo 21 do pré-voo (13 originais + 8 de integração) e 22 da auditoria de relógio existente. Foram cobertos: ausência e insuficiência de amostras, divergência realista dos horários documentados, captura tardia, campos NY/UTC forjados, alteração de contagens, e a garantia de que coincidência com a referência **não libera sinais nem atesta o broker**. Estes testes **não medem acerto de vieses** e não constituem regressão completa do repositório.

## Próximos passos verificáveis

1. Quando o AM12 conectar, **somente ler** alguns manifestos, hashes e rótulos de candles D1 e W1 do arquivo já existente. Registrar no relatório, separadamente, o servidor/perfil do terminal **sem conta, saldo, credenciais ou identificadores sensíveis**, e comparar à documentação da corretora efetivamente associada.
2. Resolver a origem dos rótulos UTC/NY e a política de horários de verão/fechamentos com evidência, sem corrigir ou excluir dados por suposição.
3. Só então definir as janelas futuras dos 56 alvos e os dois registros externos prospectivos antes do movimento; manter AGUARDAR se não houver macro ponto-no-tempo verificável.
4. Medir assertividade exclusivamente com previsões realmente pré-registradas e resultados reconciliados; incluir abstenções e medir cobertura.

**NO-GO operacional mantido.** Acurácia real e qualquer probabilidade calibrada continuam indisponíveis.
