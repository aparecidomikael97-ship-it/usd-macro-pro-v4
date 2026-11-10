# AtlasQuant Trader — porta de recibo assinado para previsão pré-evento (LAB)

**10/11/2026 | NO-GO operacional | sem serviço externo contratado**

## O que foi preparado

`atlasquant_trader_fx_signed_receipt_gate_lab.py` recebe um registro de previsão
e seus hashes da cadeia local, além de um recibo com assinatura Ed25519
*alegadamente* entregue por um serviço de carimbo de tempo. A validação é
**somente local**, sem internet, credenciais, pagamentos, gravação ou contas.

O recibo assina uma representação JSON canônica com versão do protocolo,
`receipt_id`, `signer_id`, `opportunity_id`, **hash da entrada específica da
previsão** (não apenas hash final de lote), nonce aleatório em hexadecimal e
horário de aceitação em UTC. O payload foi versionado para evitar interpretar
uma assinatura de outro contrato de dados como este recibo.

O verificador:

1. Revalida a cadeia de previsões e seus hashes, que ainda são alegações.
2. Localiza o identificador da previsão e o hash correspondente na cadeia.
3. Confirma que recibo, hash, nonce e identificador do suposto emissor são os
   esperados pelo **chamador**.
4. Exige cronologia alegada: emissão <= aceitação do recibo < início do
   resultado; e aceitação <= instante de avaliação.
5. Confere uma chave pública Ed25519 de 32 bytes contra seu fingerprint SHA-256
   fornecido pelo **chamador**, depois verifica a assinatura digital destacada.
6. Em falta da biblioteca opcional `cryptography`, bloqueia explicitamente a
   verificação. Não há fallback inseguro.

## A distinção que não podemos perder

**Assinatura válida ≠ horário autenticado independente.** Uma chave gerada
depois do evento pode assinar um horário falso de antes do evento. Como chave,
fingerprint, nome do suposto emissor e horário chegam do chamador, a porta
**não certifica** a identidade do serviço, a anterioridade da configuração de
confiança, a honestidade do relógio ou a cadeia de custódia da fonte.

O estado de sucesso **somente criptográfico** é
`LAB_SIGNED_RECEIPT_CRYPTO_MATCH_UNTRUSTED_SIGNER`; não é um carimbo de tempo
oficial nem uma previsão autenticada. Mesmo esse estado preserva:

- `signer_identity_independently_authenticated=false`;
- `public_key_previously_pinned_independently=false`;
- `timestamp_authority_independently_trusted=false`;
- `server_clock_independently_authenticated=false`;
- `historical_pre_event_prediction_proven=false`;
- `economic_vintages_independently_verified=false`;
- `can_feed_validated_backtest=false`;
- `validated_accuracy=null`, `calibrated_probability=null`;
- `operational_bias=AGUARDAR`, `trade_authorized=false`, `publishable=false`.

Para transformar isso em evidência real será preciso definir **antes** das
previsões uma autoridade externa confiável, uma chave pública pinned fora do
controle do produtor de previsões, política de carimbo de tempo, verificação
da custódia e do relógio, e retenção dos recibos. A porta de hoje ainda não
possui esse vínculo nem realiza uma chamada a qualquer serviço.

## Testes

- **15 testes sintéticos novos** com chaves Ed25519 efêmeras geradas somente
  em memória: assinatura válida sem confiança externa, assinatura corrompida,
  horário alterado depois da assinatura, aceitação antes da previsão ou depois
  do evento, nonce e emissor divergentes, troca de chave, arquivo falso de
  base64 e SHA de outra entrada. Também cobre abstenções e normalização UTC.
- `cryptography` estava disponível no executor desta rodada; não foi instalada
  dependência, solicitado serviço, gerada chave privada persistente nem
  utilizado servidor externo.
- Suíte local `python -m unittest discover -q -p 'test_atlasquant*.py'`:
  **284/284 PASS** em 10/11/2026. As 15 verificações criptográficas são
  opcionais em ambientes sem `cryptography` (SKIP, e a API permanece bloqueada).
- Os 103.600 candles reais do AM12 e as fontes macro não foram reabertos nem
  reautenticados nesta rodada. Não existe nova previsão real atestada.

## Próximo bloqueio explícito

Sem uma autoridade externa previamente confiável, qualquer mecanismo que
chame esses registros de "previsões comprovadas" ou calcule 60%–90% de acerto
deve ser recusado. Ainda não há ativação de Radar, Workers, operação real,
merge, deploy, despesas ou comercialização.
