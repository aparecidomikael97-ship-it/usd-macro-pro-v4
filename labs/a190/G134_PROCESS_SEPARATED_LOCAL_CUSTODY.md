# A190 / G134 — bridge Outbox real + custódia separada por processo (LAB)

**HARD NO-GO, 0/6 P0.** Empilhada sobre #1625 G133; nenhuma alteração do runtime operacional do AION, nenhum merge/deploy/Worker/provider SEND.

## Objetivo falsificável

O G133 comprovou que, após o host restaurar seu próprio SQLite, `ExecutionOutbox.enqueue()` admite novamente a mesma intenção local. O G134 insere um **bridge de laboratório controlado pelo chamador** que exige uma reserva durável obtida em **um subprocesso separado**, em outro diretório SQLite. Reserva é `BEGIN IMMEDIATE` + `UNIQUE(tenant,event_id)` + aumento de sequência + `COMMIT`; uma perda de resposta após COMMIT significa UNCERTAIN, nunca reenvio automático.

Este teste é propositalmente menor do que o requisito de segurança: outro processo e diretório no **mesmo host** NÃO são um custodiante independente. Um administrador/root que consiga reverter os dois arquivos ainda pode reautorizar a operação.

O `bridge` não altera `ExecutionOutbox` nem intercepta chamadas diretas para `enqueue`. O chamador pode ignorá-lo. Não há chave pinada externa, autenticação de HUMAN_OWNER, prova de idempotência fornecida por provedor ou autenticidade de `event_id`. A sequência é monotônica somente enquanto a custódia local não é revertida.

## Provas e contraexemplos

1. Restauração do **SQLite real do AION** sem restaurar a custódia separada: segunda reserva de evento é negada antes de `enqueue`.
2. Restauração **conjunta** do SQLite real do AION e do SQLite custodiado no mesmo host: nova admissão (RED; **não P0**).
3. Simulação de ACK perdido **depois do COMMIT** da custódia: primeira resposta é UNCERTAIN; nova tentativa não obtém reserva.
4. Custódia ausente: não é reinicializada; sem staging ou SEND.
5. Arquivo de custódia inválido: falha fechada, sem staging.
6. Outro `request_ref` com o mesmo `tenant,event_id` é rejeitado.
7. Identificador original redefinido pelo **próprio chamador**: segundo evento econômico semântico é admitido (RED; falta identidade original autenticada).
8. Falha/crash entre COMMIT da custódia e gravação no AION: não inferir ausência nem fazer restage.
9. Outbox padrão, mesmo com callback fornecido pelo chamador retornando `True`, não chama sequer o fake adapter `send`.
10. Concorrência entre dois subprocessos: exatamente uma reserva local.
11. Tokens de identificador ou digest inválidos não criam uma reserva.

**Sem efeitos externos em todos os testes:** `NoExternalAdapter` é um objeto Python que falharia se chamado. `ADMITTED_LOCAL_PROCESS_LAB_NOT_AUTHORITY` autoriza apenas o **staging de teste**; não concede autorização de envio, idempotência de provedor ou homologação.

## Condição futura real de P0

Necessário (1) vínculo com identidade HUMAN_OWNER original autenticada fora do host, (2) custodiante realmente independente/externo, atestado e monotônico mesmo sob restauração hostil, (3) raiz confiável instalada/rotacionada sem autorreposição do chamador, (4) identidade de efeito econômico semântico e recebimento autêntico do provedor, (5) ligação atômica ao fluxo de persistência/SQLite nativo e recusa antes do primeiro efeito, (6) prova de crash, H0 e concorrência, com G122 REAL RED finalmente alterando-se por implementação/evidência real, não por exclusão.

Até lá, **nenhuma operação real**. Estágio local e chamadas de laboratório não fecham P0. G122 mantém falhas abertas; G125 continua teste canônico sem mudanças. Sem contratação de infraestrutura/custos/segredos.

Refs: #1486, #1624 G132, #1625 G133.
