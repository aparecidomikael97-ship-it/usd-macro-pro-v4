# A301 — Contrato de evidência para recuperação (somente LAB)

**HARD NO-GO. P0 homologadas: 0/6. ZERO_AUTO_RESEND. Custo novo: nenhum.**
Branch isolada, PR draft empilhada na A300. Sem merge, Worker, deploy,
fornecedores, ordens, restauração operacional, extensões C ou efeitos externos.

## Finalidade

A300 demonstrou dois riscos reais com o SQLite staging: uma cópia só do .db
perde mensagens confirmadas quando ignora WAL, e a migração de um backup
apenas lógico não carrega o marcador local de ACK incerto.

A301 introduz um **validador experimental fail-closed** que recebe:
- Snapshot SQLite de teste, identificado pela conversa.
- Manifesto de hash SHA-256 do arquivo, tamanho, hash do histórico,
  identificador da fonte e geração mínima esperada.
- Diário sintético de intenções, com IDs semânticos, mensagem, sequência
  e estado ACKED ou ACK_UNKNOWN.
- Hash esperado do marcador local de ACK incerto, quando aplicável.
- Piso de geração informado pelo chamador e pretensa evidência externa.

Confere integridade com PRAGMA quick_check e foreign_key_check; cobre todas
as mensagens com as intenções e rejeita duplicação, ausência, troca de
conteúdo, manifesto alterado, origem trocada, geração velha e marcador
desanexado. Nenhum campo de aprovação booleana da mesma máquina é aceito
como testemunha externa.

## Casos concretos da matriz

1. Snapshot + manifesto + diário coerentes: coerência local identificada;
   **não pode retomar**, pois falta raiz de confiança independente.
2. Aprovação externa simulada ou forjada: não é reconhecida.
3. Diário faltante ou com efeito semântico duplicado: recusa.
4. Hash trocado e banco SQLite alterado depois do manifesto: recusa.
5. Geração antiga, source id diferente ou manifesto incompleto: recusa.
6. Marcador sintético ACK_UNKNOWN presente: apenas coerência local.
7. Mesmo banco recolocado em outro caminho SEM marcador: recusa explícita.
8. **Rollback conjunto de banco + manifesto auto-atestado**: ambos podem
   ser localmente coerentes, mas isso nunca comprova que o histórico
   apresentado é o mais recente. Continua recusado.

## Limites materiais

- A função assess_recovery_candidate retorna **can_resume=False sempre**.
  Sua classificação locally_consistent_only NÃO autoriza nenhuma operação.
- O manifesto local não tem assinatura verificada, custódia off-host,
  âncora monotônica ou identidade nativa FD/VFS atestada.
- Piso de geração é argumento local do chamador, não prova externa.
- Os marcadores neste LAB são sintéticos e gravados em TemporaryDirectory,
  não equivalem a uma recuperação de incidente real.
- Não implementa backup/restore de produção, física do fsync ou crash de
  hardware. Em particular, não fecha as P0-1 a P0-6.

## Verificação

Python 3.12 em Ubuntu e Windows; testes novos e regressões A300, A299,
A293 e A292. Testes verdes significam que negativas e barreiras de
contrato foram reproduzidas, **não** que o sistema está homologado.
