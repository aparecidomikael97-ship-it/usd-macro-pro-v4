# AION B2B — Execution Terminal Certificate Runtime Reader V1

Status: **design-only / fail-closed / read-only / non-executable**.

## Objetivo

Definir a fronteira de segurança do futuro leitor de runtime do certificado
terminal sem transformar leitura, status ou evidência em autoridade operacional.

Modo:

`READ_ONLY_FAIL_CLOSED_TERMINAL_CERTIFICATE_RUNTIME_READER`

## Estado máximo

`READY_FOR_EXECUTION_TERMINAL_CERTIFICATE_RUNTIME_READER_DESIGN_REVIEW`

Próximo passo permitido:

`DESIGN_EXECUTION_TERMINAL_CERTIFICATE_RUNTIME_READER_STORE_ADAPTER_ONLY`

## Pré-condição

Esta camada só pode avançar depois do
`Execution Terminal Certificate Read Model UI V1` estar exatamente em estado
de design review e continuar:

- design-only;
- fail-closed;
- read-only;
- observacional;
- consumindo somente o read model;
- sem controles de ação;
- sem autoridade de execução, retry, reopen ou efeito externo.

## Fonte lógica

O futuro runtime reader deve tratar o Terminal Certificate Read Model como sua
única fonte lógica de projeção. Não pode reconstruir verdade por conta própria a
partir de provider, rede, UI ou payload bruto.

## Estados

O leitor reconhece exatamente:

- `VERIFIED`;
- `MISMATCH`;
- `UNAVAILABLE`;
- `STALE`.

Somente `VERIFIED` pode ser retornado quando identidade, escopo, revisão
terminal e todos os digests vinculados forem consistentes. Qualquer ausência,
stale, mismatch ou estado desconhecido permanece fail-closed.

## Regras obrigatórias

O futuro leitor deve exigir:

- execution id canônico;
- tenant e workspace exatos;
- certificado persistido;
- terminal revision exata;
- snapshot consistente;
- certificate digest consistente;
- finalization digest consistente;
- audit seal digest consistente;
- ausência de fallback para provider;
- ausência de fallback para rede;
- ausência de qualquer mutação.

## Separação evidência x autoridade

Ler ou verificar um certificado não autoriza:

- nova execução;
- retry;
- reopen;
- reconciliação;
- rollback ou compensação;
- efeito externo;
- billing;
- contato com cliente;
- escrita CRM;
- provisionamento;
- deploy;
- mutação de produção.

## Material proibido

Nunca expor nem carregar como saída de leitura:

- credentials, secrets, passwords ou tokens;
- chaves privadas ou signing keys;
- authorization headers;
- payload bruto;
- resposta bruta de provider;
- mensagem bruta de cliente;
- comando de shell.

## Limite desta versão

Esta camada **não** abre banco/store, não lê registro real, não verifica digest
ao vivo, não acessa rede, não consulta provider e não renderiza UI. Ela fixa
somente o contrato que um futuro store adapter read-only deverá obedecer.

## FinOps

Permanece o teto de **R$ 200/mês** (`20000` centavos) nesta fase.

## Regra fail-closed

Qualquer divergência de schema, estado, escopo, revisão, digest,
canonicalização, material sensível ou flag de autoridade bloqueia a progressão.
