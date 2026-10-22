# A175 — Reserva semântica de intenção (somente LAB)
**22/10/2026 | baseada na A174, PR #1464 | HARD NO-GO | P0: 0/6**

## Falha caracterizada
Na A174, duas requisições com request_id diferentes podiam representar o mesmo efeito de negócio e criar duas reservas. O hash do payload isolado tampouco identifica necessariamente o efeito.

## Candidata A175
O método LAB `LocalWriteReservationLab.reserve(request_id, payload_sha256, effect)` **exige** um descritor de identidade do evento com as quatro chaves exatas `tenant`, `provider`, `action`, `business_id`. O descritor só aceita tokens ASCII minúsculos com caracteres delimitados, rejeita campos ausentes e é serializado em JSON canônico, versão A175:v1. SHA-256 desse JSON vira `effect_digest`, com índice SQLite UNIQUE. A inserção da reserva do ID técnico e o vínculo semântico ocorrem na **mesma transação BEGIN IMMEDIATE**. O mesmo evento com request_id distinto deve ser negado; um evento realmente diferente deve continuar possível.

O schema antigo A174, que não possui vínculo semântico, entra em quarentena com `JOURNAL_LEGACY_SCHEMA_UNBOUND`: não ocorre migração silenciosa nem exclusão automática de reservas desconhecidas. `PENDING` e `UNKNOWN` permanecem bloqueantes; não existe transição automática para autorização de reenvio.

## Provas candidatas / expectativa em CI
- request ID igual: replay negado; hash diferente: negado.
- mesmo `effect` com ID distinto: `SEMANTIC_EFFECT_ALREADY_RESERVED`.
- `UNKNOWN` + reinício + ID distinto do mesmo evento: negado.
- corrida de duas requisições para um evento: só uma reserva.
- evento legitimamente distinto: aceito, evitando bloquear tudo.
- banco legado sem `effect_digest`: falha fechada.
- campo semântico omitido/inválido: rejeição.
- **contraexemplos não resolvidos:** (a) apagar completamente o diário e reinicializar aceita novamente a intenção, (b) fornecedor/chamador pode falsificar um novo `business_id` para o mesmo efeito verdadeiro. Esses são testes adversariais verdes porque confirmam a vulnerabilidade, não porque foram corrigidos.

## Limites e dependências
Este hash identifica somente o descritor **declarado** pelo chamador. Não autentica o `business_id` real, não garante uma idempotência semântica entre provedores nem substitui recibos externos verificáveis. Não há raiz de confiança independente, custódia física, proteção contra rollback do arquivo SQLite, vínculo atômico ao FD SQLite, nem reconciliação de efeito real.

A construção é isolada: módulo de LAB não conectado à fachada operacional, Worker, pagamentos ou clientes; sem autorização de efeito externo. `ZERO_AUTO_RESEND` e revisão humana obrigatória. Nenhum merge/deploy/custo ou alteração na main.

## Referência de aceite do futuro P0
Para considerar P0-3 e P0-4 aptos à homologação, exigir reserva semântica estável derivada de uma fonte confiável, testemunha monotônica independente cuja indisponibilidade bloqueie qualquer tentativa, recibo de operação do provedor com autenticação verificável e reconciliação efetiva depois de restart/rollback. CI verde sozinho **não** atende esses critérios.

## Evidência conferida em 22/10/2026
CI final [GitHub Actions #39865960416](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39865960416) = **SUCCESS: Ubuntu 93/93, Windows 93/93** (186 execuções).

Observações repetidas nos dois sistemas:
- `A175_SAME_EFFECT_NEW_ID=DENIED`: segundo request_id para o mesmo descritor canônico negado.
- `A175_UNKNOWN_RESTART_NEW_ID=DENIED`: trava persistiu após reinício simulado e mudança de ID.
- `A175_DIFFERENT_BUSINESS_EVENT=ALLOWED`: duas intenções legítimas com business_id diferente não foram bloqueadas.
- `A175_LEGACY_JOURNAL=QUARANTINED_NOT_MIGRATED`: schema A174 antigo não foi migrado silenciosamente.
- `A175_FORGED_BUSINESS_ID=REPLAY_ACCEPTED_NOT_ATTESTED`: falsificação de business_id contorna o gate. É contraexemplo deliberado.
- `A174_LOCAL_JOURNAL_DELETION=REPLAY_ACCEPTED_NOT_ATTESTED`: exclusão local segue permitindo reapresentar intenção.

Histórico dos ensaios: [#39865650549](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39865650549) falhou por constantes ausentes no protótipo; [#39865755060](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39865755060) passou Ubuntu, mas falhou Windows por fixture SQLite que mantinha o arquivo aberto; teste corrigido com fechamento explícito e todos os 93/93 repetidos nas duas plataformas.

**Veredito A175:** somente LAB. Bloqueio local de duplicação de descritor melhorou; sem verificação independente do evento real, anti-rollback externo ou controle operacional de reenvio. ZERO P0 homologados. CI específico não equivale à Quality canônica.

