# G133 — Rollback do SQLite operacional + ExecutionOutbox real (LAB)

**Status: NÃO HOMOLOGADO / HARD NO-GO.** PR empilhada sobre o G132 #1624, somente laboratório.

## Diferença em relação ao G132

O G132 exercitou SQLite real com uma tabela de reservas reduzida. O G133 exercita **as classes reais `aion_chat.store.SQLiteChatStore` e `atlasquant_aion_execution_outbox.ExecutionOutbox`**, incluindo sua tabela `semantic_reservations_lab`, a decisão, a Outbox e a confirmação local. O teste usa um escopo, uma política e dados totalmente sintéticos. Não é um host operacional instalado nem invoca Worker, rede ou provedor.

1. Com histórico intacto, dois `intent_ref` diferentes para o mesmo `semantic_event_id_lab` são negados localmente (colisão esperada).
2. Snapshot real feito via SQLite `backup()`, restauração do DB/WAL/SHM depois do fechamento dos handles; um `intent_ref` relabelado para o mesmo evento pode entrar novamente. O `idempotency_key` muda.
3. Após a restauração, os callbacks fornecidos pelo chamador **continuam bloqueados por padrão**: `dispatch_claimed` retorna `UNCERTAIN`, zero acesso ao `MemoryOnlyAdapter.send`. Esse bloqueio de envio é uma defesa real do comportamento padrão, mas não restaura a identidade histórica apagada.
4. Somente com `unsafe_allow_synthetic_lab_callbacks=True`, condição explicitamente insegura para produção, dois despachos são simulados contra **um objeto Python com contagem de chamadas**. `CONFIRMED` e efeitos são fictícios; este é um controle adversarial negativo.
5. O pedido técnico original também é admitido após a reversão completa. A ausência de reserva após rollback **não comprova** ausência de efeito externo.

## Limites explícitos

- O teste verifica o armazenamento SQLite/Outbox real, porém **não** o runtime completo do AION nem uma implantação. Não realiza efeitos reais.
- O snapshot é feito em banco quiescente e conexão fechada; não testa attestation de file descriptor nativo vivo, inodes equivalentes ou recuperação após perda de energia.
- Não existe autoridade externa, chave confiável, provedor de efeito real, identidade original autenticada, contador monotônico externo ou teste de administrador/root hostil.
- G122 deve continuar com 5 falhas genuínas por SO sem mascarar qualquer requisito. G125 e regressões herdadas exigem logs exatos do SHA.
- **0/6 P0; HARD NO-GO; UNCERTAIN / ZERO_AUTO_RESEND.**

## Aceitação futura

Demonstrar uma única reserva semântica vinculada à origem autêntica de `HUMAN_OWNER` e mantida por custodiante **fora do domínio de rollback do host**. Repetir o mesmo ensaio de restauração conjunta e obter recusa verificável **do custodiante**, sem reenvio e sem substituição local da raiz de confiança. Só então avaliar uma P0; não antecipar fechamento.

Relação: #1486 (A190), #1477 (A185), #1624 (G132). Nenhum merge, deploy, conta, chave externa, custo ou operação real.
