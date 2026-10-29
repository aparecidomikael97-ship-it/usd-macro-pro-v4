# AION A208 — contrato de recibo independente (pré-validação LAB)

**28/10/2026 · DRAFT · 0/6 P0 homologadas · HARD NO-GO**

## Origem

A207 Draft #1658 comprovou em Ubuntu/Windows que respostas positivas inventadas por um adaptador conseguem marcar `CONFIRMED` e criar ledger local sem qualquer efeito externo. O teste de controle permaneceu verde.

A208 não é uma correção do A207 nem um certificado de provedor. É o **contrato mínimo de entrada** para uma futura prova independente. Ele vem de A206 Draft #1656 para isolar a falha RED da proposta de contrato.

## Código isolado

`labs/a208_independent_receipt_preflight.py`:

- contém apenas funções puras de pré-validação de formato, escopo, intenção, identificador de efeito, fonte, período e sequência;
- rejeita campos extras como `verified=True`, duplicação de chaves JSON, assinatura com base64 inválido, sequência repetida, futuro, identidade divergente e recibo de outro provider;
- **nunca** chama `ExecutionOutbox`, Worker, `send`, rede, shell ou serviço externo;
- **sempre** devolve `may_confirm=False`, inclusive com formato aparentemente válido e assinatura forjada com comprimento correto;
- diferencia `STRUCTURE_OK_EXTERNAL_CUSTODY_UNVERIFIED` de evidência externa real (que está ausente).

Uma assinatura com 64 bytes inventados passa no formato, **não** na custódia. Um `witness_root_id` que coincide com um valor injetado pelo host é apenas um vínculo textual, não uma raiz de confiança independente. A checagem de `last_witness_sequence` é apenas local e também não prova resistência a rollback.

## Atestado externo ainda necessário

Para transformar `may_confirm=False` em autoridade de confirmação no futuro:

1. **Origem HUMAN_OWNER** independente, não controlada pelo mesmo processo/host.
2. **Admissão da intenção semântica original** assinada e vinculada à autorização válida.
3. **Recibo causal do provedor**, resistente a falsificação e reutilização, com `idempotency_key`, `intent_digest`, escopo, `provider_event_id` e `effect_ref`.
4. **Testemunha monotônica de custódia** independente do disco e do relógio locais; antirollback, sequência e primeiro efeito.
5. **Proteção e testes nativos de SQLite/host** contra troca de arquivo, inode, snapshot e rollback.
6. **Homologação P0 independente e replay adversarial** contra os caminhos diretos, Worker, reentrada e perda de ACK.

Sem isso, não conectar o contrato a `_confirm` nem permitir que callback autoatestado dê `CONFIRMED`.

## Testes

`labs/test_a208_independent_receipt_preflight.py` cobre dezesseis grupos:

- forma aparentemente correta ainda sem autoridade;
- `verified=True` rejeitado;
- escopo/identidade/provider/root divergentes;
- ausência de pin externo;
- replay, rollback e tipos inválidos;
- assinaturas malformadas e de comprimento insuficiente;
- períodos inconsistentes, JSON duplicado ou inválido;
- estado não confirmado, digests incorretos;
- retorno imutável e incapaz de autorizar confirmação.

CI Linux/Windows usa a workflow A208 apenas com Python e SQLite fake de regressão A206, sem provider.

**Importante:** teste A208 verde demonstrará apenas contrato de sintaxe, nunca P0, testemunha criptográfica, recibo H0, produção ou verificação de efeito.

## Restrições

**HARD NO-GO**. `UNCERTAIN=ZERO_AUTO_RESEND`. Sem merge, deploy, Worker, SEND real, trading, AWS, contratação, credenciais, integração do painel de Negócios ou novos gastos. A207 permanece RED sem ocultação; A208 é um laboratório independente e não altera o comportamento da Outbox.
