# AION Global Worker — Activation Dry Run — 2026-09-29

Status: **READ-ONLY / NÃO EXECUTADO / NÃO AUTORIZA ATIVAÇÃO**.

Este documento transforma o caminho de ativação já implementado em uma sequência verificável, sem escrever variável de repositório, sem persistir estado real e sem executar tick de worker.

## Estado atual do candidato

- PR autoritativa: #359
- Base: `main`
- Base SHA validado: `2c9dade6a87d6f618f05cbb628eb35cee2f3a8a1`
- Head SHA validado: `a0fa2dff38d2de7e934f3897ecf06dd025552028`
- Estado: Draft / mergeable observado / **não autorizado para merge**
- Quality: 3801 testes, OK
- Security Gate, Supply-chain, Adversarial, Worker Readiness, Release Readiness, UI Smoke e Mobile DOM: SUCCESS no par base/head validado.

## Regra principal

**Readiness não é activation.**

Nenhum resultado verde acima altera a variável de feature flag, não executa worker real e não confirma 24/7.

## Cerimônia prevista pelo código

### 1. Runtime precisa estar confirmado

Antes de qualquer plano de ativação:

- checkpoint runtime precisa carregar como `CONFIRMED`;
- SHA do runtime precisa existir;
- integridade do checkpoint precisa passar;
- branch precisa ser a branch dedicada de runtime;
- estado Global Worker precisa estar persistido e coerente.

Falha em qualquer item => **BLOCKED**.

### 2. Feature flag precisa ser provadamente segura

A leitura autoritativa da variável de repositório precisa retornar:

- status `CONFIRMED`;
- estado `UNSET` ou `DISABLED`;
- `safe_for_arming_persistence=True`.

Estado `ENABLED`, desconhecido, leitura sem token ou leitura inconclusiva => **BLOCKED**.

### 3. Persisted Arming Ceremony

A persistência de ARMED é separada da ativação da flag.

O plano fica vinculado a:

- working checkpoint digest;
- runtime SHA;
- arm digest;
- estado da feature flag;
- escopo/contexto autenticado;
- janela de validade do approval.

A escrita exige:

1. approval válido;
2. frase exata da cerimônia;
3. segunda confirmação explícita;
4. nova prova de que a flag continua UNSET/DISABLED imediatamente antes da escrita;
5. CAS/readback;
6. verificação pós-escrita.

Qualquer divergência => rollback/bloqueio.

### 4. Activation Approval

A ativação da feature flag possui approval próprio e separado.

O ticket precisa continuar válido e vinculado ao mesmo:

- contexto;
- runtime SHA;
- runtime digest;
- arm digest;
- estado da flag observado no plano;
- confirmation phrase digest.

Mudança entre planejamento e execução => **BLOCKED**.

### 5. Post-incident reactivation gate

Se houver incidente anterior, a reativação exige gate fresco.

O gate precisa provar, entre outros contratos:

- incidente fechado;
- evidência reconciliada;
- feature flag segura;
- confirmação humana;
- separação entre encerramento do incidente e autorização de reativação;
- validade temporal do gate.

Gate ausente/expirado/divergente => **BLOCKED**.

### 6. Confirmação final antes de qualquer mutação

`activate_global_worker_feature_flag(..., confirmation=True)` exige booleano exato.

Qualquer valor textual/numérico/ambíguo ou `False` => bloqueio **antes** da mutação.

### 7. Escrita da feature flag

Somente após todos os gates acima.

- UNSET => create da variável;
- DISABLED => patch da variável;
- target => ENABLED.

O código usa timeout e não executa worker tick nessa função.

### 8. Read-after-write obrigatório

Após a escrita:

- feature flag precisa reler como CONFIRMED/ENABLED;
- runtime precisa ser relido;
- approval precisa continuar válido sobre o runtime relido.

Se a escrita retornar erro/resultado incerto, o código relê a flag.

Se observar ENABLED após resultado incerto, tenta rollback imediato para DISABLED.

Rollback não confirmado => estado crítico; nunca declarar sucesso.

### 9. Estado depois da ativação

Mesmo com flag ENABLED e readback coerente, o status correto é:

`ACTIVATED_PENDING_LIVE_EVIDENCE`

Isto **não** significa:

- heartbeat confirmado;
- tick confirmado;
- receipt confirmado;
- 24/7 confirmado;
- multi-instance safety confirmada.

### 10. Live Verification

A promoção de estado operacional depende de evidência live separada:

- heartbeat;
- receipt/tick;
- binding ao runtime/arm state;
- freshness;
- ausência de divergência.

Sem evidência suficiente => manter UNKNOWN/PENDING, nunca inventar sucesso.

## Rollback

Há caminhos explícitos para:

- rollback de persisted arming se pós-escrita divergir;
- force-disable da feature flag se ativação tiver resultado incerto e flag aparecer ENABLED;
- bloqueio crítico se rollback não puder ser confirmado.

Nenhum retry automático deve acontecer após outcome ambíguo.

## Dry-run atual

Resultado desta revisão:

- caminho de ativação possui confirmações separadas;
- persisted arming e feature-flag activation são cerimônias diferentes;
- activation exige confirmação final exata;
- feature flag é relida antes/depois;
- resultado verde de CI não é usado como autoridade para ativação;
- live evidence continua obrigatória;
- nenhuma ativação foi executada nesta revisão.

## Stop conditions obrigatórias

Parar e pedir decisão humana antes de:

- persistir ARMED em runtime real;
- alterar variável `ATLASQUANT_AION_GLOBAL_WORKER_ENABLED`;
- executar ativação real;
- aceitar reactivation gate real;
- habilitar serviço/cron/runner contínuo;
- declarar 24/7;
- alterar ruleset/branch protection;
- mergear #359;
- fazer deploy.

## Próximo passo permitido sem aprovação

Somente auditoria/read-only, documentação e revalidação de CI se base/head mudarem.

