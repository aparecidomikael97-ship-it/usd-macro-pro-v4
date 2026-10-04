# AION V2.22 — Core Freeze Ceremony Preflight

**Base:** V2.21 hardened head `bb30b1ef8b42af792366d46bc2d856be290b429d`

## Objetivo

V2.22 prepara a cerimônia de decisão crítica do proprietário sem tomar a decisão.

O máximo automático desta camada é:

`READY_FOR_OWNER_DECISION_PREFLIGHT`

Esse estado significa somente que o material lógico está consistente. Ele **não**
significa que a persistência externa oficial foi provada e, portanto, não libera
assinatura nem decisão do proprietário.

Isso não significa:

- decisão registrada;
- Core Complete;
- Core Freeze;
- Checkpoint salvo externamente;
- merge;
- deploy;
- worker armado;
- execução externa.

## Binding contra TOCTOU

A futura decisão de Core Freeze precisa estar ligada ao estado exato que foi revisado.

O preflight vincula o desafio a:

- target commit SHA;
- digest do manifesto V2.20;
- binding do trust root de certificação;
- digest do review V2.21;
- digest do Checkpoint Mestre;
- state digest do Checkpoint Mestre;
- revision exata do Checkpoint Mestre;
- ceremony id;
- nonce;
- janela curta de validade.

Se o Checkpoint mudar depois que o desafio foi preparado, o preflight deixa de ser
válido e uma nova cerimônia é necessária.

## Checkpoint Mestre obrigatório

Para chegar a `READY_FOR_OWNER_DECISION_PREFLIGHT`, o Checkpoint Mestre fornecido precisa conter
o registro `aion_core_completion_review` correspondente exatamente ao review V2.21.

Isso fecha a cadeia:

V2.20 certification -> V2.21 review -> Checkpoint Mestre -> V2.22 decision challenge.

A V2.22 **não salva** o Checkpoint. Ela apenas verifica o que foi fornecido.

No estado real atual, enquanto o review V2.21 não estiver explicitamente persistido no
Checkpoint oficial, a cerimônia real deve permanecer bloqueada.

## Desafio de decisão

Quando os pré-requisitos lógicos são válidos, a V2.22 produz um
`challenge_digest`, mas mantém `digest_to_sign=""`.

O material só poderá se tornar assinável em uma camada posterior que prove a
persistência externa oficial do estado revisado.

O desafio permanece:

- `owner_decision_preflight_ready=true` apenas para preparação;
- `owner_decision_ready=false`;
- `checkpoint_external_persistence_verified=false`;
- `signature_material_ready=false`;
- `owner_decision=UNDECIDED`;
- `owner_decision_recorded=false`;
- `core_freeze_authorized=false`;
- `core_frozen=false`;
- `checkpoint_saved=false`;
- `merge_authorized=false`;
- `deploy_authorized=false`;
- `execution_allowed=false`;
- `worker_armed=false`;
- `external_action_executed=false`.

O digest cobre também a decisão ainda não tomada e todas as flags de segurança.

## Assinatura crítica

O preflight somente prepara o material canônico.

Ele declara:

`signature_mechanism=FIDO2_OR_PLATFORM_SIGNATURE_FUTURE`

mas mantém:

- `signature_active=false`;
- `biometric_capture_performed=false`;
- `signature_performed=false`.

Ou seja: esta versão não captura Windows Hello, FIDO2 ou biometria e não fabrica
aprovação.

## Janela temporal

O challenge é curto e fail-closed.

A janela máxima é de 900 segundos.

Challenge expirado, ainda não válido ou com janela excessiva é bloqueado.

## Recheck antes da decisão

`verify_preflight_still_current()` não confia no hash fornecido pelo caller. Ela
reconstrói novamente a cadeia assinada V2.20 -> V2.21 -> Checkpoint -> V2.22 e compara
o challenge reconstruído com o challenge apresentado.

Ela também verifica:

- `digest_to_sign == challenge_digest`;
- validade temporal;
- Checkpoint master digest;
- state digest;
- revision;
- decisão ainda `UNDECIDED`;
- flags críticas.

Qualquer mudança exige novo preflight.

## CI

CI pode usar dados sintéticos e checkpoint em memória para provar o mecanismo.

Isso não significa que:

- o review V2.21 real foi salvo externamente;
- o proprietário aprovou freeze;
- existe assinatura FIDO2/Windows Hello ativa;
- o Core foi congelado.

CI valida somente o contrato.


## Limite explícito de persistência

O contrato V2.3 de Checkpoint Mestre é lógico/offline. O runtime oficial usa o fluxo
de persistência de `atlasquant_aion_memory`, com write receipt e read-after-write.
Nesta versão ainda não existe uma bridge explícita que prove que um envelope V2.3
específico foi persistido pelo runtime oficial.

Por isso V2.22 falha fechada semanticamente: ela **não** afirma persistência externa,
não expõe `digest_to_sign` e não declara a decisão pronta. A próxima camada deverá
criar essa ponte de evidência sem executar save automaticamente.
