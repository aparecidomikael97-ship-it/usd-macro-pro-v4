# A259 — Isolamento do callback booleano de primeira tentativa (LAB P0-4)

**HARD NO-GO · P0 0/6 homologadas · sem Worker, deploy, merge, custo ou efeito externo.**

## Vulnerabilidade demonstrada pela A258

`ExecutionOutbox(..., first_attempt_guard=lambda intent: True)` aceitava um booleano fornecido pelo próprio chamador e entrava no fluxo de `adapter.send` **sintético**. Isso é adequado apenas a testes que reproduzem um envio fictício, mas é incompatível com tratar a mesma interface como prova de reserva externa de primeira tentativa.

## A259 — patch efetivo de engenharia (não prova de autoridade independente)

1. O construtor **normal** `ExecutionOutbox(store, scope)` **não recebe mais** `first_attempt_guard`; fornecer esse argumento produz `TypeError`. A implementação normal de `_reserved_first_attempt` retorna sempre `False` até que seja projetado e homologado um novo protocolo de autoridade independente. Nenhum callback host-controlled pode ligá-lo por simples atributo `_first_attempt_guard`.
2. Criamos `labs/a259_synthetic_outbox_fixture.py` com a classe de teste `SyntheticFirstAttemptOutboxLab`, subclass explícita que reproduz o comportamento perigoso **exclusivamente para adaptadores e cenários sintéticos**. O módulo de operação não a importa nem configura como padrão.
3. Migramos A241, A242 e A243 para usar a classe de laboratório quando a simulação exige callbacks. Em A258, o antigo XFAIL sobre o construtor normal vira teste positivo de recusa do callback; uma **nova XFAIL A259** registra que um host capaz de importar `labs/` e executar código arbitrário ainda pode usar a classe sintética para chamar um adapter falso.
4. Os testes A254–A257 que usam `_attempt` continuam usando a classe LAB explicitamente importada por A243; suas provas de **0 sends** permanecem válidas.
5. Não removemos a dependência de evidências externas: o mecanismo de produção de primeira tentativa está **desabilitado e sem caminho positivo**. `UNCERTAIN=ZERO_AUTO_RESEND` permanece.

## Limitações importantes e semântica de segurança

A A259 corrige a **interface de injeção mais direta** no construtor normal, mas não impede adversário com execução arbitrária no host de realizar monkeypatch de métodos, instanciar subclass LAB, chamar um adapter por conta própria ou alterar arquivos. Separar `labs/` de um pacote de produção será condição adicional de futuras builds, mas **isso não constitui a raiz de confiança**. Somente um emissor legítimo, reserva monotônica externa e testemunha com chaves/custódia fora do host podem comprovar P0-1/2/3/4. P0-5/6 requerem provas separadas de VFS/FD e efeito externo pós-COMMIT.

## Validação

A259 contém 11 testes específicos cobrindo: rejeição de `True` e de qualquer callback no construtor normal, 0 send sem testemunha, 0 send após manipular atributo legado, continuação do simulador explicitamente LAB, manutenção de recusa para callback False, introspecção da interface, histórico após reinício e **XFAIL de importabilidade de LAB por host**.

A CI em Ubuntu/Windows deve repetir A258–A233 e testes staging. Uma suíte verde **não** homologa nenhuma P0, não permite merge nem deploy.

**Trader permanece prioritário; Investimentos preparado para futuro uso, Negócios congelada. Nenhuma nova contratação.**
