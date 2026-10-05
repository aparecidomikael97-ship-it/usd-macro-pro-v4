# ADR-0021 — Core Freeze exige preflight ligado ao Checkpoint Mestre exato

- Título: Core Freeze exige preflight ligado ao Checkpoint Mestre exato
- Data: 2026-10-04
- Status: ACCEPTED

## Contexto

V2.20 certifica tecnicamente o núcleo e V2.21 prepara o review final, mas uma decisão
crítica não deve ser aplicada a um estado diferente daquele que foi revisado.

## Problema

Entre review e eventual decisão do proprietário pode ocorrer alteração de código,
certificado, checkpoint, memória ou estado operacional.

Aceitar uma decisão sem binding ao estado exato criaria risco de TOCTOU.

Também seria inseguro interpretar um simples "vamos lá" operacional como autorização
de Core Freeze.

## Alternativas consideradas

Foram rejeitados:

- freeze direto após CI verde;
- decisão baseada apenas no SHA;
- decisão sem binding ao Checkpoint Mestre;
- decisão baseada em review não persistido;
- challenge sem expiração;
- decisão predefinida no challenge;
- captura biométrica passiva;
- assinatura privada armazenada no repositório;
- merge/deploy automático depois da decisão.

## Decisão

V2.22 introduz um Core Freeze Ceremony Preflight read-only.

O preflight:

- reverifica a cadeia V2.20/V2.21;
- exige o review V2.21 correspondente no Checkpoint Mestre fornecido;
- liga a futura decisão ao digest/revision/state digest exatos do Checkpoint;
- emite challenge curto com nonce e ceremony id;
- deixa a decisão como `UNDECIDED`;
- mantém `owner_decision_ready=false` e `digest_to_sign=""` enquanto não houver prova de persistência externa;
- produz apenas material de preflight para futura cerimônia explícita do HUMAN_OWNER;
- revalida o Checkpoint antes de qualquer futura decisão.

## Consequências

A sequência passa a ser:

1. certificação V2.20;
2. review V2.21;
3. persistência explícita do review no Checkpoint Mestre;
4. preflight lógico V2.22;
5. prova/attestation da persistência externa do estado exato;
6. decisão explícita do HUMAN_OWNER;
7. eventual registro da decisão;
8. Core Freeze separado;
9. merge/deploy separados;
10. runtime activation separada.

Nenhuma etapa implica automaticamente a próxima.

## Componentes afetados

Core Certification, Core Completion Review, Checkpoint Mestre, futura assinatura do
proprietário, CI e processo de Core Freeze.

## Segurança

- challenge é ligado ao estado exato;
- mudança do Checkpoint invalida o preflight;
- janela temporal é limitada;
- decisão permanece UNDECIDED;
- biometria/FIDO2 não é capturada nesta camada;
- chave privada não entra no repositório;
- approval não é execution authority;
- freeze não é merge/deploy;
- nenhuma ação externa é executada.

## Compatibilidade

Compõe ADR-0002, ADR-0007, ADR-0009, ADR-0011, ADR-0012, ADR-0019 e ADR-0020.

## Rollback/migração

Ativar assinatura real, registrar owner decision ou executar Core Freeze exige camada
posterior explícita e novos testes.

## PR/commit relacionado

Branch `integration/aion-v222-core-freeze-ceremony-preflight-20261004`.

## Supersedes

Nenhum.

## Superseded by

Nenhum.


## Limite descoberto na auditoria V2.22

O envelope `atlasquant_aion_checkpoint_master` não é, por si só, prova de save no
runtime oficial de `atlasquant_aion_memory`. O runtime possui receipt/reconciliação
próprios, mas não há nesta versão uma bridge de persistência entre os dois contratos.

Consequentemente, V2.22 termina em `READY_FOR_OWNER_DECISION_PREFLIGHT`, nunca em
owner-decision readiness real.
