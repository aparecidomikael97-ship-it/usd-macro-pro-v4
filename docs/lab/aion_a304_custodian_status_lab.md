# A304 — Custódia indisponível, revogação, expiração e equívoco (LAB)

**HARD NO-GO. ZERO_AUTO_RESEND. P0 homologadas: 0/6. Sem contratação.**

## Escopo

Pesquisa de contrato, sem operação real, PR draft empilhada na A303. Não edita `aion_chat/store.py`, não altera o banco do usuário, não faz backup/restauração operacional e não ativa Worker, deploy, ordens ou envio externo.

### Novidade

A303 introduziu âncora sintética assinada da raiz que vincula duas testemunhas, o manifesto do SQLite, época de chaves e sequência de incidente. A304 estuda a **situação de revogação e continuidade**, com outro recibo Ed25519 **também sintético** assinado por suposta autoridade de status.

Cada status inclui:
- Identificador da chave de status e da raiz vinculada;
- Identificador sintético do proprietário, origem e hash da âncora A303;
- Época da chave e geração do incidente;
- Sequência do status e hash do status anterior (ambos informados pelo chamador);
- Intervalo temporal limitado a até 15 minutos;
- Decisão: `ACTIVE`, `SUSPENDED`, `REVOKED`;
- Assinatura Ed25519 com separador de domínio.

A checagem recusa ausência de status, suposta autoridade indisponível, expiração, status futuro, assinatura falsa, chave trocada, chave de status igual à raiz, replay, hash anterior incompatível, incidente reaberto, chave ou raiz alterada, status `REVOKED` ou `SUSPENDED`, e **equivocação**: dois documentos diferentes assinados pela mesma chave, sobre a mesma sequência.

### Limites de segurança que não podem ser omitidos

- Mesmo um recibo `ACTIVE`, válido criptograficamente, NÃO prova que não ocorreu revogação posterior.
- As chaves, horário atual, sinal de conectividade e head anterior são **fornecidos pelo mesmo host** nos testes. Nenhum deles autentica autoridade externa, nem prova acesso recente a um serviço.
- Duas certidões assinadas contraditórias são evidência de conflito a exigir revisão, não permissão de escolher a mais conveniente.
- `cryptographic_status_count` conta apenas assinaturas válidas; `local_status_consistent=True` diz somente coerência LOCAL.
- `independent_status_proven=False`, `off_host_head_proven=False`, `revocation_completeness_proven=False`, `can_resume=False` e `can_authorize_real_effect=False` são incondicionais.
- Um adversário que controle a raiz, as chaves, cabeçalhos e o relógio da máquina pode reconstruir uma história antiga autoconsistente. A A304 **não** elimina esse problema.

### Matriz

24 testes novos para diferença entre assinatura válida e disponibilidade real; status `REVOKED` / `SUSPENDED`, expiração e janela temporal inválida, dois status conflitantes igualmente assinados, duplicação, incidentes reabertos, alterações de âncora, replay e blocos operacionais. Regressões das A303/A302/A301/A300/A299/A293/A292 em Ubuntu/Windows Python 3.12, somente bibliotecas gratuitas para CI.

**Critério futuro externo:** registros monotônicos e confirmação fresca da revogação, autenticados por autoridade independente, com procedimento de indisponibilidade/reabertura. Até lá 0/6 P0, HARD NO-GO. Uma execução de testes verde NÃO é homologação.
