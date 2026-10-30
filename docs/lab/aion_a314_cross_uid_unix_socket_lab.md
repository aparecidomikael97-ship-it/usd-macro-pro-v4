# A314 — escritor SQLite sintético por socket Unix e UIDs distintos (LAB)

**HARD NO-GO / ZERO_AUTO_RESEND / 0 de 6 P0 homologadas / custos novos zero.**

## Mudança concreta em relação à A313

A313 confirmou, em pasta descartável Ubuntu, que o kernel nega leitura/escrita do banco SQLite ao UID `nobody` quando a pasta pertence a outro UID e está em `0700` com DB em `0600`. A314 faz o próximo ensaio real: **um cliente `nobody` sem acesso ao DB solicita uma única operação local por socket Unix; um subprocesso escritor da conta do runner realiza a gravação sintética.**

Esse experimento é exclusivamente um **harness de teste** e não adiciona daemon, Worker, conta, privilégio permanente, provedor, ordem, endpoint de cliente ou infraestrutura real.

### Como funciona

- Somente no Ubuntu descartável do GitHub, cria diretório temporário sob `/tmp/a311-lab-a314-*`; a raiz usa `0711` para permitir alcançar um socket, mas o subdiretório protegido `a311-lab-a314-private` permanece `0700`, com DB SQLite `0600`.
- O escritor é um subprocesso Python com **uma única conexão de socket por execução**. Abre `AF_UNIX/SOCK_STREAM`, coloca permissão `0666` no socket sintético e extrai **`SO_PEERCRED`** (PID, UID, GID fornecidos pelo kernel Linux).
- Só aceita conexões do **UID real e preexistente `nobody`**, e ainda assim aceita apenas um envelope JSON exatamente igual ao pedido sintético permitido. Não confia num UID fornecido pelo JSON e não executa SQL de origem externa.
- Uma tentativa da conta do runner com o pedido válido recebe `PEER_UID_DENIED`. Uma tentativa de `DEPLOY` pelo UID `nobody` recebe `REQUEST_DENIED`.
- A conta `nobody` comprova `PermissionError` ao abrir DB para leitura/escrita e listar a pasta privada, **mas consegue conectar ao socket** e solicitar a conversa `A311 TEST...`; a conexão SQLite nunca é transmitida.
- Cada escritor termina após um pedido. O subprocesso é encerrado/recolhido mesmo em erro; não há serviço persistente, retries automáticos ou recursos pagos.
- Um segundo subprocesso recebe **o mesmo `request_id`** e cria outra conversa. Isso demonstra **ausência de deduplicação por intenção fora do host (P0-3)**.
- A conta que possui a pasta ainda pode abrir o DB diretamente e alterar as conversas sintéticas sem passar pelo socket. Não há isolamento contra admin, rollback ou cliente com o UID do escritor.

## Limites

Uma regra de `SO_PEERCRED` é **autenticação do principal do SO naquele socket**, não prova da identidade de uma pessoa, do titular da intenção, da autoridade de envio, da revogação, do ACK de um provedor ou de um histórico off-host imutável.

**P0-6 não está homologada.** Não há escritor operacional implantado com credenciais distintas, IPC com autorização de intenção resistente a replay, exclusividade sobre DB/WAL/SHM, identidade nativa VFS/FD (P0-5), idempotência semântica, recuperação de COMMIT incerto fora do host, custódia ou autorização independente.

No Windows, `SO_PEERCRED` Linux é **não aplicável**; o laboratório retorna explicitamente `WINDOWS_OR_LINUX_CREDENTIAL_TEST_UNAVAILABLE` e não afirma que SID/DACL ou Named Pipe foram auditados.

## Comportamento esperado dos testes

GitHub Actions Ubuntu passa `A314_REQUIRE_CROSS_UID_SOCKET=1`, que obriga o teste de duas identidades **reais** a ficar RED se faltar `sudo`, `nobody`, SO_PEERCRED, recusa de UID, negativa de arquivos, permissão de socket ou respostas do escritor.

O workflow Windows valida o contrato que sempre mantém HARD NO-GO, mas deixa casos de UID Linux marcados não aplicáveis. Executa regressões A313/A312/A311/A310/A309/A246/A247/A292/A293/A299.

Nenhuma avaliação sintética pode autorizar `resume`, `resend`, `auto_retry`, Worker, deploy, efeito real ou contar qualquer P0 como homologada.

## Próximo passo útil

Precisamos decidir a **arquitetura real de isolamento**: qual processo do AION terá conta de sistema proprietária do DB, como o Trader/Investimentos não terá acesso a DB/WAL/SHM, como o IPC atestará intenção e revogação do titular, e quais evidências independentes provam persistência/ACK. Antes disso, manter a PR em rascunho, sem integração e sem novos gastos.
