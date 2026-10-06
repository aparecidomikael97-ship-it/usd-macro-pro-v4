# AION V2.26 — Owner Decision Record Persistence Attestation

## Objetivo

V2.26 fecha a fronteira entre:

- decisão criptograficamente verificada na V2.25;
- decision record realmente persistido;
- elegibilidade para uma futura cerimônia de Core Freeze.

Ela não executa persistência. Ela prepara um candidato em memória e depois verifica
evidência externa de escrita + read-after-write.

## Pré-requisitos

V2.26 exige a cadeia completa:

1. V2.23 com persistência do estado anterior atestada;
2. assinatura V2.24 válida sobre identidade + estado;
3. request V2.25 canônico;
4. assinatura V2.25 válida sobre APPROVE ou DENY;
5. nonce V2.25 durável do **request exato**.

O nonce é preso ao digest exato do request V2.25. A V2.26 lê essa claim de forma
read-only e usa o `created_at` durável para reconstruir o instante da verificação.

## Revalidação V2.25 sem confiar no caller

V2.26 não aceita um objeto `verified_decision` como autoridade.

Ela:

- recalcula o digest do request;
- reconstrói o escopo do nonce;
- exige claim durável correspondente;
- verifica janela temporal histórica da claim;
- reconstrói V2.25 usando a evidência V2.24/V2.23;
- exige request reconstruído idêntico;
- verifica chave pública/fingerprint;
- verifica novamente a assinatura Ed25519 da decisão.

Somente então prepara o record.

## Runtime namespace

O record é preparado em:

`aion_core_owner_decision_v1`

Ele contém, entre outros:

- target commit SHA;
- APPROVE/DENY;
- decision request digest;
- decision signature digest;
- nonce e digest do scope;
- instante durável da claim;
- V2.24 request/signature digests;
- V2.23 digest;
- key id/version/fingerprint;
- `owner_decision_verified=true`;
- `owner_decision_recorded=false`;
- `decision_record_persisted=false`;
- `persistence_attested=false`;
- flags de freeze/execução false.

O record tem `record_digest` determinístico.

## Staging não é save

`stage_owner_decision_record_persistence_candidate()`:

- parte do runtime V2.23 confirmado;
- adiciona o record em memória;
- calcula o runtime digest esperado;
- registra o SHA anterior esperado para CAS;
- marca que save explícito e attestation são necessários.

Ela não chama rede nem save.

## Attestation

`verify_owner_decision_record_persistence()` exige:

- runtime CONFIRMED;
- observação fresca;
- repo exato `aparecidomikael97-ship-it/usd-macro-pro-v4`;
- branch exata `atlasquant-runtime`;
- path exato `dados/aion/checkpoint_master.json`;
- receipt válido;
- `expected_sha` igual ao SHA V2.23 anterior;
- SHA novo diferente do SHA anterior;
- write SHA igual ao runtime SHA observado;
- conteúdo final igual ao candidato staged;
- namespace/record exatos;
- record digest íntegro;
- `reconcile_runtime_write()` em CONFIRMED;
- write attribution verdadeira;
- read-after-write por SHA + digest.

Conteúdo igual sem atribuição única da escrita não basta.

## Estados positivos

### APPROVE

Após persistência realmente atestada:

`OWNER_DECISION_RECORD_PERSISTENCE_ATTESTED_APPROVE`

Só então:

- `owner_decision_recorded=true`;
- `decision_record_persisted=true`;
- `persistence_attested=true`;
- `core_freeze_ceremony_eligible=true`.

Ainda permanece:

- `core_freeze_execution_authorized=false`;
- `core_freeze_authorized=false`;
- `core_frozen=false`;
- `merge_authorized=false`;
- `deploy_authorized=false`;
- `execution_allowed=false`;
- `worker_armed=false`.

V2.26 pode preparar material determinístico para a futura cerimônia, mas não executa
o freeze.

### DENY

Após persistência realmente atestada:

`OWNER_DECISION_RECORD_PERSISTENCE_ATTESTED_DENY`

A negativa passa a estar registrada de forma durável, porém:

- `core_freeze_ceremony_eligible=false`;
- nenhum material de freeze é emitido.

## CAS e concorrência

O write receipt precisa declarar `expected_sha` exatamente igual ao SHA do runtime
V2.23 usado para montar o candidato.

Se o runtime mudou antes da escrita, a attestation bloqueia.

Também é exigido que o novo runtime SHA seja diferente do anterior.

## Truth boundary

Antes da V2.26 positiva:

- decisão pode estar verificada;
- decisão não está registrada duravelmente.

Depois da V2.26 positiva:

- o decision record pode ser chamado de persistido/registrado;
- APPROVE pode ficar elegível para a próxima cerimônia;
- freeze continua não executado.

## Estado real atual

O runtime real continua V18 e sem V2.23/V2.24/V2.25.

Portanto não existe hoje:

- decisão real persistida;
- attestation V2.26 real;
- elegibilidade real de Core Freeze.

CI usa apenas evidência sintética/controlada.

## Próxima fronteira

Uma futura V2.27 poderá consumir o material V2.26 APPROVE para preparar a cerimônia
de Core Freeze propriamente dita.

Essa camada deverá continuar separada de merge/deploy e de ativação do Worker.
