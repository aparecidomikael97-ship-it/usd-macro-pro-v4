# A236 — Marcador de tentativa pendente para interrupção real do processo SQLite

**Escopo:** mudança apenas na rotina SQLite de **staging**, em branch isolada Draft. **HARD NO-GO · seis P0 em aberto (0/6) · \`UNCERTAIN=ZERO_AUTO_RESEND\`**. Sem Worker, deploy, fornecedor, cliente real, chaves, pagamentos ou contatos externos.

## Falha residual depois do A235

A234 eliminou \`os.replace()\` em favor de \`os.link()\` (criação somente se ausente); A235 distinguiu exceção **depois** da publicação de uma falha sem efeito. Mas \`os._exit\`, falha do processo ou encerramento forçado não executam o bloco \`except\`, nem permitem devolver \`RestorePublicationUncertainError\`. Se o processo termina **depois de preparar a cópia, antes da publicação**, um novo processo poderia tentar outra vez sem reconhecer a tentativa interrompida.

## Mitigação real, restrita à API staging

1. O destino também é recusado quando existe \`<destino>.aion-restore-pending\`. Um marcador é sempre um **veto**, jamais uma autenticação externa.
2. Após verificar a origem e o banco temporário, e imediatamente antes de publicar, a rotina cria o marcador com \`Path.open("xb")\` para impedir sobrescrita concorrente. Escreve \`AION_STAGING_RESTORE_PENDING_V0\` e \`NO_AUTO_RETRY\`, faz \`flush()\` e \`os.fsync()\` do próprio arquivo.
3. Somente então chama \`os.link(temp,target)\`. Se o processo morrer antes ou depois desse ponto, o marcador deve continuar no disco em condições normais de **término de processo sem perda elétrica**.
4. Se publicação e verificações locais terminarem, a rotina remove o temporário e, por último, seu próprio marcador. Erros de remoção **depois de publicar** causam \`RestorePublicationUncertainError\`, preservando veto e destino.
5. Um marcador pendente não é retirado automaticamente em nova execução. A recuperação exige análise de evidência e procedimento específico, fora deste LAB.

**Delimitação decisiva:** \`fsync()\` do arquivo **não** garante persistência do nome no diretório sob corte de energia, sem barreiras/garantias de filesystem. Um administrador hostil pode remover ou falsificar o marcador. A proteção não prova a identidade do VFS/handle, não impede swap no mesmo inode nem constitui testemunha H0 independente. A recuperação do P0-3/4 e o pós-COMMIT do P0-6 **continuam abertos**.

## Verificação adversarial reproduzível

\`labs/test_a236_sqlite_restore_crash_fence.py\` adiciona **15 testes**, incluindo:
- Um **subprocesso Python real** terminado com \`os._exit(71)\` logo antes de \`os.link\`; o destino está ausente, o marcador persiste e a tentativa seguinte é recusada;
- Um segundo subprocesso terminado com \`os._exit(72)\` logo após \`os.link\`; o destino existe, o marcador persiste e a tentativa seguinte não repete a restauração;
- Falha ao criar o marcador, \`fsync()\` injetado, publicação recusada, erro ao remover marcador, sidecar órfão, isolamento de destinos diferentes;
- Caso normal, com marcador removido somente depois de verificação local, e regressões A234/A235.
- **1.080 testes por sistema esperados**: 15 novos + 1.065 acumulados A235, a confirmar por logs Ubuntu e Windows no PR.

Nenhum subprocesso chama Worker ou API externa; apenas arquivos SQLite sob \`TemporaryDirectory\`.

## Garantias não alcançadas

Este contrato não apresenta uma solução para:
- Host com privilégios capazes de apagar/copiar/restaurar tudo, incluindo marcador;
- Queda de energia real, não realização de \`fsync()\` do diretório, storage controller que ignore flush ou WAL perdido;
- Reconciliação de COMMIT incerto com efeito externo;
- Prova nativa de VFS/FD, chaves de custódia ou autoridade independente.

O marcador é **uma trava local conservadora**, não uma homologação da fonte ou do efeito.

**Status obrigatório:** A236 somente LAB, P0 0/6, HARD NO-GO e \`UNCERTAIN=ZERO_AUTO_RESEND\`. Mesmo com CI verde, nenhuma ativação, merge ou deploy.
