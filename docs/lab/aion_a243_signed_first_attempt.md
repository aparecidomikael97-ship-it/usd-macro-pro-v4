# A243 — Reserva da primeira tentativa assinada Ed25519 (somente LAB)

Continuação da [A242 #1693](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/pull/1693). Reaproveita a hipótese da [A180 #1470](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/pull/1470) em novo módulo de **pesquisa isolado**, sem provisionar raiz real.

## O que valida

O `PinnedFirstAttemptWitnessLab` verifica uma resposta de reserva de primeira tentativa **antes** de permitir `adapter.send` pela interface A242:

- Assinatura Ed25519 sob chave pública fixada pelo fixture LAB e domínio de assinatura A243;
- Desafio aleatório de 256 bits e vínculo a `idempotency_key`, digest da decisão, digest semântico declarado e owner/tenant/workspace;
- `RESERVED` com issuer/key ID esperados, sequência acima do high-water local, validade temporal curta e chave não revogada;
- Recusa assinatura, nonce, escopo, hash, tempo, sequência ou esquema inválidos; recusa witness indisponível e ACK perdido;
- `UNCERTAIN=ZERO_AUTO_RESEND` quando o pré-envio não obtém confirmação válida;
- Todas as assinaturas privadas nos testes são **bytes sintéticos fixos**, sem raiz, chave, serviço ou segredo operacional.

## Evidência adversarial que impede homologação fictícia

Três cenários propositalmente demonstram que a assinatura sozinha não fecha P0:

1. **Rollback da própria testemunha:** apagar a memória de reservas e reiniciar `high_water=0` permite assinar novamente o mesmo efeito declarado sob outro request ID.
2. **Repinagem pelo próprio host:** quem troca a chave pública esperada pode aceitar a assinatura do atacante como se fosse raiz autêntica.
3. **Identidade semântica insuficiente:** eventos legítimos com atributos iguais podem ser bloqueados como duplicados; alterar descritores pode escapar do pareamento. Falta ID de evento imutável de origem independente.

Estes casos têm teste **GREEN como contraprova de segurança**: um teste verde que detecta uma vulnerabilidade não significa que ela tenha sido corrigida.

## Bateria e limites

16 testes novos com SQLite real, adapter exclusivamente sintético e Ed25519 real em memória; somados aos **1.150** testes A242, previsão de **1.166 por SO** Ubuntu/Windows, pendente de conferência dos logs.

Não há bootstrap de confiança externo, custódia separada, relógio independente, H0 resistente a rollback, idempotência de provedor, recibo pós-COMMIT, identidade HUMAN_OWNER validada ou binding nativo FD/VFS. O verificador LAB não é conectado a Worker ou provedor real.

**HARD NO-GO · P0 0/6 · UNCERTAIN=ZERO_AUTO_RESEND · sem merge/deploy/Worker/contratação/operação real.**
