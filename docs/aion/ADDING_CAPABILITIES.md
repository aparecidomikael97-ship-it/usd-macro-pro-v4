# Como adicionar uma capability ao AION

## 1. Defina o contrato

Registre uma `Capability` em `atlasquant_aion_capabilities.py` ou forneça uma
lista validada ao `CapabilityRegistry`.

```python
{
    "capability_id": "support.triage",
    "specialist": "support",
    "domains": ["support"],
    "description": "Organizar dúvidas de suporte.",
    "inputs": ["question"],
    "outputs": ["triage"],
    "risk": "LOW",
    "allowed_tools": [],
    "allowed_roles": ["USER", "SALES", "ADMIN"],
    "requires_confirmation": False,
    "estimated_cost_usd": 0,
    "availability": "AVAILABLE",
    "execution_mode": "READ_ONLY",
    "aliases": ["suporte", "atendimento"],
    "guardian_action": "read",
}
```

Use um ID estável. Declare inputs, outputs e riscos reais. Não esconda custo,
side effect ou dependência externa.

## 2. Conecte um especialista real

Adicione o adapter correspondente em `SPECIALIST_MODULES`, dentro de
`atlasquant_aion_specialists.py`, e uma leitura pura em
`atlasquant_aion_specialist_evidence.py`. Reutilize módulos existentes. O
especialista não recebe permissão própria e não pode executar fora do Guardian.
A leitura local marca `answer_truth=UNKNOWN` e não transforma contrato de código
em fato de mercado. Se a capability for consumir sessão, use
`atlasquant_aion_specialist_session.py` e passe apenas o snapshot já carregado.
Não busque rede para preencher ausência, não promova dado stale a fato atual e
não escolha um lado de um conflito.

Se ainda não houver implementação:

- marque a capability como `EXPERIMENTAL` ou `UNAVAILABLE`;
- mantenha fallback read-only;
- mostre a dependência, sem simular resultado.

## 3. Defina verdade e frescor

Resultados factuais devem fornecer evidências para
`atlasquant_aion_truth.assess_truth`:

```python
{
    "claim": "identificador",
    "value": "...",
    "truth_state": "CONFIRMED",
    "source": "fonte identificada",
    "source_ref": "referência",
    "source_tier": "PRIMARY",
    "timestamp": "ISO-8601",
    "ttl_seconds": 300,
}
```

Não use `CONFIRMED` sem fonte. Para informação temporal, timestamp e TTL são
obrigatórios. Preserve conflitos.

## 4. Aplique permissões e feature flags

Defina `allowed_roles`. Ferramenta administrativa ou de desenvolvimento deve
permanecer ADMIN. A visibilidade da UI não substitui essa verificação.

Capacidade experimental deve possuir flag segura. Não crie caminho que altere:

- `REAL_TRADING_ENABLED=False`;
- `AION_EXTERNAL_ACTIONS_ENABLED=False`;
- bloqueios de secret, merge ou deploy.

## 5. Registre observabilidade

Use `execution_event` para registrar somente metadata:

- request/task IDs;
- domínio e capability;
- ferramenta;
- duração e status;
- risco e aprovação;
- fallback e confiança;
- tipo de erro.

Nunca registre prompt completo, senha, chave, token ou URL com credencial.

## 6. Teste

Inclua no mínimo:

- roteamento pelo metadata;
- role permitida e negada;
- capability/ferramenta indisponível;
- fonte ausente, stale e conflito;
- ação sensível sem aprovação;
- segredo redigido;
- fallback seguro;
- nenhum side effect;
- `real_orders_enabled=False`.

Adicione o teste ao workflow `.github/workflows/quality-tests.yml`.

## 7. Definition of Done

Uma capability só está pronta quando contrato, adapter, testes, Critic,
documentação e rollback aplicável estiverem presentes. `READY` no orquestrador
é preflight; release, merge, deploy e ativação externa continuam humanos.
