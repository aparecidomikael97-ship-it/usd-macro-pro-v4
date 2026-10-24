# A190 G5 — morte REAL de processo ao redor do COMMIT e reinício do leitor

**Data do proprietário:** 2026-10-23. PR Draft empilhada sobre G4 #1491, missão #1486. Todas as operações são de laboratório em diretórios temporários, sem efeito real.

## O que há de novo além de G0–G4

- A189 demonstrou inconsistência de witness SQLite local e rollback conjunto.
- G2 demonstrou que root/admin restaura piso local conjunto e reautoriza história.
- G3 demonstrou duplicação semântica por IDs autoalegados após ACK incerto.
- G4 demonstrou os efeitos do WAL/SHM, leitor aberto, pathname/handle e backup parcial entre Linux/Windows.
- **G5 exercita um processo-filho real** com PID distinto: a criança abre SQLite WAL, chega a barreira com transação pendente ou COMMIT já confirmado e permanece viva esperando ACK. O pai confirma a barreira através de um marcador, executa kill somente naquele subprocesso sintético e usa **um NOVO processo** para consultar o DB. O pai não recebe ACK final. Também testa o SQLiteChatStore verdadeiro do AION neste modelo.
- Esta prova de morte de processo **NÃO** equivale a perda de energia, corrupção de disco, desligamento do SO, garantia de fsync de hardware ou reboot real H0.

## Matriz de casos predefinida

| Controle | Estímulo real | Comportamento esperado | Limite |
| --- | --- | --- | --- |
| G5-1 | Filho executa INSERT sem COMMIT, mantém transação aberta, pai mata processo | Novo processo SQLite conta zero rows; pai assume UNCERTAIN, zero auto resend | SQLite local, sem efeito externo |
| G5-2 | Filho executa INSERT + COMMIT, sinaliza barreira antes de ACK final, pai mata processo | Novo processo SQLite encontra row1; pai continua UNCERTAIN, zero auto resend | Row existente não prova se fornecedor executou |
| G5-3 | Após G5-2, o próprio host restaura snapshot anterior e descarta WAL/SHM locais, sem handles vivos | Novo processo conta zero e reserva original passa NOVAMENTE | **RED:** sem piso independente, rollback autoriza nova primeira tentativa |
| G5-4 | Após G5-2, ID original duplicado via outra request e depois ID renomeado com mesmo hash | Mesmo event_id negado por UNIQUE; ID distinto passa | **RED:** idempotência por campo autoalegado ainda permite duplicação |
| G5-5 | Filho usa SQLiteChatStore REAL, grava conversa via WAL, pai mata antes de ACK | Novo SQLiteChatStore encontra conversa sintética | Demonstra persistência de linha, não H0 end-to-end |

**Observação crítica:** nenhum desses casos faz comunicação com fornecedor, cobrança, envio, operação financeira ou manipulação do Worker. O valor UNCERTAIN é política assertada no controle do pai; não existe um sinal de ACK independente nesta fixture. Qualquer sucesso do teste reproduz a vulnerabilidade/limite, não a corrige.

## Cobertura ampliada de regressão

Workflow dedicado Ubuntu + Windows, Python 3.12: cinco G5 + cinco G4 + seis G3 + dez A189 + quatro A185 = **30 testes por SO**, 60 execuções se ambos PASS. Cada subprocesso é criado e encerrado dentro de um TemporaryDirectory por teste; sem contas reais.

CI **ainda não verificada** na criação deste texto. Exigir run ID, SHA, logs individuais e falhas preservadas antes de contar evidência. Não executar Quality/Security completas ou declarar que cinco external-RED por SO e 43 advisories foram corrigidas.

## Gate real H0/P0 ainda necessário

- Custodiante monotônico fora do host e da conta restaurável, com raiz/epoch fixada e sem re-enrollment por destruição.
- Testes com hardware/OS e modelo de falha de energia definidos: flush/fsync, WAL/SHM, inode/ABA, restauração de snapshots sob lease/epoch revogado e restart H0 real, não apenas término de processo.
- Provedor com idempotência de evento original autenticado, recibo de efeito independente e reconciliação de ACK perdido; operador humano em caso indeterminado.
- Gate obrigatório de FD/VFS e conexões AION nativas, sob identidades/políticas OS reais; nenhum hook Python opt-in substitui isso.

**Estado inalterado:** 0/6 P0 homologados; HARD NO-GO; UNCERTAIN; ZERO_AUTO_RESEND; sem main/merge/deploy/Worker, cliente, conta, credencial, contratação ou custo novo.
