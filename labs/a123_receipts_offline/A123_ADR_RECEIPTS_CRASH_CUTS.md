# AtlasQuant / AION — A123: recibo de admissão, WORM simulado e cortes de falha

**Data:** 16/10/2026. **Status:** experimento offline, NÃO homologado. **Base da branch:** A122 `5d5d6a65af2d618925dbd3dcc6d880e313262a91`. **Prioridade:** P0 sem liberar Worker.

## Decisão central

**Não existe transação distribuída única entre banco, armazenamento imutável, assinador e o fornecedor da ação.** A123 testa somente um contrato conservador de *admissão de tentativa* em que uma falha nesse caminho consome a intenção em vez de permitir repetição. Perda de disponibilidade é aceita para evitar uma segunda tentativa do mesmo identificador lógico **enquanto as hipóteses de laboratório forem preservadas**.

Os nomes `ToyVault` e `LocalToySigner` são deliberados. `ToyVault` é outro arquivo SQLite mutável e `LocalToySigner` usa HMAC de teste no mesmo processo. **Isto NÃO é S3 Object Lock, KMS, custódia externa, assinatura independente, garantia contra rollback ou segurança física.** O experimento jamais realiza uma chamada de fornecedor ou rede.

## Protocolo sintético (sem efeito externo)

```text
AION (sem credenciais de emissor)                 Custodiante/assinador SIMULADOS
      |                                                     |
      | PREPARE intenção/escopo imutáveis                    |
      +------> SQLite registro PENDING_ANCHOR                 |
      |        ToyVault ANCHOR + assinatura de teste         |
      |        SQLite PREPARED após verificação              |
      |                                                     |
      | ISSUE_ONCE (uma tentativa lógica)                    |
      +------> SQLite UNKNOWN_CONSUMED  [commit ANTES]        |
      |        ToyVault ISSUE_ONCE + assinatura de teste     |
      |        reler/verificar recibo atual do ToyVault      |
      |        FakeSender.call() uma vez, sem retry          |
      |                                                     |
      +------> UNKNOWN (mesmo com ACK fictício)              |
```

**Invariantes do LAB:**

1. O vínculo de intenção usa `intent_id`, `owner`, `tenant`, `workspace`, `account`, `action`, `destination_digest`, `payload_digest`, `epoch`; nenhum desses campos pode mudar após registro.
2. `PREPARE` pode ser refeito com segurança **antes** da consumação da tentativa, para resolver quedas entre registro local e âncora. Reutiliza âncora da MESMA intenção, sem emitir.
3. **A primeira gravação de `UNKNOWN_CONSUMED` acontece antes da escrita `ISSUE_ONCE` no ToyVault e antes de `FakeSender`.** Se ToyVault ou assinador falhar, a tentativa não pode ser feita de novo automaticamente.
4. ToyVault só aceita uma marca `ISSUE_ONCE` por intenção e impede combinar `ISSUE_ONCE` com `PRE_FENCE`; os nonces são únicos no arquivo ToyVault.
5. A verificação da assinatura simulada depende de leitura fresca do arquivo ToyVault. Um recibo trazido pelo chamador, mesmo assinado, não autoriza uma segunda emissão.
6. `ISSUE_ONCE_ADMISSION` **NÃO** é `COMMITTED_EFFECT` nem prova de entrega; `PRE_FENCE` no simulador **NÃO** é `NO_EFFECT_FENCED` definitivo após handoff. Resposta ambígua => `UNKNOWN`, `ZERO_AUTO_RESEND`.

## Cortes de falha e decisão conservadora

