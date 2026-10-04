# AION V2.21 — Core Completion Review Gate

**Base:** V2.20 hardened head `e9f8df996da88f4a060e31f597e489ad2c3176b1`

## Objetivo

V2.21 fecha a lacuna entre uma certificação V2.20 válida e a revisão humana final
do núcleo.

Ela não declara Core Complete e não executa Core Freeze.

O máximo automático desta camada é:

`READY_FOR_OWNER_REVIEW`

## Princípio de confiança

V2.21 não confia nos booleanos do manifesto V2.20.

Ela reconstrói as evidências assinadas do manifesto e chama novamente o contrato
V2.20 com o trust root público fornecido pelo host confiável.

Para ficar pronta para revisão, é obrigatório:

- schema V2.20 correto;
- target SHA válido e igual ao SHA esperado;
- conjunto exato das 17 dimensões V2.20;
- todas as evidências novamente verificáveis por Ed25519;
- manifest digest reconstruído igual ao digest fornecido;
- `CERTIFICATION_CANDIDATE` real;
- `CANONICAL_GATES` assinado e verde;
- `GLOBAL_WORKER_READINESS` assinado e verde;
- nenhum campo inseguro promovido fora do digest.

## Campos que continuam obrigatoriamente falsos

Mesmo com `READY_FOR_OWNER_REVIEW`:

- `core_complete=false`;
- `core_complete_claim_allowed=false`;
- `owner_decision_recorded=false`;
- `core_freeze_authorized=false`;
- `core_frozen=false`;
- `checkpoint_saved=false`;
- `execution_allowed=false`;
- `worker_armed=false`;
- `merge_authorized=false`;
- `deploy_authorized=false`;
- `external_action_executed=false`.

## Checkpoint Mestre

V2.21 não cria store paralelo.

A função de checkpoint produz apenas um **patch candidate** para o namespace:

`aion_core_completion_review`

O patch contém digest, SHA alvo, digest do certificado, binding do trust root,
blockers e o estado de revisão.

Persistência externa continua fora desta camada e exige o fluxo explícito já
definido pelo Checkpoint Mestre.

Portanto:

- gerar patch != salvar checkpoint;
- staging em memória != persistência remota;
- owner review != freeze;
- freeze != merge;
- merge != deploy;
- deploy != ativação de runtime.

## Relação com o estado atual

O workflow V2.21 pode validar o mecanismo com chaves efêmeras de teste.

Isso não cria a certificação real do Core em produção.

A revisão real só poderá ficar `READY_FOR_OWNER_REVIEW` quando houver um manifesto
V2.20 real, com evidências assinadas por trust root de certificação provisionado fora
do repositório e com Global Worker readiness efetivamente saudável.

## Fail-closed

Bloqueiam a revisão:

- manifesto ausente ou schema incorreto;
- target SHA inválido ou divergente;
- dimensão V2.20 faltante ou extra;
- assinatura inválida;
- chave desconhecida, revogada ou fora da janela;
- evidência expirada;
- manifest digest divergente;
- candidate/state adulterados;
- qualquer tentativa de marcar freeze, execução, worker, merge ou deploy como verdadeiro.

## Saída

A saída é um pacote determinístico com `review_digest`.

Esse digest pode ser referenciado em um evento explícito do Checkpoint Mestre, mas a
V2.21 não grava esse evento automaticamente.
