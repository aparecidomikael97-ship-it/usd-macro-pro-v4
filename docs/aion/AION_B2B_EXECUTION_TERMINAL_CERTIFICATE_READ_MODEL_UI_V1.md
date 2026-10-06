# AION B2B — Execution Terminal Certificate Read-Model UI V1

Status: **design-only / fail-closed / read-only / non-executable**.

## Objetivo

Definir a fronteira de apresentação do futuro painel do certificado terminal sem
permitir que evidência visual seja confundida com autoridade operacional.

Modo:

`READ_ONLY_FAIL_CLOSED_TERMINAL_CERTIFICATE_PANEL`

## Estado máximo

`READY_FOR_EXECUTION_TERMINAL_CERTIFICATE_READ_MODEL_UI_DESIGN_REVIEW`

Próximo passo permitido:

`DESIGN_EXECUTION_TERMINAL_CERTIFICATE_RUNTIME_READER_ONLY`

## Fonte única

A UI futura só poderá consumir o Terminal Certificate Read Model. Ela não deve
abrir banco, consultar provider nem reconstruir verdade operacional por conta
própria.

## Estados

A UI reconhece exatamente:

- `VERIFIED`;
- `MISMATCH`;
- `UNAVAILABLE`;
- `STALE`.

Somente VERIFIED pode usar aparência positiva, e apenas quando o próprio read
model estiver VERIFIED. Mismatch, ausência, stale ou estado desconhecido são
fail-closed.

## Seções obrigatórias

O painel futuro deve separar:

- status do certificado;
- execution id;
- estado terminal;
- revisão terminal;
- digest do certificado;
- evidência de finalização;
- audit seal;
- FinOps;
- trace de observabilidade;
- escopo tenant/workspace.

## Controles proibidos

A UI não pode conter controles que executem:

- ação externa;
- retry;
- reopen;
- reconciliação;
- rollback/compensação;
- emissão/assinatura/exclusão/substituição de certificado;
- cobrança;
- contato com cliente;
- escrita CRM;
- provisionamento;
- deploy;
- mutação de produção.

## Material proibido

Nunca renderizar credenciais, secrets, tokens, chaves privadas/signing keys,
authorization headers, payload bruto, resposta bruta de provider, mensagem
bruta de cliente ou comando de shell.

## Separação evidência x autoridade

Badge, digest, estado terminal e certificado são somente informação. Nenhum
estado visual pode conceder autoridade de execução, retry, reopen ou efeito
externo.

## Limite desta versão

Esta camada ainda não renderiza HTML/Streamlit e não lê dados reais. Ela fixa o
contrato de apresentação que a futura UI deverá obedecer.
