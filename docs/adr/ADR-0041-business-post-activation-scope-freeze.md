# ADR-0041 — Ativação verificada congela escopo antes de qualquer expansão

- Título: Ativação verificada congela escopo antes de qualquer expansão
- Data: 2026-09-30
- Status: ACCEPTED

## Contexto

ADR-0040 define autorização de runtime limitada e separa autorização de execução.
Ainda faltava fechar o ciclo posterior a uma futura execução real de ativação.

## Problema

Uma ativação concluída não pode ser tratada como permissão para aumentar tenants,
mudar de pilot para produção limitada, iniciar cobrança ou ampliar ações com
clientes.

## Decisão

Criar uma verificação pós-ativação read-only que exige:

1. packet de revisão de execução válido;
2. escopo observado idêntico ao autorizado;
3. conjunto de tenants idêntico ao autorizado;
4. limite de tenants preservado;
5. health, observabilidade, isolamento, privacidade, suporte, billing guardrail e rollback verdes;
6. referência de evidência da ativação;
7. confirmação explícita de runtime somente no escopo autorizado.

O estado verde é RUNTIME_ACTIVATION_VERIFIED_SCOPE_FROZEN.

Somente depois disso pode existir um packet de fronteira com estado
EXPLICIT_EXPANSION_DECISION_REQUIRED e token reservado
AUTHORIZE_BUSINESS_SCOPE_EXPANSION.

Esse packet não autoriza nem executa expansão.

## Consequências

Uma ativação saudável permanece congelada no escopo aprovado. Toda ampliação
passa a exigir nova decisão explícita e nova validação.

## Segurança

Nenhuma função ativa runtime, expande tenants, muda tráfego, deploya, faz
rollback, publica, cobra ou contata clientes.

## Compatibilidade

ADR-0040 fornece o execution review packet. Este ADR verifica somente evidência
de uma execução realizada por caminho separado.

## Rollback

Read-only/administrativo; sem efeito externo a compensar.

## Supersedes

Nenhum.

## Superseded by

Nenhum.
