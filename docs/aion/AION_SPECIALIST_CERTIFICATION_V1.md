# AION Specialist Certification V1

Schema: `ATLASQUANT_AION_SPECIALIST_CERTIFICATION_V1`

Este contrato certifica especialistas de domínio do núcleo AION. Ele não é o
contrato `ATLASQUANT_AION_SKILL_CERTIFICATION_V1`. Skill, plugin e especialista
permanecem conceitos diferentes. A decisão de exigir os quatro fechamentos está
em ADR-0010. O núcleo único está em ADR-0001. A ausência de permissão
independente está em ADR-0005.

## Especialistas

O roteador determinístico reconhece:

| Domínio | Perfil | Nome |
| --- | --- | --- |
| TRADER | `TRADER_EXPERT` | AION Trader Expert |
| BUSINESS | `BUSINESS_EXPERT` | AION Business Expert |
| INVESTMENTS | `INVESTMENT_EXPERT` | AION Investment Expert |
| AION/CORE | `AION_CORE` | AION completo |

Não são quatro IAs. O roteador apenas seleciona o perfil. Domínio desconhecido
responde `UNKNOWN` / `DENIED_SAFE`. Domínio ambíguo responde
`CLARIFICATION_REQUIRED`. Especialista ausente responde `DEGRADED_SAFE`. Não há
fallback silencioso nem ampliação de permissão por inferência.

`BUSINESS_FUTURE`, `TRADER_FUTURE` e `INVESTMENTS_FUTURE` continuam com runtime
indisponível. O registry separa domínio reconhecido, perfil registrado,
capability de runtime e certificação. Registrado pode coexistir com
`NOT_CERTIFIED`.

## Permissões

Trader Expert lê e analisa evidência de mercado permitida. Não recebe trade
real, pagamento, deploy nem publicação.

Business Expert analisa e prepara material comercial. Não envia contato, não
assina contrato, não gasta, não publica e não cobra.

Investment Expert analisa e compara. Não movimenta dinheiro, não compra, não
vende e não altera carteira real.

AION Core coordena os especialistas e não herda a autoridade física de nenhum
deles. O especialista não amplia role, scope ou ferramenta do contexto pai.
Papel, ferramenta, escopo ou ação do perfil são metadata
(`profile_allowed_roles`, `profile_allowed_tools`, `profile_allowed_actions`).
Eles só entram em `granted_roles`, `granted_tools`, `granted_scopes` ou
`granted_actions` quando o contexto pai traz essa autoridade. Scope efetivo
ainda exige a allowlist do perfil, o guardião e runtime ligado. `*` não abre
acesso. Pai ausente ou vazio não concede nada: `authority_bound=false` e
`permissions_expanded=false`.
Quando aplicável, a seleção também reporta `external_action_executed=false`,
`real_trading_enabled=false`, `payment_executed=false` e
`publication_executed=false`.

## Memória e evidência

`automatic_cross_domain_access=false`. Memória TRADER não aparece para
BUSINESS. Memória BUSINESS não aparece para INVESTMENTS. O Core só lê outro
domínio com perfil `AION_CORE` e o domínio de origem nomeado em
`explicit_domains`. `AION_CORE` sozinho não abre evidência cruzada. Essa
leitura não promove evidência: `UNKNOWN` continua `UNKNOWN`, `STALE` não vira
fato atual, `CONFLICT` continua conflito e `INCOMPLETE` continua fechado. O
isolamento por persona já existente permanece.

## Estados

`CANDIDATE`, `TESTED`, `CERTIFIED`, `SUSPENDED`, `REVOKED`.

`CERTIFIED` só existe quando a evidência explícita comprova, ao mesmo tempo:

- roteamento correto e domínio ambíguo sem seleção silenciosa;
- memória e evidência separadas, com cruzamento automático desligado;
- ausência de escalada de scope, role e ferramenta não declarada;
- verdade fail-closed para `UNKNOWN`, `STALE`, `CONFLICT` e `INCOMPLETE`;
- trade real, pagamento, publicação, deploy e efeito externo desligados;
- suíte explícita `PASS`, com versão e fingerprint igual ao hash do corpo da
  prova;
- proveniência confirmada por um `evidence_verifier` externo ao payload.
  Texto autodeclarado, inclusive `local-specialist-suite`, não verifica;
- SHA ausente continua opcional. SHA presente precisa ser hexadecimal de 7 a
  64 caracteres e coincidir com a referência do verifier. Refs presentes entram
  no corpo e na lista verificada;
- `tests_pass=true`, `evidence_verified=true` vindo do verifier, e
  `human_review_approved` igual ao booleano `True`. Revisão humana não substitui
  a prova técnica. `evidence_verified=true` escrito no payload, sem verifier,
  não certifica.

As strings `"true"`, `"yes"` e `"approved"`, assim como `1` e `None`, não contam
como aprovação. `TESTED` sem revisão humana não vira `CERTIFIED`.

A certificação não ativa o especialista, não chama ferramenta, não expande
permissão e não executa ação.

## Readiness

`specialist_readiness_matrix()` é somente leitura. Dimensão sem evidência fica
`NOT_EVIDENCED`. O agregado fica `READY` somente quando Trader, Business e
Investments estão `CERTIFIED` com todas as dimensões exigidas em `PASS`.
Existir código não certifica o especialista. O agregado do Core não esconde um
especialista sem certificação.

## Fora deste contrato

Este gate não adiciona estratégia de Trader, Average Daily Range, ATR,
American Depositary Receipts, automação comercial real, CRM, Opportunity Scout,
investimento real, chamada de provider ou trading real.
