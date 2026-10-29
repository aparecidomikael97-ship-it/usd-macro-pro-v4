# A265 — Separar callbacks de reconciliação do Outbox normal (LAB P0-6)

**HARD NO-GO · 0/6 P0 homologadas · sem Worker, deploy, merge, custos ou efeitos reais.**

## Falha concreta verificada

Após A259, o `ExecutionOutbox` normal impede `adapter.send()` por falta de reserva independente da primeira tentativa, mas o método `reconcile()` ainda fazia `getattr(adapter, "reconcile")` e chamava `adapter.reconcile(key, decision)`, aceitando objeto inteiramente fornecido pelo chamador.

Mesmo quando uma resposta positiva ou ausência falsa não era promovida a `CONFIRMED`/`RETRY`, **executar o callback pode causar uma operação externa**, acesso à rede ou efeito colateral, inclusive na avaliação de um atributo Python malicioso. Não podemos dizer `NO-SEND` para a fronteira se um método de reconciliação pode chamar código do adapter. Com as seis P0 abertas, não existe autenticação de recibo externo.

## Mudança A265

1. No `atlasquant_aion_execution_outbox.py` **normal**, `reconcile()` realiza apenas leitura da intenção em seu SQLite já vinculado. Requer estado `UNCERTAIN` ou `SENT`, e devolve o mesmo estado com `reconcile_state="INDEPENDENT_RECEIPT_REQUIRED_NO_ADAPTER_QUERY"`. **Não olha nem chama `adapter` ou `authorize`**, não muda a decisão e não marca `CONFIRMED` nem `RETRY`.
2. A lógica histórica que consulta `adapter.reconcile()` foi **movida para `labs/a259_synthetic_outbox_fixture.py`**, na classe `SyntheticFirstAttemptOutboxLab`. Ela permanece deliberadamente perigosa, apenas para simulação offline (A204/A205/A213/Outbox/Saga/Chaos), **não é implementação operacional**.
3. Casos A204 e A213 que criavam um `ExecutionOutbox` comum para receber resposta sintética de outro thread agora criam **explicitamente** a classe LAB. As outras suítes já recebem a fixture LAB herdada da A259.
4. `labs/test_a265_outbox_reconcile_adapter_isolation.py` cobre 12 cenários: resposta positiva falsa, falsa ausência, `@property reconcile` com exceção, adapter ausente, SENT sintético, estado CLAIMED inválido, 64 consultas concorrentes, reboot/UNCERTAIN, fixture LAB preservada, ausência de chamada no código da classe normal, diferença explícita de método entre classes, e **XFAIL** de host capaz de substituir método Python por monkeypatch.

## Limites importantes

- A265 remove um callback perigoso da API de reconciliação **normal**, mas **não implementa provedor nem uma testemunha independente**. O sistema continua sem caminho de comprovação confiável de `NO_EFFECT_FENCED` ou `CONFIRMED`.
- Um processo malicioso com controle do host pode importar `labs/`, monkeypatchar Python ou chamar uma API externa diretamente. A segregação real de builds (A260–A262) ainda não está exigida no Render.
- Os parâmetros `adapter` e `authorize` continuam na assinatura de `reconcile` por compatibilidade de chamadas, mas o corpo comum **não os acessa**.
- A liberação futura exigiria credenciais e raiz de confiança independentes, recibos verificáveis e mecanismo de reserva monotônico fora do computador. A política `main` também permanece não protegida, com proposta A264 **não aplicada**.
- CI verde do laboratório não homologa nenhuma P0, não comprova provider effect nem libera operação.

**UNCERTAIN=ZERO_AUTO_RESEND.** Prioridade Trader, Investimentos preparado e Negócios congelada. Sem novos gastos.
