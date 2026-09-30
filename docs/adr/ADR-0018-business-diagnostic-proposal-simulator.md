# ADR-0018 — Diagnóstico e proposta do AION Business devem começar em simulador draft-only

- Título: Diagnóstico e proposta do AION Business devem começar em simulador draft-only
- Data: 2026-09-30
- Status: ACCEPTED

## Contexto

AION Business já possui Demo visual, sandbox e treinamento guiado. O próximo
passo é ensinar o administrador a transformar dados de uma empresa em
diagnóstico, pacote e proposta.

## Problema

Gerar proposta diretamente para cliente real antes de dominar diagnóstico,
escopo, precificação e limites criaria risco comercial e técnico. Também
poderia induzir preço prematuro ou promessa de resultado.

## Decisão

Criar um simulador offline e draft-only. Ele recebe somente dados fictícios,
gera diagnóstico nos pilares Atrair/Atender/Converter/Reter, monta Radar,
sugere pacote e produz rascunho de proposta.

Preço de implantação e manutenção nunca é calculado automaticamente nesta
versão; permanece `A DEFINIR APÓS ESCOPO`.

O rascunho não possui caminho de envio, assinatura, cobrança ou runtime.

## Consequências

O administrador consegue praticar a venda consultiva de ponta a ponta antes de
usar dados de empresa real. O processo comercial passa a ser ensinado com
verdade de evidência e limites claros.

## Segurança

Nenhum resultado deste simulador autoriza contato, contrato, pagamento,
publicação, gasto, deploy, merge ou runtime.

Não existe garantia de resultado financeiro.

## Compatibilidade

ADR-0017 continua definindo que treinamento precede uso real. Este ADR acrescenta
o exercício estruturado de diagnóstico e proposta.

## Rollback

O módulo é de sessão e sem efeitos externos. Sua remoção não exige compensação
ou migração.

## Supersedes

Nenhum.

## Superseded by

Nenhum.
