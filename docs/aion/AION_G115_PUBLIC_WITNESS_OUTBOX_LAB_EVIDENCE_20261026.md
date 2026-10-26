# AtlasQuant / AION G115 — Outbox e recibo de custodiante em processo separado (LAB)

**Data:** 2026-10-26. **PR:** #1605 Draft, base G114 #1604. **Status:** testes sintéticos aprovados, cinco requisitos A184 externos não homologados. **0/6 P0, HARD NO-GO.** Nenhuma mudança em Worker/main/deploy e nenhuma chamada a fornecedor real.

## Por que G115 existe

G113 executou o custodiante em outro processo e persistiu seu ledger local; G114 retirou a chave privada do objeto cliente e de argv, mantendo o signer em arquivo sob controle do processo assinador TESTE. Essas etapas provavam protocolo e persistência, mas não verificavam que o Outbox consumia as respostas corretas de pré-reserva, COMMIT e pós-reserva sem liberar um SEND inesperado.

G115 implementa **somente um callback opt-in de LAB**: `labs/a190/g115_public_witness_outbox_guard_lab.py`, compatível com `ExecutionOutbox.first_attempt_guard`.

1. Antes de iniciar, congela `event_id`, digest semântico da decisão original, escopo e o digest do efeito em memória local.
2. Exige status `ENROLLED` assinado pelo cliente G114 com nonce fresco, correspondência exata do original/escopo e high-water/contagem coerentes.
3. Solicita uma única reserva no outro processo, que a grava em SQLite antes de assinar `RESERVED`.
4. Requer a reserva assinada com o mesmo ID de evento, decisão, efeito, solicitação técnica e ordinal imediatamente posterior.
5. Reconsulta `status` usando novo desafio, exige que o mesmo evento conste como `RESERVED` com a mesma sequência e campos.
6. Só então permite **o adaptador em memória** do Outbox TESTE. Falhas de chave, divergências, duplicidade, timeout, resposta perdida e ausência de custodiante retornam `False`, levando a `UNCERTAIN` e zero chamadas ao adaptador.

A verificação não é uma transação atômica com o fornecedor, não impede alterações da custódia após a última leitura e NÃO comprova autenticidade do evento original, cuja inscrição vem do mesmo teste.

## Testes objetivos

[GitHub Actions G115 run 40368528744](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40368528744), fonte testada commit `41e18790c68a7af0954714f770a2a99571a3fa6e`:

| SO | Integração G115 | Regressões G114 | Job |
| --- | ---: | ---: | --- |
| Ubuntu | **11/11 PASS** | **15/15 PASS** | 121732672593 |
| Windows | **11/11 PASS** | **15/15 PASS** | 121732673021 |

Os 11 casos incluem: 1 envio pelo **adaptador falso**, evento não inscrito, ACK perdido depois de COMMIT com 0 envios, decisão semântica alterada, tentativa com novo ID técnico após perda do banco host, signer falso, troca da chave APÓS a reserva com 0 envios, serviço inacessível, quatro tentativas concorrentes com uma única admissão, pin original divergente e ataque de restauração do próprio ledger.

### Controle negativo obrigatório, sem autoengano

`G115_HOST_CONTROLLED_WITNESS_ROLLBACK=STILL_VULNERABLE_NOT_P0`.

O teste restaura os bytes do banco SQLite do próprio testemunho e mostra que o MESMO evento pode receber nova reserva e voltar a ser aprovado pela proteção G115. Logo, a proteção ainda pode ser contornada pelo administrador do host. O teste passar comprova **a existência dessa vulnerabilidade**, não sua remoção.

Outros limites: signer keyfile ainda está na mesma máquina; o cliente recebe uma instância de transporte fornecida pelo test harness; um ator que controla tanto o pin quanto o assinador pode forjar identidade; o registro inicial do evento de negócio não vem de uma autoridade externa protegida; callback LAB é opcional, não é enforce pelo Worker; o adapter usa `fake_confirmed` e não é fornecedor.

## Necessário para liberar P0

As cinco exigências externas de A184 permanecem sem provas: contador/custódia independentemente monotônicos; identidade original de negócio registrada fora da intenção local; raiz pública/trust pin administrado fora do host; prova assinada do snapshot/handle VFS vivo do SQLite; recusa nativa de escrita após restauração de bytes no MESMO inode.

O último conjunto **canônico de Quality/Security do código original** aprovado antes de G114/G115 foi G112 [run 40362610483](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40362610483) no Windows e G111 [A184 run 40362029628](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40362029628) no Ubuntu. G114/G115 somente adicionam módulos e workflows opt-in LAB; as baterias canônicas completas **não foram reexecutadas nestes PRs**, não declarar resultados inéditos.

**0/6 P0 homologadas. HARD NO-GO. Sem merge/deploy/Worker, sem SEND real, sem fundos e sem contratação/provisionamento de infraestrutura externa.**
