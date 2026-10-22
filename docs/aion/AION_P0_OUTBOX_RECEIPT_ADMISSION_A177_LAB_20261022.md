# A177 LAB — Bloqueio de confirmações/rejeições sem prova confiável

**22/10/2026. PR Draft #1467, sobre A176 #1466. main não alterada. 0/6 P0 HOMOLOGADOS — HARD NO-GO.**

## Riscos reais do fluxo de código identificados
`atlasquant_aion_execution_outbox.py` cruzava a fronteira `adapter.send` e:
1. `accepted=False,retryable=False` era interpretado como `FAILED` mesmo que o efeito externo pudesse já ter ocorrido; o estado terminal implicava ausência de incerteza sem comprovação.
2. `accepted=True,confirmed=True` entrava no ledger `action_effects` sem verificar que o `effect_ref` vinha de origem autenticada.
3. `reconcile` aceitava `found=True,confirmed=True` pelo próprio adaptador e escrevia `CONFIRMED` sem prova independente.

Esses são **caminhos exercitáveis em simulação**, não alegação de duplicação real de fornecedor.

## Testes RED — [GitHub Actions #39868471657](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39868471657)
Ubuntu e Windows, 40 testes por sistema: **3 FAIL** reproduziram exatamente os três comportamentos acima. **4 ERROR** ocorreram porque a interface de verificação ainda não existia no baseline; são erros de interface esperados, e não três ou quatro falhas extras de segurança. Não inflar contagem.

## Correção LAB candidata
- Padrão `evidence_verifier=None`: **nenhum resultado é autenticado**, nem positivo nem negativo.
- `adapter.send()` rejeitado após cruzar fronteira: sem `EFFECT_ZERO` verificável, o estado fica `UNCERTAIN` e não `FAILED`/`RETRY`.
- `adapter.send()` com `confirmed=True` mas sem `EFFECT_CONFIRMED` verificável permanece `SENT` e não entra no ledger de confirmações.
- `adapter.reconcile()` com `found=True,confirmed=True` sem verificador não muda `UNCERTAIN/SENT` para `CONFIRMED`.
- Verificador ausente, levantando exceção ou retornando algo diferente do booleano `True` é negado.
- Há um **callback de teste**, `synthetic_lab_evidence_verifier`, apenas no código de teste, para preservar cenários históricos de Saga (compensação e orçamentos) e Outbox. Ele não é raiz independente de confiança, não prova recibo real, assinatura, custódia ou efeito externo. **Qualquer chamador capaz de fornecer um verificador arbitrário pode simular aprovação neste contrato atual**; portanto NO-GO operacional.

## Testes GREEN — [GitHub Actions #39868617571](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39868617571)
A177 + A176 + Outbox/Saga: **40/40 Ubuntu; 40/40 Windows**. O job A176 separado [#39868617589](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39868617589) também passou **33/33 Ubuntu; 33/33 Windows**. São **146 execuções de testes** em dois workflows, com rede bloqueada, não 146 provas independentes homologadas.

`A177_FAKE_DEFINITIVE_REJECTION=UNCERTAIN_NO_RETRY`; `A177_UNVERIFIED_POSITIVE_SEND=NO_LEDGER`; `A177_UNVERIFIED_POSITIVE_RECONCILE=NO_LEDGER`; `A177_VERIFIER_UNAVAILABLE=NO_CONFIRMATION`; `A177_TEST_ONLY_RECEIPT=CONFIRMED_SYNTHETIC`.

## Bloqueios restantes antes de qualquer P0 fechado
1. Não há implementação de **raiz de confiança independente**, registro de chaves autorizadas, revogação, custódia monotônica anti-rollback nem verificação de assinatura de provedor/operador.
2. Callback `evidence_verifier` é interface experimental injetável; não garante competência ou independência do verificador. O contrato operacional deve impedir que adaptadores controlem o verificador ou as chaves de confiança.
3. Não há atestado criptográfico ligando recibo ao `request_id`, descritor imutável do efeito, tenant, nonce, sequência, versão, hash de histórico e momento externo.
4. Diário SQLite apagado/restaurado reabre reservas locais (A174/A175); banco de origem continua com limitações de vínculo VFS/FD (P0-5/6).
5. A Quality canônica completa e todos os locais de chamada/injeção de adaptadores não foram auditados nem reexecutados aqui.
6. Um callback sintético não homologa identidade do HUMAN_OWNER, recibos, fornecedor ou disponibilidade H0.

**Próxima prioridade:** construir ensaio de contrato de recibo assinado com chave pública previamente aprovada fora do adaptador, antirreplicação, sequenciamento e revogação; testar falsificação e falha de custódia; sem comprar serviço ou criar credenciais reais. Até evidência externa real, NO-GO.

**ZERO_AUTO_RESEND. Nenhum merge, deploy, Worker, fornecedor real, envio, pagamento ou gasto autorizado.**
