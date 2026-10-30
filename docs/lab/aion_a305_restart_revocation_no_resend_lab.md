# A305 — Reinício com COMMIT incerto e revogação posterior (LAB)

**HARD NO-GO · ZERO_AUTO_RESEND · 0/6 P0 homologadas · sem contratação nova.**

## Objetivo

A304 documentou que um status de custódia assinado e revogado, expirado, conflitante ou indisponível precisa bloquear recuperação. A300 mostrou que um snapshot só do banco pode perder o marcador de ACK incerto. A305 combina essas duas situações **no mesmo ensaio isolado**, para caracterizar como uma autorização anterior ao incidente pode ser reutilizada indevidamente.

## Experimento com SQLite real (somente dados temporários)

1. Cria uma conversa de teste na instância real `SQLiteChatStore`.
2. Injeta perda **sintética** de ACK depois de um COMMIT que efetivamente armazenou uma mensagem identificada por ID estável.
3. Confere que a mensagem está armazenada e a origem mantém o marcador bloqueante `.aion-message-commit-pending`.
4. Fecha a conexão e verifica que a origem recusa reabrir com esse marcador.
5. Cria via API nativa do `sqlite3` um backup **apenas lógico do banco** em pathname diferente, sem usar os métodos operacionais de restore. Esse arquivo reabre HEALTHY e contém a mensagem, **mas perdeu o marcador**.
6. Apresenta ao contrato A305 status A304 antes e depois do incidente, assinados por chaves **sintéticas**. Inclui um status ACTIVE anterior e uma revogação posterior com sequência e hash do anterior.
7. Toda tentativa de RESUME ou RESEND permanece bloqueada. Não executa tentativa nem efeito externo.

## Regras testadas

- COMMIT confirmado por SQLite e ACK incerto não autoriza novo envio.
- Status ACTIVE anterior à falha não sobrepõe status REVOKED/SUSPENDED posterior.
- Novo status ACTIVE corretamente assinado também **não** resolve a ambiguidade de COMMIT.
- Não existe recuperação ao usar o mesmo recibo ACTIVE antigo (replay).
- Sem resposta atual da custódia, com status expirado, assinatura falsificada, fork de status assinado ou geração do incidente antiga, a decisão permanece bloqueada.
- Snapshot trasladado com marcador ausente deve registrar explicitamente o risco de perda do veto.
- Ação de revisão de leitura (`READ_ONLY_REVIEW`) continua diferente de liberação operacional.
- Nenhum campo externo, IP/host ou timestamp fornecido pelo chamador serve como prova de autoridade real.

## Limites

Este é um **classificador de recusas de pesquisa**, não um gate ativado no runtime. Embora use o `SQLiteChatStore` com SQLite real para reproduzir incerteza, o contrato não autentica o FD/VFS, não prova custódia fora do host e não mede queda física de energia.

As chaves Ed25519, marcadores de sequência e horários são auto-gerados por fixtures de LAB. O relatório observa coerência criptográfica mas nunca conclui identidade do proprietário, revogação fresca independente ou permissão. `can_resume=False`, `can_auto_retry=False`, `can_authorize_real_effect=False` são invariantes da A305.

Nenhuma P0 homologada, sem merge, Worker, deploy, provider, ordem de Trader, real backup/restore, custo ou mudança em produção.

## Validação

Python 3.12 em Ubuntu e Windows. Testes A305 + regressões A304/A303/A302/A301/A300/A299/A293/A292. Biblioteca open-source cryptography instalada apenas em CI. Os testes demonstram respostas negativas sob as condições sintéticas; verde **não** equivale a GO operacional.

**Próxima dependência real:** uma raiz de confiança e sequência/revogação monotônica independentes, mais uma política de reconciliação manual de intenções com ACK desconhecido. Esses requisitos permanecem pendentes.
