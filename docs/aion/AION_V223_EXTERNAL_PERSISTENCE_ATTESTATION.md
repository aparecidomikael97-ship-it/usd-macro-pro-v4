# AION V2.23 — External Checkpoint Persistence Attestation

## Objetivo

A V2.23 fecha a lacuna entre dois contratos diferentes:

1. o **Checkpoint Mestre lógico** de `atlasquant_aion_checkpoint_master`;
2. o **Checkpoint runtime persistido** de `atlasquant_aion_memory`.

A camada não executa persistência. Ela prepara um candidato em memória e, depois,
verifica evidências fornecidas por um fluxo externo já existente.

## Problema que V2.23 resolve

V2.22 consegue provar que:

- V2.20 foi certificado;
- V2.21 foi revisado;
- o Checkpoint lógico contém o review exato;
- o challenge V2.22 está ligado ao SHA/revision/state digest exatos.

Mas isso não prova que esse estado lógico foi persistido no runtime oficial.

V2.23 adiciona um binding compacto no namespace:

`aion_core_checkpoint_master_v1`

O binding carrega somente digests e metadados necessários para provar identidade do
estado. Ele não duplica o Checkpoint Mestre inteiro.

## Staging sem save

`stage_runtime_persistence_candidate()`:

- normaliza uma cópia do runtime checkpoint;
- injeta o binding V2.23 somente nessa cópia;
- calcula o `checkpoint_source_digest` esperado;
- marca que save explícito é necessário;
- mantém `external_persisted=false`;
- não usa rede;
- não chama rotina de save;
- não altera runtime real.

## Alvo runtime oficial

A attestation é presa ao alvo exato:

- repo: `aparecidomikael97-ship-it/usd-macro-pro-v4`;
- branch: `atlasquant-runtime`;
- path: `dados/aion/checkpoint_master.json`.

Receipt de outro repo, branch ou path é bloqueado, mesmo que o restante do conteúdo
seja estruturalmente válido.

## Attestation

`verify_external_checkpoint_persistence()` aceita:

- Checkpoint Mestre lógico;
- preflight V2.22;
- cadeia de certificação/review;
- observação runtime confirmada;
- write receipt do fluxo de persistência existente;
- horário atual.

Ela exige simultaneamente:

- preflight V2.22 ainda CURRENT;
- binding runtime idêntico ao estado lógico;
- digest interno do binding válido;
- runtime status CONFIRMED;
- runtime SHA válido;
- observação runtime fresca;
- target do receipt completo;
- branch runtime permitida;
- source do runtime igual ao target do receipt;
- `reconcile_runtime_write()` retornando `CONFIRMED`;
- `verified=true`;
- `write_attributed=true`;
- digest do runtime igual ao receipt;
- write SHA igual ao SHA observado.

Conteúdo coincidente sem atribuição de escrita não basta.

## Estado positivo

Quando toda a evidência é válida:

`READY_FOR_OWNER_SIGNATURE_CEREMONY`

Esse estado significa apenas que existe material determinístico para uma futura
cerimônia de assinatura do HUMAN_OWNER.

Ele permite:

- `checkpoint_external_persistence_verified=true`;
- `signature_material_ready=true`;
- um novo `digest_to_sign` ligado à attestation.

Ele **não** permite:

- decisão do proprietário;
- assinatura automática;
- biometria passiva;
- Core Freeze;
- merge;
- deploy;
- arming do Worker;
- execução externa.

Por isso continuam:

- `owner_decision_ready=false`;
- `owner_decision=UNDECIDED`;
- `signature_active=false`;
- `biometric_capture_performed=false`;
- `signature_performed=false`;
- `core_freeze_authorized=false`;
- `core_frozen=false`;
- `worker_armed=false`;
- `execution_allowed=false`.

## Novo digest assinável

O digest V2.23 não reutiliza cegamente o challenge V2.22.

Ele cria um novo challenge que inclui:

- target commit SHA;
- challenge digest V2.22;
- binding digest runtime;
- digest do runtime checkpoint;
- runtime SHA;
- runtime source;
- write receipt intent id;
- schema do receipt;
- confirmação de persistence attested;
- decisão ainda UNDECIDED;
- flags críticas ainda falsas.

Assim a futura assinatura estará ligada não apenas ao estado revisado, mas também à
prova concreta de persistência desse estado.

## Frescor

A observação runtime precisa ter no máximo 300 segundos.

Observação stale ou futura bloqueia a attestation.

## Estado real em 04/10/2026

A auditoria read-only do runtime oficial encontrou:

- branch: `atlasquant-runtime`;
- path: `dados/aion/checkpoint_master.json`;
- schema: `ATLASQUANT_AION_MEMORY_V1`;
- checkpoint version: 18;
- namespace V2.23: ausente.

Portanto o runtime real ainda **não está atestado pela V2.23**.

Isso é esperado: nenhuma persistência foi executada neste bloco.

## Próxima fronteira

Depois de uma futura persistência explicitamente autorizada e confirmada, V2.23 pode
produzir material assinável.

A camada seguinte deve realizar/verificar a cerimônia explícita de assinatura do
HUMAN_OWNER, mantendo assinatura separada de decisão e decisão separada de Core Freeze.
