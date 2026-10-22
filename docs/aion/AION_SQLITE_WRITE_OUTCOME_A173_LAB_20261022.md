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
Aguardando execução Windows e Ubuntu; transcrever contagens/logs reais aqui antes de qualquer conclusão.
