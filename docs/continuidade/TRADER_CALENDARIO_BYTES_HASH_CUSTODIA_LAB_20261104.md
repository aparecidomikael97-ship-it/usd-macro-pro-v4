# AtlasQuant Trader — conteúdo documental e integridade dos calendários (LAB)

**Checkpoint 04/11/2026. Foco P1 (notícias/calendário) e P2 (três revisões
diárias), subordinado ao viés contextual das oito moedas e 28 pares.**

## O que foi criado

O módulo `atlasquant_trader_calendar_document_bytes_gate_lab.py` liga os
**bytes recebidos como insumo** aos eventos de calendário de cada uma das
três janelas planejadas: 06h35, 10h45 e 17h15 de Brasília.

Para cada evento declarado, exige que o insumo contenha:

1. Identificador da fonte e do evento, conforme o documento de calendário.
2. URL efetiva igual à URL que o calendário declara como origem.
3. Relógio declarado de recebimento coerente com a data de atualização do
   editor, a observação da fonte e a captura do slot.
4. **Bytes brutos fornecidos pelo chamador** cujo SHA-256 calculado seja
   idêntico ao hash que o documento de calendário declara.

Se faltarem bytes, houver troca de evento, divergência de hash, exagero de
tamanho ou horário incompatível, o módulo responde `LAB_BLOCKED` e
**não fornece lista de mudanças para uso operacional**.

Também gera uma cadeia local SHA-256 dos slots e hashes de documentos,
incluindo slots vazios, para futura comparação. A cadeia **não tem uma
testemunha independente** nem armazenamento imutável; é apenas uma prova
reproduzível de consistência dos dados informados nesta chamada.

Os relatórios de calendário continuam os mesmos do bloco anterior: fila de
revisão **humana**, remarcações e cancelamentos explicitamente declarados,
omissões de fontes parciais sem falso cancelamento, 28 cartões Forex e viés
**`AGUARDAR` em D1/W1/MN1**.

## Limite que não pode desaparecer do produto

Conferir SHA-256 prova que **estes bytes combinam com este hash**, mas não
prova que o banco central ou instituto de estatística de fato os publicou.
Ainda faltam identidade de origem/TLS atestada, horário independente,
custódia imutável e revisão de contraprovas. Mesmo com todos os hashes
coincidentes:

- `original_publisher_bytes_authenticated = false`;
- `tls_response_custody_attested = false`;
- `receipt_timestamps_independently_verified = false`;
- `three_daily_updates_verified = false`;
- `real_time_calendar_verified = false`;
- `publishable = false` e `trade_authorized = false`.

Não há coleta HTTP, agendamento, Worker, Render, envio de alerta, ordem,
cobrança, merge ou deploy. Nada desta etapa muda a aplicação publicada.

## Testes

Executado localmente:

```bash
python -m unittest discover -s . -p 'test_atlasquant_trader_*lab.py' -q
```

**220 testes locais aprovados**, incluindo **12 novos** da conferência
de bytes; zero falhas/erros. A conclusão de CI no GitHub deve ser
verificada por SHA antes de ser afirmada.

**Próximo passo:** conferir uma captura original independente de fonte
oficial, preservar sua proveniência e horário, respeitar termos/licença e
aplicar a validação sem inferir direção de câmbio a partir de notícias.
