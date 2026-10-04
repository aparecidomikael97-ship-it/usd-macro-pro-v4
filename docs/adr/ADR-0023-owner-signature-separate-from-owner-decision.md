# ADR-0023 — Assinatura do proprietário é separada da decisão do proprietário

- Título: Assinatura do proprietário é separada da decisão do proprietário
- Data: 2026-10-04
- Status: ACCEPTED

## Contexto

V2.23 produz material assinável somente depois de provar persistência externa do
estado revisado.

Ainda assim, assinatura e decisão são eventos semanticamente diferentes.

## Problema

Se assinatura significasse automaticamente aprovação, seria possível:

- transformar prova de identidade em autorização operacional;
- congelar o Core sem uma decisão explícita;
- confundir autenticação com consentimento;
- tratar texto comum de chat como substituto de assinatura;
- reutilizar uma assinatura antiga contra estado novo;
- sofrer replay de nonce.

## Alternativas rejeitadas

- interpretar "vamos lá" como aprovação crítica;
- assinatura = Core Freeze;
- assinatura = decisão APPROVE;
- assinatura sem nonce durável;
- assinatura sem reconstruir V2.23;
- confiar no request enviado pelo caller sem reconstrução;
- capturar biometria passivamente;
- armazenar material secreto no repositório;
- afirmar suporte Windows Hello/FIDO2 antes do adaptador real existir.

## Decisão

V2.24 cria uma cerimônia de assinatura de identidade/estado.

O request é reconstruído do estado V2.23 atual e assinado externamente.

Assinatura válida permite somente:

`READY_FOR_EXPLICIT_OWNER_DECISION`

A decisão continua:

`UNDECIDED`

## Segurança

V2.24 exige:

- trust root público separado do HUMAN_OWNER;
- chave ativa e não revogada;
- assinatura Ed25519 válida;
- request idêntico ao reconstruído;
- target/runtime/binding/digests exatos;
- janela máxima de 180 segundos;
- nonce durável anti-replay;
- V2.23 atual no momento da verificação.

Mantém:

- `approval_implied=false`;
- `core_freeze_authorized=false`;
- `core_frozen=false`;
- `execution_allowed=false`;
- `worker_armed=false`;
- nenhuma ação externa.

## Consequências

A cadeia passa a ser:

1. V2.20 certificação;
2. V2.21 review;
3. V2.22 preflight;
4. V2.23 persistência atestada;
5. V2.24 request de assinatura;
6. assinatura externa explícita;
7. V2.24 verificação + anti-replay;
8. decisão explícita posterior;
9. registro de decisão;
10. Core Freeze separado;
11. merge/deploy separados;
12. runtime activation separada.

Nenhuma etapa implica automaticamente a seguinte.

## Windows Hello / FIDO2

A arquitetura mantém espaço para adaptadores de plataforma no futuro.

V2.24 atual não captura biometria e não declara suporte que ainda não existe.

## Compatibilidade

Compõe ADR-0002, ADR-0007, ADR-0009, ADR-0011, ADR-0012, ADR-0019, ADR-0020,
ADR-0021 e ADR-0022.

## PR/commit relacionado

Branch `integration/aion-v224-owner-signature-ceremony-20261004`.

## Supersedes

Nenhum.

## Superseded by

Nenhum.
