# A173 — Renomeação ABA durante write: resultado UNCERTAIN (LAB)

**2026-10-22 | Draft empilhada sobre A172 (#1462). ZERO_AUTO_RESEND, P0 0/6, HARD NO-GO.**

## Problema comprovado A172
No Ubuntu, `os.replace` moveu o mesmo arquivo SQLite para fora e de volta durante `append_message`. `st_dev/st_ino` continuaram iguais e a fachada retornou sucesso. Uma checagem baseada no nome do arquivo ao fim não atesta que não houve troca intermediária.

## Hipótese A173
Capturar a impressão digital temporal do diretório-pai imediatamente **após abertura e preparação da conexão SQLite** e antes de chamadas que escrevem no banco; comparar após o método e após validar as identidades A170. Se mudou, travar a fachada com `BOUND_DATABASE_WRITE_OUTCOME_UNKNOWN_DIRECTORY_CHANGED`. Isso significa **desfecho incerto**, não transação desfeita e não prova de corrupção. O commit pode ter ocorrido exatamente uma vez; verificação independente e reconciliação antes de qualquer nova intenção são obrigatórias.

`_WRITE_SENSITIVE_METHODS` inclui `create_conversation`, `archive_conversation`, `append_message`, `add_attachment_metadata`, `save_checkpoint`, `save_context_summary`, `wal_checkpoint`. **`backup_to` intencionalmente fora do gate**: cria/renomeia arquivo externo e necessita protocolo transacional próprio, não está homologado.

## Testes esperados e interpretação
| Caso | Critério |
|---|---|
| Escritas normais | Sucesso, sem falso sinal |
| ABA real Ubuntu durante `append_message` | Sinalizar outcome unknown; checagem posterior independente pode encontrar mensagem gravada |
| Windows renomeação bloqueada pelo SO | Declarar não exercitado, não detecção |
| Sensor adulterado após commit | Outcome unknown, readback prova commit; segunda tentativa proibida |
| Sensor indisponível antes de write | Bloqueio sem mutação do método |
| Criação de arquivo não relacionado | Possível falso positivo após commit; medir por SO |
| Escrita concorrente ao WAL | Não causar bloqueio por si só |
| Backup | Explicitamente fora de escopo; necessidade de verificação própria |

## Limites
- **Não é ligação atômica ao FD que o SQLite realmente usa** (o descritor `os.open` é independente). Também não prova resistência a rollback físico, nem protege contra relógio/metadados forjados, ataques de ABA com timestamp não observável ou host comprometido.
- Fail-closed pós-commit transforma sucesso real em **resultado desconhecido** e pode gerar falsa suspeita por outra criação de arquivo no diretório. Nunca reexecutar operação por causa dessa exceção.
- Mesmo que os testes passem, pendem produtor independente, recibos reais, identidade custodiantes e Quality canônica.

**Sem merge, deploy, Worker, integração externa, credenciais novas ou custo.**

## Evidência do CI
[Execução GitHub Actions #39857256120](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39857256120): **SUCESSO Ubuntu 75/75 + Windows 75/75, total 150**. O primeiro run #39856913156 falhou em um mock de `st_nlink`; o segundo #39857103187 expôs deslocamento da contagem `os.fstat` no teste legado A168; ambos foram corrigidos e toda a bateria repetida no terceiro run.

- Ubuntu: `A173_WRITE_ABA=ABA_COMPLETED_OUTCOME_UNKNOWN_POST_COMMIT`. O rename ABA ocorreu e foi detectado no pós-commit; readback nativo independente confirmou **uma** mensagem persistida. **Falha pós-commit não é rollback.**
- Windows: `A173_WRITE_ABA=OS_DENIED_OR_RESTORED_OS_NOT_EXERCISED`. O sistema operacional impediu o rename, portanto proteção A173 não foi exercitada nesse caso.
- Ambos: `A173_NORMAL_WRITES=ALLOWED`, `A173_CONCURRENT_WRITER=WRITES_ALLOWED` e `A173_INJECTED_DRIFT=OUTCOME_UNKNOWN_BUT_COMMITTED_ONCE`.
- Arquivo não relacionado no diretório durante write: Ubuntu `A173_UNRELATED_FILE=FALSE_POST_WRITE_UNKNOWN`; Windows `A173_UNRELATED_FILE=TIMESTAMP_DRIFT_NOT_OBSERVED`. **O sensor produz falsos positivos e pode não observar determinadas alterações de diretório no Windows.**
- O teste herdado de âncora pós-commit (A168) voltou a passar, preservando o erro `BOUND_DATABASE_ANCHOR_MISMATCH` e a proibição de reenvio automático.

**Veredito:** detecção heurística de ABA durante escrita no Ubuntu demonstrada, com custo de disponibilidade e limitações de metadados; **não está apta a homologação**. Zero prova de atomicidade do handle SQLite, custódia externa, recibo produtor independente ou proteção contra host hostil. P0 permanecem 0/6.
