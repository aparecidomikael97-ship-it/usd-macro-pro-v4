# A181 — Continuidade da primeira reserva após perda/restauração do AION (LAB)

**Data:** 22/10/2026. **PR Draft:** #1471 sobre A180 #1470. **HARD NO-GO, P0 homologados: 0/6.**

## Objetivo verificado somente em simulação
A180 bloqueia o primeiro envio sem uma reserva assinada de testemunha, mas a testemunha era volátil. A181 adicionou `aion_chat/separate_custody_a181_lab.py`: um **segundo SQLite** sob diretório diferente do banco AION, simulando a memória de uma autoridade que ainda existe quando o host perde ou restaura o próprio banco. Ambos os arquivos são do **mesmo host de CI** — isto **não** cria independência física, administrativa ou anti-rollback.

## Contrato de escrita, leitura e falhas
1. O simulador exige `bootstrap_lab()` explícito. `open_existing()` (construtor normal) exige arquivo e esquema esperados e **não** reinicializa um diário de custódia vazio caso ele desapareça. Não há identidade externa de gênese que impeça um operador privilegiado de fazer um novo bootstrap proposital.
2. `reserve(challenge, request)` usa `BEGIN IMMEDIATE`, chave primária UNIQUE no digest do efeito **declarado**, sequenciamento monotônico no segundo banco e COMMIT antes de retornar a assinatura Ed25519 sintética. Duas conexões concorrentes para o mesmo efeito declarado não devem conceder duas reservas.
3. Atestado de reserva após COMMIT contém desafio, IDs e digest vinculados ao contrato A180. Perda da resposta, indisponibilidade de chave privada sintética ou falta do arquivo da testemunha impedem `adapter.send`.
4. Em recuperação: se AION perde o diário e cria outra intenção com outro ID técnico, a testemunha preservada recusa o digest semântico que já reservou. Se o AION restaura um backup antigo `CLAIMED`, a mesma recusa preserva `UNCERTAIN` sem reenvio automático.
5. O digest semântico usado ainda depende de escopo, ação, alvo e payload **declarados pelo chamador**. Operações legítimas diferentes com o mesmo conteúdo podem colidir; falsificar um campo pode esconder um efeito repetido.

## Bateria A181 — 15 casos
- Exclusão completa do arquivo SQLite local do AION com sobrevivência do segundo arquivo de custódia: mesma operação com outro ID deve ser negada.
- Restauração do host para snapshot anterior ao envio: reserva persistente no outro arquivo deve negar nova chamada.
- COMMIT da reserva seguido de perda do recibo/ack e depois perda do diário do AION: nenhum envio ocorre nem é liberado após recuperação.
- Testemunha fora do ar, arquivo ausente/corrompido e chave sintética indisponível após COMMIT: falha fechada.
- Corrida de oito requisições com identificadores técnicos diferentes e digest idêntico: somente uma reserva.
- Segunda inicialização explícita sobre arquivo existente: negada.
- Evento legitimamente diferente (payload diferente): aceito.
- Teste de **falsos positivos**: duas operações de negócio distintas, com payload idêntico, podem ser confundidas.

## Contraprovas vermelhas — expostas como testes de caracterização verdes
- `A181_CUSTODY_REENROLL_AFTER_WIPE=REPLAY_ACCEPTED_NO_ROOT`: exclusão da memória **da própria testemunha** seguida de bootstrap explícito novo permite repetir um efeito.
- `A181_CUSTODY_SNAPSHOT_ROLLBACK=REPLAY_ACCEPTED_NOT_ATTESTED`: restaurar um snapshot antigo da testemunha reabre o digest.
- `A181_INJECTED_TRUE_GUARD=FAKE_AUTHORITY_ACCEPTED`: chamador que possa instanciar o Outbox com um callback `first_attempt_guard` sempre verdadeiro simula autorização.
- `A181_DISTINCT_IDENTICAL_LEGITIMATE_EVENT=DENIED_FALSE_POSITIVE`: o digest de campos declarados não identifica eventos empresariais legítimos de modo único.
- Um arquivo em diretório separado ainda pode ser apagado/restaurado pelo mesmo operador/host. Um índice UNIQUE não prova custódia externa, testemunha anti-rollback, procedência do emissor, entrega do provedor nem recuperação real H0.

## Evidências e limites de validação
**Resultado final, código exercitado no commit `72fe8d7e033b1cc43d6ad144c9c554d12edbeb20`:**
- [A181 CI #39872947467](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39872947467): **110/110 Ubuntu + 110/110 Windows**. Contém os 15 testes A181 e as baterias A180/A179/A178/A177/A176/Outbox/Saga com rede negada.
- [SQLite lifecycle CI #39872947397](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39872947397): **93/93 Ubuntu + 93/93 Windows**.
- **406 execuções aprovadas** (duas baterias repetidas nos dois SOs); não são 406 garantias homologadas. Quality canônica completa, custódia externa e testes de infraestrutura real continuam não executados.
- Primeira execução A181 [#39872730587](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39872730587) passou 110/110 no Ubuntu; Windows teve 1 erro em 110 testes causado por vazamento de handle SQLite ao rejeitar PRAGMA num arquivo de custódia corrompido. A correção fechou a conexão imediatamente em caso de erro antes de retornar ao chamador; testes repetidos passaram nas duas plataformas.
- Marcadores confirmados nos dois logs finais: `A181_HOST_DB_DELETED_WITNESS_SURVIVES=NO_REPLAY`, `A181_HOST_ROLLBACK_WITH_CUSTODY_INTACT=NO_REPLAY`, `A181_LOST_RESERVATION_REPLY_AND_HOST_LOSS=NO_SEND`, `A181_CONCURRENT_TWO_IDS_ONE_EFFECT=ONE_RESERVATION`, `A181_CUSTODY_REENROLL_AFTER_WIPE=REPLAY_ACCEPTED_NO_ROOT`, `A181_CUSTODY_SNAPSHOT_ROLLBACK=REPLAY_ACCEPTED_NOT_ATTESTED`, `A181_INJECTED_TRUE_GUARD=FAKE_AUTHORITY_ACCEPTED`, `A181_DISTINCT_IDENTICAL_LEGITIMATE_EVENT=DENIED_FALSE_POSITIVE`.
  
Não houve teste de custodiantes físicos remotos, quórum real, falhas de rede entre domínios independentes, cerimônia HUMAN_OWNER, assinatura do provedor real, retomada H0 sobre infraestrutura final, Quality completa nem vinculação atômica ao arquivo nativo SQLite em uso pela VFS.

## Plano de aceite que permanece necessário
P0-3/4 requer autoridade independente com reserva antes do envio, geração e custódia de identificador imutável de evento, consulta pós-falha consistente, recusa sob perda de quórum, sequência não restaurável, bootstrap e revogação protegidos, logs/recibos assinados por chaves com proveniência verificável e ensaios de recuperação em infraestrutura-alvo. P0-1/2/5/6 seguem pendentes.

**Sem merge, deploy, Worker, credenciais, cadastros, efeitos externos ou gastos. ZERO_AUTO_RESEND. HARD NO-GO.**
