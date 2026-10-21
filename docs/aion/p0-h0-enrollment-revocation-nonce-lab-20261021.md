# AION H0 LAB — matrícula, revogação e desafio sintéticos (21/10/2026)

**Apenas LAB. Não concede confiança externa, autorização operacional, integração, compra, deploy ou ativação.** Este bloco sucede as PR Draft #1380 (dois recibos Ed25519, sob chaves fornecidas pelo chamador) e #1381 (grafo declarativo de controle administrativo).

## O que foi implementado

`atlasquant_aion_p0_h0_enrollment_revocation_nonce_lab.py` examina três envelopes canônicos assinados em simulação:

1. **Matrícula** — duas chaves públicas distintas, papel de reserva e papel de leitura, identidade declarada, escopo, época, sequência e versão de registro.
2. **Instantâneo de revogação** — assinado pela mesma raiz de registro sintética, vinculando o SHA-256 dos bytes da matrícula; exige ordem de sequência, conjunto de chaves ativas, ausência de revogação de qualquer chave necessária e mesma época.
3. **Desafio de custódia** — assinado por outra chave sintética, vincula o hash do instantâneo de revogação, contador de custódia, nonce, solicitação, intenção, escopo, época, sequência e cabeça declarada do histórico.

As chaves da raiz do registro e do custodiador são fornecidas pelo **próprio chamador** (`caller_pinned_fixture`); o horário `now_utc` também. Todos os envelopes aceitos são somente **assinaturas matematicamente válidas sob chaves de LAB**. Não há emissão real, fonte da verdade externa, consumo atômico de nonce, anti-rollback físico, relógio autenticado, comprovação de última versão remota, revogação online nem assinatura de provedor.

A validação rejeita representações Base64URL não canônicas, campos adicionais, tipos hostis, datas inconsistentes, épocas e sequências divergentes, chaves compartilhadas entre papel/custódia, nonce vencido e revogações. O resultado, inclusive para três envelopes perfeitamente coerentes, é **`HARD_NO_GO` e `allowed=False`**; todas as 16 flags de autoridade permanecem falsas.

## Limitação proposital — vínculo faltante

A matrícula desta etapa **ainda não foi conectada** aos dois transcritos da PR #1380 para conferir que as chaves da reserva e da leitura são exatamente as inscritas no registro sintético. Os ensaios de assinatura e matrícula são separados. O próximo gate integrado deve verificar isso e vincular o desafio assinado ao `challenge_nonce` do readback, sem transformar o fixture em autoridade.

Uma assinatura de revogação não prova que se está vendo o **último** estado; um atacante pode reapresentar uma versão antiga, assinada e formalmente válida, se também controlar os valores mínimos fornecidos pelo chamador. O desafio não prova que seu nonce é aleatório, único, durável nem consumido fora do executor. A verificação de uma janela de tempo contra `now_utc` fornecido pelo chamador não é frescor autêntico.

## Condições externas para homologação futura

- Registrar chaves-mestre previamente **fora** da máquina/conta de execução, mediante identidade e autorização do HUMAN_OWNER verificadas por canal independente.
- Obter mapa comprovado de superadministradores, recuperação/MFA, faturamento, IAM e controle indireto, inclusive se dois provedores compartilham uma identidade ou sistema de recuperação.
- Consultar, com verificação independente, a época e a revogação **mais recentes**; bloquear indisponibilidade, conflito, conta restaurada, perda de histórico ou chave substituída.
- Exigir geração, reserva e consumo atômico persistente do nonce em domínio protegido do rollback; não transformar `UNKNOWN` em `NO_EFFECT_FENCED`.
- Exigir confirmação causal do fornecedor externo, readback de versão precisa e prova independente de cabeça mais recente; preservar `ZERO_AUTO_RESEND`.
- Realizar ensaio físico de recuperação e reexecutar Quality/Security canônicas, sem dispensas de falhas históricas.

## Isolamento e evidência

Branch separada de LAB, PR Draft empilhada sobre #1381; nova bateria de **56 métodos adversariais** e regressões de #1380/#1381, custódia e H0 A79 em Ubuntu/Windows. O número de casos e seu estado só devem ser declarados como aprovados após inspeção de CI do **mesmo SHA da PR final**.

**0/6 P0 homologados · HARD NO-GO · Worker OFF · ZERO_AUTO_RESEND · sem merge/deploy/serviço/conta/credencial externa/custo.**
