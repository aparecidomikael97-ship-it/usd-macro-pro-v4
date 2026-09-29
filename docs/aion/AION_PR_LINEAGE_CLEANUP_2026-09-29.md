# AION/Núcleo — PR Lineage Cleanup — 2026-09-29

Status: **limpeza de integração concluída sem merge**.

Objetivo: reduzir ambiguidade entre dezenas de Draft PRs empilhadas e manter uma única ponta autoritativa para integração.

## Ponta autoritativa

- **#359 — AION Core consolidated hardening V2**
- Base: `main`
- Head validado: `a0fa2dff38d2de7e934f3897ecf06dd025552028`
- Estado: OPEN / DRAFT
- Regra: **não fazer merge sem aprovação humana explícita**

## PRs exatas ancestrais arquivadas

As PRs abaixo foram verificadas como ancestrais exatas da ponta #359 e foram fechadas **sem merge**:

#326, #327, #328, #329, #330, #331, #332, #334, #335, #336, #337, #338, #342, #343, #345, #346, #347, #348, #349, #350, #354 e #355.

O fechamento não apaga histórico nem branches; apenas impede integração duplicada.

## PRs divergentes com semântica absorvida

As PRs abaixo tinham linhagem divergente, mas as garantias necessárias já foram explicitamente reconciliadas/absorvidas pela #359. Foram fechadas **sem merge**:

- #339 — Worker lease/runtime hardening;
- #340 — Recovery outcome hardening;
- #351 — supply-chain residual pins;
- #352 — supply-chain residual hardening;
- #353 — Recovery revision binding;
- #356 — optional product-domain isolation;
- #357 — residual resource bounds.

Não reintegrar nenhuma delas separadamente.

## Auditoria histórica

- #333 — Independent Codex Red Team Audit V1 — fechada sem merge e preservada como evidência histórica.
- A reconciliação atual dos achados RT01–RT20 está em `AION_CORE_REDTEAM_CLOSURE_MATRIX_2026-09-29.md`.

## Handoff e interface

- #344 — permanece OPEN/DRAFT como trilha de handoff/validação.
- #358 — permanece OPEN/DRAFT, mas **PAUSADA por solicitação do usuário**.
- #341 — handoff antigo, fechado como superseded pela #344.

## PR legado fora da cadeia atual

- #286 — shared coordination gate — permanece intocado por enquanto.
- Sua linhagem diverge materialmente da #359; não será fechado nem integrado automaticamente sem auditoria específica.

## Regra operacional daqui para frente

1. desenvolvimento/hardening do AION/Núcleo referencia somente #359;
2. documentação/handoff referencia #344;
3. interface só retoma pela #358 quando o usuário pedir;
4. PRs arquivadas não são reabertas nem cherry-picked sem evidência concreta de regressão faltante;
5. se base/head da #359 mudar, revalidar antes de qualquer decisão de integração.
