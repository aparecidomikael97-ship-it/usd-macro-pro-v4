# AION H0 — sete envelopes assinados e prova causal do produtor (LAB)

Data: 21/10/2026. Este pacote é **somente experimento offline**. Nenhum Worker, Outbox, Saga, API real, conta externa, envio, transação, deploy, merge ou custo novo autorizado.

## Problema real

Após uma tentativa externa com timeout, `UNKNOWN` **não significa** que o efeito não ocorreu. Se o executor puder repetir automaticamente a operação, poderá enviar/pagar/executar duas vezes. Nem assinatura Ed25519 por chave fornecida pelo chamador, nem duas leituras locais, nem um HTTP 404 com cache falso estabelecem o estado causal do **produtor**. A situação fica ainda mais difícil se o histórico local for restaurado à versão anterior ao primeiro envio.

## Bloco técnico

A sequência sintética existente da PR Draft #1383 contém matrícula de chaves, revogação assinada, desafio/nonce assinado, reserva da primeira tentativa e readback assinado. O novo `atlasquant_aion_p0_h0_seven_signed_provider_receipt_lab.py` acrescenta dois documentos de laboratório:

6. **Recibo causal simulado do fornecedor**: assinatura de chave de LAB supostamente originária do fornecedor, com `request_id`, `intent_id`, `attempt_nonce`, escopo, operação, referência idempotente, três hashes dos documentos anteriores, epoch, sequence, digest, horário e um dos resultados `COMMITTED_EFFECT`, `NO_EFFECT_FENCED` ou `UNKNOWN`.
7. **Leitura simulada do head do fornecedor**: assinatura de outra chave sintética sobre os mesmos identificadores, epoch/sequence/digest e SHA-256 do recibo assinado. Os dois documentos precisam coincidir também com o `minimum_provider_epoch`, `minimum_provider_sequence` e digest **fornecidos pelo chamador**.

### Estado declarado e controles de forma

| `kind` assinado | Campos sintéticos coerentes exigidos | Consequência operacional |
| --- | --- | --- |
| `COMMITTED_EFFECT` | `effect_applied=True`, `fence_applied=False`, cutoff 0 e `future_dispatch_forbidden=True` | **UNKNOWN_BLOCKED**; não autentica efeito real |
| `NO_EFFECT_FENCED` | `effect_applied=False`, `fence_applied=True`, `fence_cutoff_sequence >= provider_sequence`, `future_dispatch_forbidden=True` | **UNKNOWN_BLOCKED**; não autentica no-effect de fornecedor real |
| `UNKNOWN` | flags de efeito/fence falsas, cutoff 0 e `future_dispatch_forbidden=False` | **UNKNOWN_BLOCKED** e zero reenvio automático |

Todos os caminhos de retorno ficam `HARD_NO_GO`, `allowed=False`, `reconciliation_state=UNKNOWN_BLOCKED` e 17 flags de autoridade falsas. `claimed_provider_outcome_lab_only` é apenas o texto informado por um envelope sintético, não uma transição terminal. Não existe armazenamento de estado, consumo de nonce, registro durável de idempotência, clock trusted ou produtor conectado.

## Ameaças incluídas nos testes

- 60 novos testes adversariais para documentos alterados, campos extras, tipos Python hostis, assinatura/encoding falso ou malformado, chave compartilhada entre papéis, IDs de operação e idempotência divergentes, hashes de reserva/readback/nonce incompatíveis, epoch/sequence/head antigos, falso fence, `UNKNOWN` com campos contraditórios, horários inconsistentes e repetição de pacote completo.
- Regressão de todos os blocos anteriores (44+56+38+34+55+28+20+64+8 = 347 métodos), total **407 testes selecionados por sistema**, se a CI passar.
- ACI read-only em Windows e Ubuntu, seguida por Quality original (562 módulos, 6.562 testes) e Security A74 original (365), sem dispensas de falhas.

## Limitações que os testes verdes NÃO resolvem

1. Chaves públicas de "fornecedor" e "último head" vêm de `caller_provider_pins`: o usuário da função pode inventar chaves, resultados e arquivos. Assinatura válida **não** prova origem do fornecedor.
2. Ausência de API/protocolo externo que emita recibos de efeito ou que garanta e comprove `NO_EFFECT_FENCED` após outcome incerto. Não há evidência que um provedor real consiga cercar irreversivelmente a operação.
3. `idempotency_ref` é só campo textual assinado em fixture: não representa semântica real de API. Provedores que não suportam idempotência forte e cancelamento com fencing não permitem inferir `NO_EFFECT_FENCED` de simples ausência.
4. "Última sequência" é um snapshot assinado em simulação, não uma consulta autenticada do estado realmente mais atual.
5. No teste, `future_dispatch_forbidden=True` é texto em um recibo fictício; não é uma política executada no fornecedor.
6. Rollback da máquina e do custodiador, chave raiz comprometida, restauração após `UNKNOWN` e duplicações de evento continuam bloqueios de H0.
7. Os 86 FAIL/ERROR históricos da Quality são bloqueios reais até resolvidos; nenhuma falha é dispensada como "esperada" para fins de homologação.

## Critérios de eventual reconhecimento real (não implementados)

Exigir identidade de emissor enrolada fora do executor, segregação comprovada de administração/recuperação, leitura fresca do head remoto, prova de consumo atômico de desafio e idempotência durável realmente oferecida pelo fornecedor. A separação COMMITTED vs NO_EFFECT deve depender de recibos realmente **originados** do produtor e verificados por raiz aprovada, recuperáveis e auditáveis após reinício e rollback; nunca inferidos de HTTP timeout, 404, flag local ou testemunha sintética. Aprovação de HUMAN_OWNER, Security e Quality canônicas, e fechamento dos 6 P0 vêm separadamente antes de qualquer operação real.

**HARD NO-GO · 0/6 P0 homologados · Worker OFF · ZERO_AUTO_RESEND · nenhum merge/deploy/serviço novo.**
