# ADR-0024 — Aquisição comercial do AION Business deve terminar em diagnóstico antes de venda

- Título: Aquisição comercial do AION Business deve terminar em diagnóstico antes de venda
- Data: 2026-09-30
- Status: ACCEPTED

## Contexto

O usuário precisa dominar como empresas serão encontradas, como o serviço será
divulgado, como o site apresenta a solução e como o lead percorre proposta,
contrato e onboarding.

## Problema

Vender ferramenta avulsa ou iniciar automação antes de entender o problema pode
gerar escopo ruim, promessa indevida, contato sem revisão e baixa retenção.

## Decisão

O fluxo comercial oficial passa a ser:

Canal → Lead → Qualificação → Diagnóstico → Proposta Draft → Revisões →
Assinatura futura → Cobrança futura → Onboarding.

O CTA principal do site é **Solicitar diagnóstico**, não "comprar agora".

Outreach é draft-only e respeita estado de permissão. Conteúdo e cases exigem
aprovação e evidência.

## Consequências

A venda fica consultiva e orientada ao problema do cliente. O pacote nasce do
diagnóstico, e não de uma lista fixa de ferramentas.

## Segurança

Nenhuma etapa deste demo envia mensagem, assina contrato, emite cobrança,
publica conteúdo, gasta orçamento ou ativa runtime.

## Compatibilidade

ADR-0023 cuida de tendências e oportunidades. Este ADR transforma oportunidades
em um funil comercial controlado.

## Rollback

Módulo offline/session-only; remoção sem compensação externa.

## Supersedes

Nenhum.

## Superseded by

Nenhum.
