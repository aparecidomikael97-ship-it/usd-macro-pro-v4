# ADR-0025 — Hub de Integrações Business deve ser least-privilege e secret-free antes do runtime

- Título: Hub de Integrações Business deve ser least-privilege e secret-free antes do runtime
- Data: 2026-09-30
- Status: ACCEPTED

## Contexto

O AION Business depende futuramente de WhatsApp Business, e-mail, formulários,
calendário, CRM, pagamentos, redes sociais e analytics.

## Problema

Conectar provedores antes de definir escopos, saúde, autorização e tratamento de
credenciais pode abrir permissões excessivas, vazamento de segredo e ações
externas não intencionais.

## Decisão

Criar primeiro um Hub de Readiness sem conexão real.

Cada integração possui estado, finalidade, escopo mínimo e postura de saúde.
Write scopes ficam separados de read/draft e exigem autorização futura.

Credenciais reais são proibidas no demo e produção futura requer secret store
dedicado, rotação e least privilege.

## Consequências

O produto pode desenhar e auditar integrações antes de abrir OAuth ou escrever em
sistemas externos.

## Segurança

Nenhuma integração deste ADR envia, publica, cobra, exclui, administra ou ativa
runtime.

## Compatibilidade

ADR-0024 define captação e jornada comercial. Este ADR prepara as dependências
externas necessárias para onboarding e operação futura.

## Rollback

Módulo de readiness/offline; remoção sem efeitos externos.

## Supersedes

Nenhum.

## Superseded by

Nenhum.