| Momento da queda | Evidência possível | Decisão segura da fixture |
|---|---|---|
| Antes da âncora, com PENDING_ANCHOR | Sem emissão, registro local | Reconciliar PREPARE, sem sender |
| Após âncora, antes do commit PREPARED | Âncora fictícia íntegra | Reconciliar PREPARE, sem sender |
| Após PREPARED, antes do ISSUE | Nenhum efeito autorizado | Pode competir uma única vez por ISSUE |
| Após SQLite `UNKNOWN_CONSUMED`, antes do ToyVault ISSUE | Marca local consumida | `UNKNOWN` e nenhuma segunda tentativa |
| Após ToyVault ISSUE, antes de devolver recibo | Duas marcas persistidas (sem emissão) | `UNKNOWN` e nenhuma segunda tentativa |
| Assinador indisponível/corrompido | Recibo não verificável | Negar, não assumir `NO_EFFECT` |
| Depois de FakeSender, resposta perdida | Handoff ambíguo | `UNKNOWN`, nunca reenviar automaticamente |
| Banco local restaurado, ToyVault preservado | Âncora+ISSUE preservados | Repetição negada pela fixture |
| ToyVault restaurado, banco local preservado | `UNKNOWN_CONSUMED` preservado | Repetição negada pela fixture |
| **Banco local + ToyVault restaurados juntos** | Histórico de ISSUE apagado nos dois | **VULNERABILIDADE REPRODUZIDA: segunda chamada fictícia possível** |

## Testes com resultado concreto

Comando: `PYTHONWARNINGS=error::ResourceWarning python -m unittest -v test_contract`, Python 3.13/Linux local:

- **38/38 testes executados com sucesso**, incluindo 32 processos disputando a mesma intenção, uma única chamada fake vencedora, cinco cortes de falha, assinatura e recibos alterados, escopo cruzado, nonce duplicado, queda do signatário, pre-fence versus emissão e callbacks falsamente interpretados.
- O teste **35** foi intencionalmente definido para **PASSAR quando a segurança falha**, mostrando que co-rollback dos dois arquivos permite duas chamadas `FakeSender` para a mesma intenção.
- Primeira execução: **37 PASS / 1 ERROR**, nonce duplicado lançou `sqlite3.IntegrityError` fora da classificação segura. Correção mínima no código traduziu para `Denied("UNIQUE_CONSTRAINT_OR_NONCE_REPLAY")` e fechou conexões nos testes. Resultado final 38/38 PASS, zero `ResourceWarning`.
- NÃO foram executados GitHub Actions/CI hospedada, Windows real, Android, testes de host independente, serviço cloud real, autenticação KMS, custos verificados, chamadas bancárias/SMS ou rede.

## Critérios externos para um futuro GO (TODOS ABERTOS)

- [ ] Provar administração e credenciais da custódia fora do runtime, conta e backup AION, com acesso a restore negado ao admin AION; verificar a titularidade por fonte não informada pelo checkpoint.
- [ ] Provar monotonicidade de alto-nível, transações condicionais e replay/nonce/per-intent CAS contra restore, backup, cópia e novo administrador; evidência independente retida após co-rollback local.
- [ ] Provar persistência independente de recibos e signatures com política de chaves: emissão, rotação, revogação, verificação por chave pública distribuída out-of-band e recuperação após indisponibilidade do assinador.
- [ ] Definir/ensaiar o protocolo **DB + WORM sem commit atômico**, com falhas em cada corte, conservação de marcas e proibição de reenvio; usar URL/`version_id` autenticado e cadeia monotônica, não somente versão `latest`.
- [ ] Verificar exclusividade real do emissor e ausência de bypass: o AION não deve possuir credenciais do fornecedor ou ter caminho alternativo de disparo.
- [ ] Fornecedor de SMS/WhatsApp/e-mail qualificado especificamente para `COMMITTED_EFFECT` e eventual `NO_EFFECT_FENCED` abrangente pós-handoff; caso contrário, resultados ambíguos permanecem `UNKNOWN`.
- [ ] F1/T1 para origem e antirollback de checkpoint, H0 para efeitos, F2 para HUMAN_OWNER e controle de custos/LGPD em processos separados. Testes cross-host/Windows/Linux e autorização prévia para POC real.

**Status final:** nenhuma P0 homologada por A123. Os 84 diagnósticos históricos do corte A118 permanecem abertos e não foram reexecutados aqui; o corte A115 de 89 ocorrências é outra linha histórica. `HARD NO-GO`, `ZERO_AUTO_RESEND`, Worker OFF, 20/20 FIRST_INSTALL bloqueados. Sem merge, deploy, dados pessoais, envio ou custo.
