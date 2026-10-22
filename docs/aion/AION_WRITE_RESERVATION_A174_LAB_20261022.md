# A174 LAB — Reserva local persistente e bloqueio de reenvio após reinício

**2026-10-22. Draft empilhada sobre A173 (#1463). HARD NO-GO, P0 0/6.**

## Motivação
A173 demonstrou que uma exceção após o commit pode coexistir com mensagem já persistida. A trava `_failure` da fachada é volátil; um novo processo não herda a razão do bloqueio. A174 mantém no estado de saúde da A173 o código explícito `BOUND_DATABASE_WRITE_OUTCOME_UNKNOWN_DIRECTORY_CHANGED` e implementa **protótipo isolado**, **ainda não conectado à fachada nem ao Worker**, de reserva local persistente de intenção.

## Contrato do protótipo
`LocalWriteReservationLab` (`aion_chat/uncertain_reservation_lab.py`) usa um banco SQLite **separado**, `journal_mode=DELETE`, `synchronous=FULL`, transação `BEGIN IMMEDIATE` e ID de requisição estrito ligado a um digest de payload SHA-256. Estados:
- Ausente → `PENDING` via `reserve(request_id,payload_sha256)`.
- `PENDING` → `UNKNOWN` via `mark_unknown(request_id)` quando se observa desfecho incerto.
- `PENDING` e `UNKNOWN` **sempre negam nova `reserve` para o mesmo ID**, inclusive após reinício. `UNKNOWN` não é resolvido automaticamente.
- Mesmo ID com payload diferente → `PAYLOAD_MISMATCH_DENIED`.
- Duas conexões concorrentes serializadas por SQLite; somente uma pode reservar.

O módulo não executa o efeito externo, não fornece API de reenvio e não declara que sucesso local é recibo de fornecedor.

## Falhas deliberadamente demonstradas
- **Deleção de todo o banco de reservas** seguida de nova inicialização pode liberar o mesmo ID: bloqueio local não é prova de custódia independente nem de monotonicidade externa. Registro de teste `A174_LOCAL_JOURNAL_DELETION=REPLAY_ACCEPTED_NOT_ATTESTED` esperado.
- Novo `request_id` para o mesmo efeito semântico não é reconhecido como duplicação: faltam normalização e idempotência semântica confirmadas pelo fornecedor e/ou testemunha independente.
- Host hostil, troca de arquivo no intervalo entre fingerprint e abertura SQLite, restauração de backup antigo ou corrupção de fsync não são excluídos; não existe ligação atômica ao FD nativo nem recibo assinado.
- O teste de saída abrupta verifica **apenas** processo terminando depois do commit de reserva; não assegura durabilidade elétrica no host, disponibilidade H0 ou recuperação histórica real.

## Escopo e gates
- LAB temporário, sem chaves reais, sem emissão de mensagens, sem pagamentos, sem rede e sem efeitos de fornecedor.
- Nenhuma integração com Worker/usuário; main intocada, PR Draft, sem merge ou deploy e sem custo novo.
- A174 não homologa os 6 P0: identidade independente, recibos externos e rollback físico continuam pendentes. ZERO_AUTO_RESEND em qualquer resultado incerto.

## Evidências do CI
CI [GitHub Actions #39858489340](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39858489340): **SUCESSO Ubuntu 85/85 e Windows 85/85 (170 execuções de testes)**.

| Evidência emitida | Ubuntu | Windows |
|---|---|---|
| Mesmo ID reservado novamente | `A174_REPLAY_SAME_ID=DENIED` | `DENIED` |
| Reinício em processo Python distinto | `A174_NEW_PROCESS_REPLAY=DENIED_LOCAL_JOURNAL_PRESENT` | `DENIED_LOCAL_JOURNAL_PRESENT` |
| Saída abrupta após commit da reserva | `A174_ABRUPT_EXIT=PENDING_SURVIVED_LOCAL_RESTART` | `PENDING_SURVIVED_LOCAL_RESTART` |
| `UNKNOWN` permanece em reinício | `A174_UNKNOWN_RESTART=DENIED` | `DENIED` |
| Apagar diário local e reinicializar | `A174_LOCAL_JOURNAL_DELETION=REPLAY_ACCEPTED_NOT_ATTESTED` | `REPLAY_ACCEPTED_NOT_ATTESTED` |

O teste `test_02_post_write_observation_denies_success_but_write_exists` também confirmou o código exato `BOUND_DATABASE_WRITE_OUTCOME_UNKNOWN_DIRECTORY_CHANGED` no `storage_health.reason` da fachada experimental.

**Veredito:** contrato local anti-reenvio após reinício confirmado nos cenários específicos. **Não homologado:** exclusão/rollback do diário local permite nova reserva, estado independente inexistente, vínculo com efeito real não implementado, proteção H0 não comprovada. Nenhuma alteração de produção autorizada.
