# A180 — Primeira reserva da intenção antes da chamada externa (LAB)

**22/10/2026. PR Draft #1470 sobre A179 #1469. P0 0/6 homologados. HARD NO-GO.**

## Causa anterior / ameaça
O Outbox A179 registrava `UNCERTAIN` antes da chamada ao adaptador, porém não exigia testemunha de reserva da **primeira tentativa** antes de atravessar a fronteira. Um resultado de envio ambíguo exigia reconciliação, mas não havia prova prévia assinada de que uma tentativa havia sido reservada. As reservas locais A174/A175 são apagáveis e não impedem rollback do host. A testemunha A179 refere-se à admissão de um **recibo após efeito**, não à autorização de reserva inicial.

## Candidata A180
- Novo `aion_chat/first_attempt_witness_lab.py`: `PinnedFirstAttemptWitnessLab` confere `RESERVED` Ed25519 com chave pública fixada, desafio aleatório de 256 bits, decisão íntegra SHA-256, `idempotency_key`, escopo proprietário/tenant/workspace, digest de efeito semântico declarado, sequência `high_water` e validade máxima de 90 segundos.
- O digest de efeito da simulação usa escopo, `action`, `aggregate_key`, `payload_digest`, excluindo o `intent_ref` técnico. Isso detecta IDs técnicos diferentes com mesmos campos, mas pode bloquear operações legítimas idênticas e ser burlado por alteração de campos. Ainda falta identidade imutável autêntica de evento de negócio.
- `ExecutionOutbox(..., first_attempt_guard=None)` é **fail-closed por padrão** para envio. Antes de contactar a testemunha, `dispatch_claimed()` altera com condição `CLAIMED→UNCERTAIN` e persiste `FIRST_ATTEMPT_WITNESS_PENDING`. Se a testemunha reservar e a resposta se perder, a decisão fica `UNCERTAIN`, sem que `adapter.send` seja chamado ou o item volte automaticamente a `RETRY` após reinício/expiração de lease.
- Uma testemunha que responda com reserva assinada válida permite uma única chamada do adaptador em cenário sintético. Resposta ausente/inválida/antiga/revogada/perdida/assinatura incorreta impede envio; `ZERO_AUTO_RESEND` é mantido.
- A concorrência de troca de estado `CLAIMED→UNCERTAIN` agora verifica se a atualização afetou exatamente uma linha, negando a continuação no caso de corrida/estado alterado.
- Fixtures históricas Outbox/Saga/A176–A179 só enviam porque injetam `synthetic_lab_first_attempt_reservation` claramente identificado em código de **teste**, não testemunha real.

## Caracterização RED
CI inicial [A180 RED #39871324744](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39871324744) apresentou Ubuntu **95 testes, 2 FAIL** demonstrando a ausência de bloqueio padrão, e **15 ERROR** devido ao construtor `first_attempt_guard` ainda inexistente. Esta separação é importante: os erros de interface não são falhas adicionais comprovadas de segurança.

## Testes de LAB
18 novos testes: sem testemunha, reserva válida pré-envio, testemunha offline, reserva concluída com resposta perdida, reinício após resposta incerta, ID técnico novo para o mesmo efeito declarado, assinatura vencida, desafio reusado, assinatura não confiável, revogação, high-water, intenção divergente, rollback de estado de testemunha, reconfiguração maliciosa de chave, formato inválido, identidade de efeito alterada, evento distinto permitido e lease expirado com estado UNCERTAIN.

## Contraexemplos que NÃO se fecharam
- `A180_RESTORED_WITNESS=REPEATED_SEMANTIC_EFFECT_NOT_ATTESTED`: apagar/restaurar o estado da testemunha abre novamente a reserva do mesmo digest, embora o novo desafio seja assinado corretamente.
- `A180_CALLER_REPINS_FIRST_WITNESS=FALSE_AUTHORITY_ACCEPTED`: a chave pública considerada confiável pode ser trocada se o chamador controla o bootstrap. O callback `first_attempt_guard` também pode ser falsificado por um chamador interno arbitrário.
- `A180_ALTERED_SEMANTIC_DESCRIPTOR=UNDETECTABLE_AS_SAME_EFFECT`: o digest não é prova de identidade do efeito real; alterar campos pode produzir outro digest, e operação legítima idêntica pode colidir.
- Não há assinatura de fornecedor real, serviço externo de testemunha, custódia resistente a rollback, prova de autenticação de proprietário/fornecedor, garantia de **nenhuma** duplicação entre diferentes máquinas ou verificação física do arquivo SQLite.
- Não há análise de todos os call sites de envio, Quality canônica completa, validação de falhas de rede reais nem homologação das seis frentes P0.
- Resultados de CI em LAB provam somente os casos e ambientes testados; nenhum teste simulado é aceite de produção.

## Validação executada
Código da rodada testado no commit `bbfbe7b448a1eb7ba5be400a137d6cdaf70ab935` (as alterações posteriores são somente documentação).
- [GitHub Actions A180 #39871528923](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39871528923): **95/95 Ubuntu + 95/95 Windows**, total 190 execuções; inclui A180/A179/A178/A177/A176, Outbox e Saga com rede negada.
- [GitHub Actions SQLite #39871528959](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39871528959): **93/93 Ubuntu + 93/93 Windows**, total 186 execuções.
- **376/376 execuções nas duas baterias principais**. Os fluxos adicionais A176, A177, A178 e A179 também foram repetidos e concluíram com sucesso no Ubuntu e Windows ([A176](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39871528746), [A177](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39871528735), [A178](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39871528957), [A179](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39871528887)).
- Marcadores de logs verificados em **ambas** plataformas: `A180_DEFAULT_NO_FIRST_WITNESS=NO_SEND`, `A180_UNCERTAIN_RESERVATION_REPLY=NO_SEND`, `A180_PREFLIGHT_CRASH_REOPEN=UNKNOWN_NO_RETRY`, `A180_NEW_TECHNICAL_ID_SAME_SEMANTIC_DIGEST=DENIED`, `A180_RESTORED_WITNESS=REPEATED_SEMANTIC_EFFECT_NOT_ATTESTED`, `A180_CALLER_REPINS_FIRST_WITNESS=FALSE_AUTHORITY_ACCEPTED`, `A180_ALTERED_SEMANTIC_DESCRIPTOR=UNDETECTABLE_AS_SAME_EFFECT`.
- **Não é homologação:** 95 testes por OS são cenários concretos de regressão; testes deliberadamente verdes de rollback e confiança falsa reproduzem falhas. Quality canônica completa, origem externa e recuperação sob host adversarial não verificadas.

## Política
**Proibido** merge, deploy, Worker, provisionamento, pagamentos, provedores externos ou novas despesas. Sem prova externa de primeira reserva e custódia após rollback, **0/6 P0 homologados e HARD NO-GO.**
