# Memória → checkpoint → origem → witness → CAS → recuperação

Contrato offline: `recovery.review_recovery`. Referências duráveis reutilizadas: `ReferenceIsolatedSqliteWitnessCAS`, journal one-shot UNKNOWN, `PersistentNonceRegistry` e dual-domain signed challenge. Não é criado outro outbox/CAS/dispatcher. Nenhuma referência é ligada ao source gate de produção.

## Modelo de confiança

Um SHA de GitHub identifica conteúdo, não custódia independente nem head atual. Um digest local ou assinatura válida de chave fornecida pelo mesmo chamador também não prova origem independente. SQLite separado testa atomicidade local, mas operador privilegiado pode restaurar simultaneamente ledger, registry e witness. A prova faltante é uma raiz e high-watermark protegidos sob domínios administrativos distintos, com matrícula, revogação e leitura causal autenticada.

O modelo simulado exige duas heads fechadas, domínio e credencial distintos, mesmo vínculo owner/tenant/workspace/device/recurso, operação e request digest, nonce, snapshot e efeito causal, geração monotônica, freshness inferior a 60 s e revogação conhecida. Rejeita head abaixo do floor, forks, saltos sem histórico e mudança de epoch sem recuperação separada. Mesmo o match é `REFERENCE_CAUSAL_MATCH_UNTRUSTED` e não permite retry. Os IDs de domínio são descrições de fixture, não prova de separação real.

## Futuro protocolo externo

Intenção durável exata → claim/CAS de uso único → estado UNCERTAIN antes do efeito → observação causal externa → confirmação independente. Cada etapa liga operação, geração, conteúdo, recurso e precedente. Um erro/timeout/404/presença local não autoriza repetir. Após queda, somente leitura autorizada, fresca e nonce-bound de ambos os domínios pode reconciliar. Falha entre domínios, versão/retention ambígua, falta de cabeçalho ou revogação mantém quarentena. Aprovação humana não transforma ausência de evidência causal em prova de que nada aconteceu.

Epoch novo exige autorização de recuperação e prova dos floors anteriores, custódia/revogação independente e continuidade de histórico. Não há incremento silencioso que apague uma operação incerta. Testes locais de restore demonstram detecção apenas contra um anchor/floor fornecido fresco: restaurar todas as fontes autorreferidas pode continuar passando matemática. Esse controle negativo é mantido como limite, não eliminado para produzir verde.

## Falha real corrigida na referência

Commit SQLite concluído seguido de erro anteriormente dizia rollback e zero appends. Agora retorna UNKNOWN e contagem indisponível. Os testes fazem commit real, falha na confirmação, reabertura independente em outro processo e leitura do mesmo operation ID, sem outro append e sem provider. Concorrência entre quatro processos produz um único vencedor; payload conflitante ou outro tenant é recusado. Erro no rollback também fica UNKNOWN e não vaza exceção bruta.

Os testes não provam durabilidade contra perda física de disco/energia, storage de outro provedor, rollback de administrador, relógio confiável, key custody ou consenso entre máquinas. Nenhum desses itens é liberado pela PR. Operações antigas continuam precisando de identidade e evidência causal originais.

## Condições de aceite externo ainda pendentes

Custódia separada demonstrada; matrícula autenticada; retenção configurada e verificada; head atual com versões/paginação/delete markers; CSPRNG/replay entre reinícios; CAS externo concorrente; PITR/fork/crash entre domínios; plano de revogação e break-glass; autorização de custo/privacidade; ensaio físico aprovado. Não executar esses procedimentos nesta fase.
