# A247 — Veto local pré-COMMIT e recuperação conservadora de mensagens (LAB)

**Estado: HARD NO-GO · 0/6 P0 homologadas · sem Worker, deploy, integração real, contratação ou merge.**

## Problema e mudança
A246 detecta um COMMIT com retorno incerto enquanto o mesmo objeto SQLite está aberto, mas o erro desaparece após reiniciar o processo. Agora, `append_message()` cria exclusivamente um arquivo `<database>.aion-message-commit-pending` antes de chamar COMMIT (durante o lock `BEGIN IMMEDIATE`). O arquivo é gravado e recebe `fsync`; o programa solicita `fsync` da pasta quando o SO permite. A conexão só remove o arquivo depois de `commit()` retornar normalmente. Se a confirmação ou remoção do marcador falhar, a operação fica bloqueada. Uma nova abertura é recusada caso haja qualquer arquivo/elo naquele nome. Não há limpeza automática.

O marcador é um **veto local**, não uma raiz de confiança. É possível também bloquear a instância atual se outro escritor criar o marcador; durante operações normais isso pode reduzir disponibilidade, aceitável para laboratório. Não elimina corrida externa, mesma identidade do arquivo, adulteração host ou ambiente SQLite com WAL de origem não confiável.

## Ensaios
- Operação normal remove o marcador e permite reabrir.
- SQLite COMMIT verdadeiro seguido de exceção sintética antes do ACK deixa registro confirmado e marcador pendente; reabertura é recusada.
- Erro antes do COMMIT também conserva o marcador e bloqueia tentativa automática.
- Marcador arbitrário/vazio causa veto antes mesmo de conectar/criar outro SQLite.
- Marcador introduzido após a conexão bloqueia health check e leituras.
- Erro na limpeza depois do COMMIT é tratado como incerto.
- Um subprocesso realmente termina de forma abrupta **depois do COMMIT verdadeiro e antes de limpar o marcador**: o processo seguinte deve recusar.
- **XFAIL explícito:** se o administrador remove o marcador local, a abertura é novamente aceita — vulnerabilidade ainda aberta.

## Limites e segurança
- Não é simulação de energia física: `os._exit` simula perda abrupta do processo, não a durabilidade do controlador/disco.
- Em plataformas sem fsync do diretório, como Windows, a persistência da entrada não é comprovada contra queda de energia.
- Um ator com controle da máquina pode apagar, substituir ou fazer rollback do arquivo marcador **e do banco**. Esta PR não valida testemunha, contador monotônico externo, evento de negócio ou VFS/FD nativo. **P0-5 e P0-6 permanecem abertos.**
- Outras gravações diretas ou via `with self.db` exigem auditoria separada. A247 cobre somente `append_message()`.
- Este veto não é autoridade para retomar operações. Qualquer incerteza requer reconciliação independente; **UNCERTAIN=ZERO_AUTO_RESEND**.
- Estratégia do proprietário: Trader prioritário, motor econômico sob demanda compartilhado com Investimentos, Negócios congelada/preservada; nenhum gasto novo.
